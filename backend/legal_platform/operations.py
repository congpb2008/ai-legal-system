"""Local host operations. Backups are encrypted and restores never overwrite data."""
from __future__ import annotations
import contextlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b'LEGALBACKUP1\0'


def restrict_file(path):
    """Keep credentials readable only to their OS owner and machine administrators."""
    if os.name != 'nt':
        os.chmod(path, 0o600)
        return
    import win32api, win32security, ntsecuritycon
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    owner = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    acl = win32security.ACL()
    for sid in (owner, win32security.CreateWellKnownSid(win32security.WinLocalSystemSid), win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid)):
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, sid)
    protection = win32security.PROTECTED_DACL_SECURITY_INFORMATION
    # The service data root grants its installing operator access for backup and
    # setup. Preserve that inherited grant on files created by Local Service.
    local_service = win32security.CreateWellKnownSid(win32security.WinLocalServiceSid)
    if owner == local_service:
        from legal_platform.windows_service import service_data
        if Path(path).resolve().is_relative_to(service_data().resolve()):
            protection = win32security.UNPROTECTED_DACL_SECURITY_INFORMATION
    win32security.SetNamedSecurityInfo(str(path), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | protection,
        None, None, acl, None)


def installation_in_use(root):
    """Probe the actual OS lock, so stale files never imply a live server."""
    path = Path(root) / '.server.lock'
    if not path.exists():
        return False
    try:
        with installation_lock(root):
            return False
    except RuntimeError:
        return True


def recover_administrator(root, username, password):
    """Offline host recovery; never exposed as a web route or a role promotion.

    The host operator already controls this database. Require the server to be
    stopped, target an existing active admin and record the action atomically.
    """
    import time
    from uuid import uuid4
    from datetime import datetime, timezone
    from legal_platform.accounts import digest, password_hash
    root = Path(root).resolve()
    database = root / 'db/legal_platform.db'
    if not database.is_file():
        raise ValueError('This folder does not contain a library database.')
    username = str(username).strip().lower()
    hashed = password_hash(password)
    with installation_lock(root), contextlib.closing(sqlite3.connect(database)) as conn:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            account = conn.execute("SELECT id FROM account WHERE username=? AND role='admin' AND state='active'", (username,)).fetchone()
            if not account:
                raise ValueError('Enter the username of an existing active administrator. Other accounts cannot be promoted through recovery.')
            uid = account[0]
            conn.execute('UPDATE account SET password_hash=?,password_changed_at=? WHERE id=?', (hashed, time.time(), uid))
            conn.execute('DELETE FROM account_session WHERE user_id=?', (uid,))
            conn.execute("DELETE FROM account_code WHERE user_id=? AND purpose='reset'", (uid,))
            conn.execute('DELETE FROM login_throttle WHERE key=?', (digest(username),))
            conn.execute('INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?,?,?)', (
                str(uuid4()), datetime.now(timezone.utc).isoformat(), 'host', 'accounts',
                'ADMINISTRATOR_RECOVERED', 'account', uid, 'WARNING',
                'The host operator reset this administrator password while the server was stopped.', '{}'))
    return username


