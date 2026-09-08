"""Host settings and a stoppable process entrypoint shared by desktop and service."""
from __future__ import annotations
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import threading
from datetime import datetime, timedelta, timezone


def addresses():
    values = {'127.0.0.1'}
    try:
        values.update(row[4][0] for row in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    return sorted(values)


def load_settings(root):
    path = Path(root) / 'server.json'
    data = json.loads(path.read_text()) if path.exists() else {}
    return {'host': data.get('host', '0.0.0.0'), 'port': int(data.get('port', 8443)), 'https': bool(data.get('https', True))}


def save_settings(root, settings):
    if not 1024 <= int(settings['port']) <= 65535:
        raise ValueError('Choose a port between 1024 and 65535.')
    path = Path(root) / 'server.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2))


def ensure_certificate(root):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from ipaddress import ip_address
    from legal_platform.operations import restrict_file
    directory = Path(root) / 'tls'
    directory.mkdir(parents=True, exist_ok=True)
    cert, key = directory / 'server.crt', directory / 'server.key'
    if cert.exists() and key.exists():
        return cert, key
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Legal Library ' + socket.gethostname())])
    sans = [x509.DNSName('localhost'), x509.DNSName(socket.gethostname())] + [x509.IPAddress(ip_address(a)) for a in addresses()]
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(private.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).sign(private, hashes.SHA256()))
    key.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    restrict_file(key)
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert, key


def run_server(root, stop_event=None):
    from legal_platform.operations import installation_lock
    root = Path(root).resolve()
    os.environ['LEGAL_PLATFORM_DATA_DIR'] = str(root)
    root.mkdir(parents=True, exist_ok=True)
    with installation_lock(root):
        (root / 'logs').mkdir(exist_ok=True)
        handler = RotatingFileHandler(root / 'logs/server.log', maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        settings = load_settings(root)
        if settings['https']:
            cert, key = ensure_certificate(root)
            os.environ['LEGAL_PLATFORM_TLS_CERT'], os.environ['LEGAL_PLATFORM_TLS_KEY'] = str(cert), str(key)
        else:
            os.environ.pop('LEGAL_PLATFORM_TLS_CERT', None)
            os.environ.pop('LEGAL_PLATFORM_TLS_KEY', None)
        from legal_platform.api.server import PlatformAPI
        api = PlatformAPI(host=settings['host'], port=settings['port'])
        request_stop = root / '.stop-request'
        request_stop.unlink(missing_ok=True)
        finished = threading.Event()
        def watch():
            while not finished.wait(.4):
                if request_stop.exists() or (stop_event and stop_event.is_set()):
                    # Wait until server startup completes before stopping its worker pool.
                    server = getattr(api, '_server', None)
                    if server and getattr(server, 'ready', False):
                        request_stop.unlink(missing_ok=True)
                        api.stop()
                        return
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            api.start()
        finally:
            finished.set()
            api.stop()
            logging.getLogger().removeHandler(handler)
            handler.close()
