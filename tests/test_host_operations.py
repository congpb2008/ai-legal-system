"""Operator recovery and cross-process control, using disposable local libraries."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from legal_platform.api.server import PlatformAPI
from legal_platform.operations import installation_lock, installation_in_use, recover_administrator
from legal_platform.host import running_host, save_settings, stop_host
from legal_platform.storage.db import connect_thread_local
from legal_platform.accounts import AuthHandler, password_matches


OLD_PASSWORD = 'Original synthetic passphrase 123'
NEW_PASSWORD = 'Recovered synthetic passphrase 456'


def test_offline_recovery_preserves_identity_and_revokes_credentials(isolated_application_data):
    root = isolated_application_data
    api = PlatformAPI(host='127.0.0.1', port=18099)
    auth = api._auth
    result = auth.register({'username': 'owner', 'password': OLD_PASSWORD,
                            'code': (root / 'setup-code.txt').read_text()}, bootstrap=True)
    uid = result.data['account']['id']
    token = auth.login({'username': 'owner', 'password': OLD_PASSWORD}).data['token']
    auth.issue_code('reset', uid=uid)
    organization = auth.organization_id
    api.stop()

    with installation_lock(root), pytest.raises(RuntimeError, match='in use'):
        recover_administrator(root, 'owner', NEW_PASSWORD)
    assert recover_administrator(root, ' OWNER ', NEW_PASSWORD) == 'owner'
    conn = connect_thread_local(root / 'db/legal_platform.db')
    try:
        recovered = AuthHandler(conn, root)
        assert recovered.organization_id == organization
        row = recovered.account(uid)
        assert row['role'] == 'admin' and row['state'] == 'active'
        assert password_matches(NEW_PASSWORD, row['password_hash'])
        assert not password_matches(OLD_PASSWORD, row['password_hash'])
        assert recovered.resolve_user(token) is None
        assert conn.execute('SELECT COUNT(*) FROM account_code WHERE user_id=?', (uid,)).fetchone()[0] == 0
        audit = conn.execute("SELECT * FROM audit_log WHERE event='ADMINISTRATOR_RECOVERED'").fetchone()
        assert audit['entity_id'] == uid
        assert NEW_PASSWORD not in json.dumps(dict(audit))
        assert recovered.login({'username': 'owner', 'password': NEW_PASSWORD}).status == 200
    finally:
        conn.close()


def test_recovery_cannot_create_or_promote_accounts(isolated_application_data):
    root = isolated_application_data
    api = PlatformAPI(host='127.0.0.1', port=18099)
    auth = api._auth
    auth.register({'username': 'owner', 'password': OLD_PASSWORD,
                   'code': (root / 'setup-code.txt').read_text()}, bootstrap=True)
    member = auth.register({'username': 'member', 'password': OLD_PASSWORD}).data['account']['id']
    api.stop()
    for username in ('missing', 'member'):
        with pytest.raises(ValueError, match='existing active administrator'):
            recover_administrator(root, username, NEW_PASSWORD)
    with pytest.raises(ValueError, match='12–256'):
        recover_administrator(root, 'owner', 'short')
    conn = connect_thread_local(root / 'db/legal_platform.db')
    try:
        row = conn.execute('SELECT * FROM account WHERE id=?', (member,)).fetchone()
        assert row['role'] == 'member' and row['state'] == 'pending'
        assert password_matches(OLD_PASSWORD, row['password_hash'])
        assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE event='ADMINISTRATOR_RECOVERED'").fetchone()[0] == 0
    finally:
        conn.close()


def test_reopened_controller_stops_host_and_ignores_stale_status(isolated_application_data):
    root = isolated_application_data
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    save_settings(root, {'host': '127.0.0.1', 'port': port, 'https': False})
    assert not installation_in_use(root)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'backend')
    command = [sys.executable, '-m', 'legal_platform.desktop', '--serve', '--data-dir', str(root)]
    process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               creationflags=0x08000000 if os.name == 'nt' else 0)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(process.stderr.read().decode(errors='replace'))
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.1)
        else:
            pytest.fail('Host did not start in time')
        # This controller has no child-process handle from the original launcher.
        status = running_host(root)
        assert status['port'] == port and not status['https']
        assert installation_in_use(root)
        stop_host(root)
        assert process.wait(timeout=15) == 0
        assert running_host(root) is None
        assert not (root / 'running-host.json').exists()
        (root / 'running-host.json').write_text(json.dumps(status))
        assert running_host(root) is None
        with pytest.raises(ValueError, match='No launcher-controlled'):
            stop_host(root)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        process.stderr.close()
