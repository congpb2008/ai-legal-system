"""Separate immutable application assets from writable installation data."""
from pathlib import Path
import os
import sys


def asset_root():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / 'frontend/index.html').exists():
        return checkout
    import sysconfig
    return Path(sysconfig.get_path('data')) / 'share/legal-platform'


def data_root():
    configured = os.environ.get('LEGAL_PLATFORM_DATA_DIR')
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'LegalPlatform' / 'data'
    return Path.home() / '.local' / 'share' / 'legal-platform'
