"""Optional real Caddy/HTTPS journey, with loopback-only processes and cleanup.

Set LEGAL_PLATFORM_TEST_CADDY to a verified Caddy binary to include this test.
No Docker daemon, public domain, ACME request or system service is used.
"""
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import threading
import time
import urllib.request

import pytest

from legal_platform.api.server import PlatformAPI
from legal_platform.host import ensure_certificate
from test_user_journeys import word_file


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.mark.skipif(not os.environ.get('LEGAL_PLATFORM_TEST_CADDY'), reason='Set LEGAL_PLATFORM_TEST_CADDY for the optional real proxy journey')
def test_real_https_proxy_account_upload_answer(monkeypatch, isolated_application_data):
    root = isolated_application_data
    root.mkdir(parents=True)
    backend_port, proxy_port = available_port(), available_port()
    origin = f'https://localhost:{proxy_port}'
    monkeypatch.setenv('LEGAL_PLATFORM_PUBLIC_ORIGIN', origin)
    monkeypatch.setenv('LEGAL_PLATFORM_TRUSTED_PROXIES', '127.0.0.1/32')
    cert, key = ensure_certificate(root)
    config = root / 'Caddyfile'
    config.write_text(f'''{{
    admin off
    auto_https off
}}
{origin} {{
    bind 127.0.0.1
    tls "{cert.as_posix()}" "{key.as_posix()}"
    reverse_proxy 127.0.0.1:{backend_port} {{
        header_up X-Forwarded-For {{remote_host}}
    }}
}}
''', encoding='utf-8')
    api = PlatformAPI(host='127.0.0.1', port=backend_port)
    backend = threading.Thread(target=api.start, daemon=True)
    backend.start()
    env = {**os.environ, 'XDG_DATA_HOME': str(root), 'XDG_CONFIG_HOME': str(root)}
    process = None
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies),
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=str(cert))))

    def request(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(origin + '/api' + path, method=method, data=data,
            headers={'Content-Type': 'application/json', 'Origin': origin, 'X-Requested-With': 'LegalPlatform'})
        with client.open(req, timeout=10) as response:
            payload = json.loads(response.read())
        assert payload['success'], payload
        return payload['data']

    with open(root / 'proxy.log', 'wb') as log:
        try:
            process = subprocess.Popen([str(Path(os.environ['LEGAL_PLATFORM_TEST_CADDY']).resolve()),
                'run', '--config', str(config), '--adapter', 'caddyfile'], env=env,
                stdout=log, stderr=log, creationflags=0x08000000 if os.name == 'nt' else 0)
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                try:
                    if request('GET', '/health')['status'] == 'alive':
                        break
                except OSError:
                    time.sleep(.1)
            else:
                pytest.fail('Proxy did not become ready: ' + (root / 'proxy.log').read_text(errors='replace'))
            password = 'Disposable proxy test passphrase 123'
            request('POST', '/v1/auth/bootstrap', {'username': 'owner', 'password': password,
                    'code': (root / 'setup-code.txt').read_text()})
            request('POST', '/v1/auth/login', {'username': 'owner', 'password': password})
            assert list(cookies) and all(cookie.secure for cookie in cookies)
            collection = request('POST', '/v1/vaults', {'name': 'Test policies', 'vault_type': 'DEPARTMENT'})
            original = word_file('QUY CHẾ MUA SẮM\nĐiều 1. Hồ sơ mua sắm\nHồ sơ mua sắm máy chủ phải có đề nghị, dự toán và phê duyệt của giám đốc.')
            uploaded = request('POST', '/v1/uploads', {'vault_id': collection['id'], 'title': 'Quy chế mua sắm',
                'document_type': 'INTERNAL_REGULATION', 'issuing_authority': 'Synthetic organization',
                'filename': 'policy.docx', 'content_base64': base64.b64encode(original).decode()})
            did = uploaded['document_id']
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                document = request('GET', '/v1/documents/' + did)
                if document['processing_state'] == 'READY':
                    break
                assert document['processing_state'] != 'FAILED', document
                time.sleep(.1)
            assert document['processing_state'] == 'READY', document
            answer = request('POST', '/v1/answers', {'query': 'Hồ sơ mua sắm máy chủ cần gì?', 'vault_id': collection['id']})
            assert answer['citations'] and 'dự toán' in answer['response']['content']
            source = request('GET', '/v1/documents/' + did + '/source?include_original=true')
            assert base64.b64decode(source['content_base64']) == original
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            api.stop()
            backend.join(timeout=10)
