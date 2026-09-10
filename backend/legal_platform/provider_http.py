"""Direct, bounded provider connections with explicit LAN scope and pinned DNS.

Provider URLs are administrator settings. Redirects and ambient HTTP proxies are
not followed, so a configured destination cannot forward credentials elsewhere.
"""
from contextlib import contextmanager
import http.client
from ipaddress import ip_address, ip_network
import socket
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit

_LAN = tuple(map(ip_network, ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7')))
_LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _address_allowed(address, host, allow_lan):
    address = ip_address(address)
    address = getattr(address, 'ipv4_mapped', None) or address
    if address.is_loopback:
        return host in _LOCAL_HOSTS
    if address.is_link_local or address.is_unspecified or address.is_multicast or address.is_reserved:
        return False
    if any(address in network for network in _LAN):
        return allow_lan is True
    return address.is_global


def resolve_provider_url(url, *, allow_lan=False):
    if not isinstance(url, str) or not url or any(ord(c) < 33 for c in url) or '\\' in url:
        raise ValueError('Enter a valid provider URL without spaces or control characters.')
    try:
        parsed = urlsplit(url)
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError('Provider URL has an invalid host or port.') from exc
    if parsed.scheme not in ('http', 'https') or not host or not 1 <= port <= 65535:
        raise ValueError('Provider URL must include an http or https host and valid port.')
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or '%' in host:
        raise ValueError('Provider URL must not contain credentials, a query, fragment or scoped address.')
    host = host.lower()
    try:
        ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
        except OSError as exc:
            raise ValueError('Provider hostname could not be resolved from this server. Check its address or use its LAN IP.') from exc
    if not addresses or any(not _address_allowed(address, host, allow_lan) for address in addresses):
        raise ValueError('Provider address is not allowed. For a private network server, enable LAN access. Link-local, metadata and reserved addresses remain blocked.')
    return parsed, port, addresses


def validate_provider_url(url, *, allow_lan=False):
    try:
        resolve_provider_url(url, allow_lan=allow_lan)
        return True, ''
    except ValueError as exc:
        return False, str(exc)


class _BoundedResponse:
    def __init__(self, response):
        self.response = response

    def read(self):
        data = self.response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise URLError('Provider response exceeds the size limit.')
        return data


@contextmanager
def provider_urlopen(request, timeout, *, allow_lan=False):
    try:
        parsed, port, addresses = resolve_provider_url(request.full_url, allow_lan=allow_lan)
    except ValueError as exc:
        raise URLError(str(exc)) from exc
    connection_type = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
    if any('\r' in value or '\n' in value for _, value in request.header_items()):
        raise URLError('Provider headers are invalid. Check the configured API key.')
    connection = connection_type(parsed.hostname, port, timeout=timeout)
    # Keep the original Host/SNI/certificate name, but connect only to an address
    # from this validation pass. No second DNS resolution or global monkeypatch.
    def connect_pinned(_address, timeout=timeout, source_address=None, **_kwargs):
        last_error = None
        for address in addresses:
            try:
                return socket.create_connection((address, port), timeout, source_address)
            except OSError as exc:
                last_error = exc
        raise last_error or OSError('Provider has no reachable address.')
    connection._create_connection = connect_pinned
    try:
        connection.request(request.get_method(), parsed.path or '/', body=request.data, headers=dict(request.header_items()))
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise URLError('Provider redirects are not followed. Enter the final provider address.')
        if response.status >= 400:
            raise HTTPError(request.full_url, response.status, f'Provider returned HTTP {response.status}', response.headers, None)
        yield _BoundedResponse(response)
    except (OSError, http.client.HTTPException) as exc:
        if isinstance(exc, URLError):
            raise
        raise URLError('Could not connect to the configured provider. Check its address, listening port, firewall and certificate.') from exc
    finally:
        connection.close()
