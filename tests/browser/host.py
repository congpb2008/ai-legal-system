"""Isolated synthetic catalog for browser regression tests; never use real data."""
import json
import os
from pathlib import Path
import socket
import sys
import threading

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
if any(root.iterdir()):
    raise SystemExit('Browser fixture requires an empty data directory.')
os.environ['LEGAL_PLATFORM_DATA_DIR'] = str(root)
(root / '.local-mode').write_text('Synthetic browser test')

from legal_platform.api.server import PlatformAPI
from legal_platform.api.handlers import DocumentHandler
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.vault.models import VaultType

with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
app = PlatformAPI(host='127.0.0.1', port=port)
password = 'Synthetic browser test passphrase 123'
result = app._auth.register(dict(username='admin', password=password,
    code=(root / 'setup-code.txt').read_text()), bootstrap=True)
assert result.success
admin = result.data['account']['id']
members = {}
for name in ('reader', 'editor'):
    code = app._auth.issue_code('invite').data['code']
    result = app._auth.register(dict(username=name, password=password, code=code))
    assert result.success
    members[name] = result.data['account']['id']
vault = app._vault.create_vault(name='Procurement policies', vault_type=VaultType.DEPARTMENT, owner=admin)
other = app._vault.create_vault(name='Other policies', vault_type=VaultType.DEPARTMENT, owner=admin)
app._vault.add_member(vault.id, members['reader'], role='VIEWER')
app._vault.add_member(vault.id, members['editor'], role='CONTRIBUTOR')
handler = DocumentHandler(registry=app._registry, vault_service=app._vault, vector_index=app._vector_index)
for index in range(106):
    result = handler.create_document(dict(title='Đấu thầu 100%_policy' if index == 0 else f'Sample policy {index}',
        document_type='INTERNAL_REGULATION', issuing_authority='Synthetic fixture',
        vault_id=str(vault.id if index == 0 else other.id)), admin)
    assert result.success
    from uuid import UUID
    did = UUID(result.data['id'])
    if index == 0:
        target = str(did)
    # These are catalog fixtures, without fabricated source files or ingestion jobs.
    state = ProcessingState.FAILED if index == 104 else ProcessingState.READY
    app._registry.repo.set_processing(did, state)
for index in range(101):
    app._vault.create_vault(name=f'Reference collection {index}', vault_type=VaultType.DEPARTMENT, owner=admin)
from provider_fixture import start_provider
provider=start_provider()
(root / 'fixture.json').write_text(json.dumps(dict(port=port, vault=str(vault.id), target=target,
    provider=f'http://192.168.50.40:{provider.server_port}/v1')), encoding='utf-8')

def stop_when_requested():
    for _ in range(180):
        if (root / 'stop').exists():
            break
        threading.Event().wait(1)
    app.stop()

threading.Thread(target=stop_when_requested, daemon=True).start()
try:
    app.start()
finally:
    app.stop()
    provider.shutdown();provider.server_close()
