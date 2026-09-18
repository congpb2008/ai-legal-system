"""Local organization accounts, hashed credentials, revocable sessions and invitations.

An installation belongs to one organization. New accounts require approval or a
single-use invitation. Existing document-owner strings never establish identity.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from uuid import uuid4
from legal_platform.api.models import ApiResponse, ApiError, ErrorCategory
from legal_platform.storage.db import in_memory


SCHEMA = '''
CREATE TABLE IF NOT EXISTS account (
 id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
 email TEXT NOT NULL DEFAULT '', password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'member', state TEXT NOT NULL DEFAULT 'pending',
 created_at REAL NOT NULL, password_changed_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS account_session (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES account(id),
 created_at REAL NOT NULL, expires_at REAL NOT NULL, label TEXT NOT NULL DEFAULT 'Browser');
CREATE TABLE IF NOT EXISTS account_code (
 code_hash TEXT PRIMARY KEY, purpose TEXT NOT NULL, user_id TEXT, email TEXT,
 expires_at REAL NOT NULL, used_at REAL);
CREATE TABLE IF NOT EXISTS account_setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_throttle (key TEXT PRIMARY KEY, attempts INTEGER, reset_at REAL);
'''


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 256:
        raise ValueError('Use a password with 12–256 characters.')
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(value.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return 'scrypt$16384$' + salt.hex() + '$' + key.hex()


def password_matches(value, stored):
    try:
        algorithm, n, salt, expected = stored.split('$')
        if algorithm != 'scrypt' or n != '16384' or not isinstance(value, str) or len(value) > 256:
            return False
        actual = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


class AuthHandler:
    def __init__(self, conn=None, data_dir=None):
        self.conn = conn or in_memory()
        self.conn.executescript(SCHEMA)
        self.data_dir = Path(data_dir) if data_dir else None
        self._dummy_hash = password_hash(secrets.token_urlsafe(24))
        self.conn.execute("INSERT OR IGNORE INTO account_setting VALUES ('organization_id', ?)", (str(uuid4()),))
        self.conn.commit()
        if self.data_dir and self.needs_admin():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            code_path = self.data_dir / 'setup-code.txt'
            # Exclusive creation prevents concurrent startups from replacing the claim code.
            try:
                fd = os.open(code_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as handle:
                    handle.write(secrets.token_urlsafe(32))
            except FileExistsError:
                pass
            from legal_platform.operations import restrict_file
            restrict_file(code_path)
            self.bootstrap_hash = digest(code_path.read_text().strip())
        else:
            self.bootstrap_hash = None

    @property
    def organization_id(self):
        return self.conn.execute("SELECT value FROM account_setting WHERE key='organization_id'").fetchone()[0]

    def needs_admin(self):
        return self.conn.execute('SELECT COUNT(*) FROM account').fetchone()[0] == 0

    @staticmethod
    def error(message, status=400, code='INVALID_REQUEST'):
        category = {401: ErrorCategory.AUTHENTICATION, 403: ErrorCategory.AUTHORIZATION,
                    409: ErrorCategory.CONFLICT, 429: ErrorCategory.RATE_LIMITED}.get(status, ErrorCategory.VALIDATION)
        return ApiResponse.err_response(ApiError(code=code, message=message, category=category), status=status)

    @staticmethod
    def public(row):
        return {key: row[key] for key in ('id', 'username', 'display_name', 'email', 'role', 'state', 'created_at')}

    def account(self, user_id):
        return self.conn.execute('SELECT * FROM account WHERE id=?', (user_id,)).fetchone()

    def is_admin(self, user_id):
        row = self.account(user_id)
        return bool(row and row['state'] == 'active' and row['role'] == 'admin')

    def register(self, body, *, bootstrap=False):
        username = str(body.get('username') or body.get('user_id') or '').strip().lower()
        display = str(body.get('display_name') or username).strip()
        email = str(body.get('email') or '').strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9._@+-]{2,79}', username):
            return self.error('Username must have 3–80 letters, numbers, or . _ @ + - characters.')
        if not 1 <= len(display) <= 120 or len(email) > 254 or (email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
            return self.error('Enter a valid name and email address.')
        try:
            hashed = password_hash(body.get('password'))
        except ValueError as exc:
            return self.error(str(exc))
        code = str(body.get('code') or '').strip()
        uid = str(uuid4())
        now = time.time()
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            if bootstrap:
                if not self.needs_admin() or not self.bootstrap_hash or not hmac.compare_digest(digest(code), self.bootstrap_hash):
                    self.conn.rollback()
                    return self.error('The setup code is invalid or this server already has an administrator.', 403)
                role, state = 'admin', 'active'
            else:
                if self.needs_admin():
                    self.conn.rollback()
                    return self.error('The server owner needs to finish setup first.', 409)
                role, state = 'member', 'pending'
                if code:
                    invitation = self.conn.execute("SELECT * FROM account_code WHERE code_hash=? AND purpose='invite' AND used_at IS NULL AND expires_at>?", (digest(code), now)).fetchone()
                    if not invitation or (invitation['email'] and invitation['email'] != email):
                        self.conn.rollback()
                        return self.error('Invitation is invalid, expired, or belongs to another email address.')
                    self.conn.execute('UPDATE account_code SET used_at=? WHERE code_hash=?', (now, digest(code)))
                    state = 'active'
            self.conn.execute('INSERT INTO account VALUES (?,?,?,?,?,?,?,?,?)', (uid, username, display, email, hashed, role, state, now, now))
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return self.error('That username is already registered.', 409)
        except Exception:
            self.conn.rollback()
            raise
        if bootstrap and self.data_dir:
            (self.data_dir / 'setup-code.txt').unlink(missing_ok=True)
        return ApiResponse.ok(data={'account': self.public(self.account(uid)), 'requires_approval': state == 'pending'}, status=201)

    def login(self, body):
        username = str(body.get('user_id') or body.get('username') or '').strip().lower()
        password = body.get('password')
        if not username or not password:
            return self.error('Enter your username and password.')
        now = time.time()
        key = digest(username)
        attempt = self.conn.execute('SELECT * FROM login_throttle WHERE key=?', (key,)).fetchone()
        if attempt and attempt['reset_at'] > now and attempt['attempts'] >= 8:
            return self.error('Too many attempts. Please try again in 15 minutes.', 429)
        row = self.conn.execute('SELECT * FROM account WHERE username=?', (username,)).fetchone()
        matched = password_matches(password, row['password_hash'] if row else self._dummy_hash)
        if not row or not matched:
            self.conn.execute('''INSERT INTO login_throttle VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET
                attempts=CASE WHEN reset_at<? THEN 1 ELSE attempts+1 END,
                reset_at=CASE WHEN reset_at<? THEN excluded.reset_at ELSE reset_at END''', (key, now + 900, now, now))
            self.conn.commit()
            return self.error('Username or password is incorrect.', 401, 'INVALID_CREDENTIALS')
        if row['state'] != 'active':
            return self.error('Your account is awaiting approval or has been disabled. Contact your administrator.', 403)
        self.conn.execute('DELETE FROM login_throttle WHERE key=?', (key,))
        token = secrets.token_urlsafe(32)
        expires = now + 12 * 3600
        self.conn.execute('DELETE FROM account_session WHERE expires_at<?', (now,))
        self.conn.execute('INSERT INTO account_session VALUES (?,?,?,?,?)', (digest(token), row['id'], now, expires, 'Browser'))
        self.conn.commit()
        return ApiResponse.ok(data={'token': token, 'user_id': row['id'], 'account': self.public(row), 'expires_at': expires, 'token_type': 'Bearer'})

    def resolve_user(self, token):
        if not isinstance(token, str) or not token or len(token) > 200:
            return None
        row = self.conn.execute('''SELECT a.id FROM account_session s JOIN account a ON a.id=s.user_id
            WHERE s.token_hash=? AND s.expires_at>? AND a.state='active' ''', (digest(token), time.time())).fetchone()
        return row['id'] if row else None

    def me(self, token):
        uid = self.resolve_user(token)
        if not uid:
            return self.error('Please sign in.', 401, 'NOT_AUTHENTICATED')
        return ApiResponse.ok(data={'user_id': uid, 'account': self.public(self.account(uid)), 'organization_id': self.organization_id})

    def logout(self, token):
        if token:
            self.conn.execute('DELETE FROM account_session WHERE token_hash=?', (digest(token),))
            self.conn.commit()
        return ApiResponse.ok(data={'message': 'Signed out.'})

    def profile(self, uid, body):
        display = str(body.get('display_name', '')).strip()
        email = str(body.get('email', '')).strip().lower()
        if not 1 <= len(display) <= 120 or len(email) > 254 or (email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
            return self.error('Enter a valid name and email address.')
        self.conn.execute('UPDATE account SET display_name=?,email=? WHERE id=?', (display, email, uid))
        self.conn.commit()
        return ApiResponse.ok(data=self.public(self.account(uid)))

    def change_password(self, uid, body):
        row = self.account(uid)
        if not password_matches(body.get('current_password'), row['password_hash']):
            return self.error('Current password is incorrect.', 403)
        return self._set_password(uid, body.get('new_password'))

    def _set_password(self, uid, password):
        try:
            hashed = password_hash(password)
        except ValueError as exc:
            return self.error(str(exc))
        with self.conn:
            self.conn.execute('UPDATE account SET password_hash=?,password_changed_at=? WHERE id=?', (hashed, time.time(), uid))
            self.conn.execute('DELETE FROM account_session WHERE user_id=?', (uid,))
            self.conn.execute('DELETE FROM login_throttle WHERE key=?', (digest(self.account(uid)['username']),))
        return ApiResponse.ok(data={'message': 'Password updated. Sign in again on your devices.'})

    def reset_password(self, body):
        code = str(body.get('code') or '')
        try:
            hashed = password_hash(body.get('new_password'))
        except ValueError as exc:
            return self.error(str(exc))
        self.conn.execute('BEGIN IMMEDIATE')
        row = self.conn.execute("SELECT * FROM account_code WHERE code_hash=? AND purpose='reset' AND used_at IS NULL AND expires_at>?", (digest(code), time.time())).fetchone()
        if not row:
            self.conn.rollback()
            return self.error('Recovery code is invalid or expired.')
        self.conn.execute('UPDATE account SET password_hash=?,password_changed_at=? WHERE id=?', (hashed, time.time(), row['user_id']))
        self.conn.execute('DELETE FROM account_session WHERE user_id=?', (row['user_id'],))
        self.conn.execute('UPDATE account_code SET used_at=? WHERE code_hash=?', (time.time(), digest(code)))
        self.conn.execute('DELETE FROM login_throttle WHERE key=?', (digest(self.account(row['user_id'])['username']),))
        self.conn.commit()
        return ApiResponse.ok(data={'message': 'Password reset. You can sign in now.'})

    def sessions(self, uid, token):
        rows = self.conn.execute('SELECT token_hash,created_at,expires_at,label FROM account_session WHERE user_id=? AND expires_at>? ORDER BY created_at DESC', (uid, time.time()))
        return ApiResponse.ok(data=[{'id': r['token_hash'], 'created_at': r['created_at'], 'expires_at': r['expires_at'], 'current': r['token_hash'] == digest(token), 'label': r['label']} for r in rows])

    def revoke(self, uid, session_id):
        self.conn.execute('DELETE FROM account_session WHERE user_id=? AND token_hash=?', (uid, session_id))
        self.conn.commit()
        return ApiResponse.ok(data={'message': 'Session signed out.'})

    def list_accounts(self):
        return ApiResponse.ok(data=[self.public(r) for r in self.conn.execute('SELECT * FROM account ORDER BY created_at DESC')])

    def update_account(self, actor, target, body):
        row = self.account(target)
        if not row:
            return self.error('Account not found.', 404)
        state = body.get('state', row['state'])
        role = body.get('role', row['role'])
        if state not in ('pending', 'active', 'disabled') or role not in ('admin', 'member'):
            return self.error('Invalid account status or role.')
        self.conn.execute('BEGIN IMMEDIATE')
        admins = self.conn.execute("SELECT COUNT(*) FROM account WHERE role='admin' AND state='active'").fetchone()[0]
        if row['role'] == 'admin' and row['state'] == 'active' and admins <= 1 and (state != 'active' or role != 'admin'):
            self.conn.rollback()
            return self.error('Keep at least one active administrator.', 409)
        self.conn.execute('UPDATE account SET state=?,role=? WHERE id=?', (state, role, target))
        self.conn.execute('DELETE FROM account_session WHERE user_id=?', (target,))
        self.conn.commit()
        return ApiResponse.ok(data=self.public(self.account(target)))

    def issue_code(self, purpose, *, uid=None, email=''):
        if purpose == 'reset' and (not uid or not self.account(uid)):
            return self.error('Account not found.', 404)
        code = secrets.token_urlsafe(24)
        expiry = time.time() + (3600 if purpose == 'reset' else 7 * 86400)
        with self.conn:
            if purpose == 'reset':
                self.conn.execute("DELETE FROM account_code WHERE user_id=? AND purpose='reset'", (uid,))
            self.conn.execute('INSERT INTO account_code VALUES (?,?,?,?,?,NULL)', (digest(code), purpose, uid, email.strip().lower(), expiry))
        return ApiResponse.ok(data={'code': code, 'expires_at': expiry, 'purpose': purpose})