@contextlib.contextmanager
def installation_lock(root):
    """One server or offline restore operation per data directory."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    handle = open(root / '.server.lock', 'a+b')
    if handle.tell() == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('This data folder is in use. Stop its server first.') from None
    try:
        yield
    finally:
        handle.close()


def _key(password, salt):
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError('Use a backup passphrase of at least 12 characters.')
    return Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode())


def backup(root, destination, password):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Choose a new backup filename; existing backups are never overwritten.')
    db = root / 'db/legal_platform.db'
    if not db.is_file():
        raise ValueError('This folder does not contain a library database.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    salt, nonce = os.urandom(16), os.urandom(12)
    key = _key(password, salt)
    from uuid import uuid4
    temporary = destination.with_name(destination.name + '.' + uuid4().hex + '.partial')
    try:
        with tempfile.TemporaryDirectory(prefix='legal-backup-') as temp:
            temp = Path(temp)
            snapshot = temp / 'database.db'
            with contextlib.closing(sqlite3.connect(str(db))) as source, contextlib.closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
                # Recovery never resurrects logged-in sessions or one-time credentials.
                target.execute('DELETE FROM account_session')
                target.execute('DELETE FROM account_code')
                target.commit()
                refs = [r[0] for r in target.execute('SELECT storage_ref FROM document_source_version UNION SELECT storage_ref FROM document_source')]
            archive = temp / 'archive.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(snapshot, 'db/legal_platform.db')
                for ref in set(refs):
                    file = (root / 'files' / ref).resolve()
                    if not file.is_relative_to(root / 'files') or not file.is_file():
                        raise ValueError('An original source is missing; backup was not created.')
                    z.write(file, 'files/' + Path(ref).as_posix())
                for name in ('provider_config.json', '.configured', '.local-mode'):
                    if (root / name).is_file():
                        z.write(root / name, name)
                z.writestr('manifest.json', json.dumps({'format': 1, 'product': 'Legal Library', 'sessions_restored': False}))
            encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            header = MAGIC + salt + nonce
            encryptor.authenticate_additional_data(header)
            with open(temporary, 'xb') as out, open(archive, 'rb') as source:
                restrict_file(temporary)
                out.write(header)
                for chunk in iter(lambda: source.read(1024*1024), b''):
                    out.write(encryptor.update(chunk))
                out.write(encryptor.finalize())
                out.write(encryptor.tag)
            # Publish without replacing a file created by another backup/operator.
            # Hard links are atomic on local disks; the exclusive-copy fallback
            # also supports backup destinations on shares without hard-link support.
            try:
                os.link(temporary, destination)
            except FileExistsError:
                raise ValueError('A backup already exists at that filename.') from None
            except OSError:
                owned = False
                try:
                    with open(destination, 'xb') as out, open(temporary, 'rb') as source:
                        owned = True
                        restrict_file(destination)
                        shutil.copyfileobj(source, out, 1024 * 1024)
                except Exception:
                    if owned:
                        destination.unlink(missing_ok=True)
                    raise
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def restore(archive, destination, password):
    """Authenticate the complete archive before extracting; target must be empty."""
    archive, destination = Path(archive), Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Restore into a new, empty folder. Existing library data is never overwritten.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='legal-restore-', dir=destination.parent) as temp:
        temp = Path(temp)
        decrypted = temp / 'archive.zip'
        with open(archive, 'rb') as source:
            header = source.read(len(MAGIC)+28)
            if len(header) != len(MAGIC)+28 or not header.startswith(MAGIC):
                raise ValueError('This is not a Legal Library backup.')
            salt, nonce = header[len(MAGIC):len(MAGIC)+16], header[-12:]
            source.seek(-16, 2)
            tag = source.read(16)
            remaining = source.tell() - len(header) - 16
            source.seek(len(header))
            decryptor = Cipher(algorithms.AES(_key(password, salt)), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            try:
                with open(decrypted, 'wb') as out:
                    restrict_file(decrypted)
                    while remaining:
                        chunk = source.read(min(1024*1024, remaining))
                        if not chunk:
                            raise ValueError('The backup is incomplete.')
                        remaining -= len(chunk)
                        out.write(decryptor.update(chunk))
                    out.write(decryptor.finalize())
            except Exception as exc:
                raise ValueError('Cannot unlock backup. Check the passphrase and that the file is intact.') from exc
        staged = temp / 'data'
        staged.mkdir()
        with zipfile.ZipFile(decrypted) as z:
            entries = z.infolist()
            if len(entries) > 100000 or sum(i.file_size for i in entries) > 20*1024**3:
                raise ValueError('Backup exceeds the restore size limit.')
            names = set()
            for info in entries:
                path = Path(info.filename.replace('\\', '/'))
                if path.is_absolute() or '..' in path.parts or ':' in info.filename or info.filename in names or not (info.filename.startswith('files/') or info.filename in ('db/legal_platform.db','manifest.json','provider_config.json','.configured','.local-mode')):
                    raise ValueError('Backup contains an invalid entry.')
                names.add(info.filename)
            if 'db/legal_platform.db' not in names:
                raise ValueError('Backup is missing its database.')
            z.extractall(staged)
        with contextlib.closing(sqlite3.connect(staged / 'db/legal_platform.db')) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup database failed its integrity check.')
        if destination.exists():
            destination.rmdir()  # Already verified empty; never recursively delete a target.
        staged.rename(destination)
        if (destination / 'provider_config.json').exists():
            restrict_file(destination / 'provider_config.json')
    return destination
