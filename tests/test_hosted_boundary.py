"""HTTPS origin and proxy attribution without trusting browser-supplied headers."""
import io
import json

import pytest

from legal_platform.api.server import PlatformAPI, create_app
from legal_platform.api.handlers import HealthHandler
from legal_platform.web import WebApplication


def make_web(api):
    return WebApplication(create_app(auth_handler=api._auth, health_handler=HealthHandler()), api)


def call(web, path, method='GET', body=None, **headers):
    raw = json.dumps(body).encode() if body is not None else b''
    env = {'PATH_INFO': path, 'REQUEST_METHOD': method, 'wsgi.url_scheme': 'http',
           'HTTP_HOST': 'library.example.test', 'REMOTE_ADDR': '192.0.2.10',
           'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(raw)),
           'wsgi.input': io.BytesIO(raw), **headers}
    result = {}
    def start(status, response_headers):
        result.update(status=int(status.split()[0]), headers=dict(response_headers))
    result['body'] = b''.join(web(env, start))
    return result


def test_hosted_https_cookie_csrf_and_canonical_host(monkeypatch, isolated_application_data):
    monkeypatch.setenv('LEGAL_PLATFORM_PUBLIC_ORIGIN', 'https://library.example.test')
    api = PlatformAPI(host='127.0.0.1', port=18099)
    try:
        web = make_web(api)
        password = 'Synthetic hosted passphrase 123'
        result = call(web, '/api/v1/auth/bootstrap', 'POST', {'username': 'owner', 'password': password,
                      'code': (isolated_application_data / 'setup-code.txt').read_text()},
                      HTTP_ORIGIN='https://library.example.test')
        assert result['status'] == 201, result
        login = call(web, '/api/v1/auth/login', 'POST', {'username': 'owner', 'password': password},
                     HTTP_ORIGIN='https://library.example.test')
        assert login['status'] == 200, login
        cookie = login['headers']['Set-Cookie']
        assert '; Secure' in cookie and 'HttpOnly' in cookie
        assert call(web, '/api/v1/auth/logout', 'POST', {}, HTTP_COOKIE=cookie,
                    HTTP_X_REQUESTED_WITH='LegalPlatform', HTTP_ORIGIN='https://attacker.example')['status'] == 403
        assert call(web, '/', HTTP_HOST='attacker.example')['status'] == 421
        assert call(web, '/health', HTTP_HOST='localhost:8080')['status'] == 200
        assert call(web, '/api/v1/auth/logout', 'POST', {}, HTTP_COOKIE=cookie,
                    HTTP_X_REQUESTED_WITH='LegalPlatform', HTTP_ORIGIN='https://library.example.test')['status'] == 200
    finally:
        api.stop()


def test_forwarded_addresses_only_count_for_configured_proxy(monkeypatch):
    monkeypatch.setenv('LEGAL_PLATFORM_TRUSTED_PROXIES', '192.0.2.10/32')
    api = PlatformAPI(host='127.0.0.1', port=18099)
    try:
        web = make_web(api)
        call(web, '/api/v1/setup/status', HTTP_X_FORWARDED_FOR='198.51.100.5')
        call(web, '/api/v1/setup/status', REMOTE_ADDR='192.0.2.11', HTTP_X_FORWARDED_FOR='198.51.100.6')
        call(web, '/api/v1/setup/status', HTTP_X_FORWARDED_FOR='198.51.100.5, 198.51.100.7')
        assert ('ip', '198.51.100.5') in web._rates
        assert ('ip', '192.0.2.11') in web._rates
        assert ('ip', '198.51.100.6') not in web._rates
        assert ('ip', '192.0.2.10') in web._rates
    finally:
        api.stop()


@pytest.mark.parametrize('origin', ['http://library.example.test', 'https://user:secret@library.example.test', 'https://library.example.test/path'])
def test_invalid_public_origin_fails_startup(monkeypatch, origin):
    monkeypatch.setenv('LEGAL_PLATFORM_PUBLIC_ORIGIN', origin)
    api = PlatformAPI(host='127.0.0.1', port=18099)
    try:
        with pytest.raises(ValueError, match='HTTPS origin'):
            make_web(api)
    finally:
        api.stop()
