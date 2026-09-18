from pathlib import Path
import sys
import importlib.util

root = Path(SPECPATH).parent
extra_binaries = []

spec = importlib.util.find_spec('pymupdf')
if spec and spec.submodule_search_locations:
    pymupdf_path = Path(spec.submodule_search_locations[0])
    crt = pymupdf_path / 'msvcp140.dll'
    if crt.exists():
        extra_binaries.append((str(crt), '.'))
a = Analysis([str(root / 'packaging/windows_entry.py')], pathex=[str(root/'backend')],
    binaries=extra_binaries,
    datas=[(str(root/'frontend'), 'frontend'), (str(root/'design'), 'design')],
    hiddenimports=['win32timezone', 'win32serviceutil', 'win32service', 'win32event', 'servicemanager', 'win32security', 'win32api', 'ntsecuritycon', 'cheroot.ssl.builtin'],
    excludes=['pytest','matplotlib','numpy','scipy','pandas'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='LegalLibrary', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LegalLibrary')
