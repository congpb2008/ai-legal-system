"""Stage a private Windows OCR runtime; never execute the system installer.

Requires full 7-Zip (7z.exe, not 7za). Downloads are pinned and hash checked.
Run before PyInstaller. Nothing is downloaded on an end user's machine.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    'setup.exe': ('https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe', 'c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9'),
    'vie.traineddata': ('https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/vie.traineddata', '79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1'),
    'eng.traineddata': ('https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/eng.traineddata', '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2'),
}


def prepare(seven_zip):
    target = ROOT / 'ocr'
    if target.exists():
        raise SystemExit(f'{target} already exists; use a fresh checkout to rebuild OCR.')
    with tempfile.TemporaryDirectory(prefix='legal-ocr-') as temporary:
        stage = Path(temporary)
        for name, (url, expected) in ASSETS.items():
            with urllib.request.urlopen(url, timeout=120) as response:
                payload = response.read()
            if hashlib.sha256(payload).hexdigest() != expected:
                raise RuntimeError(f'Checksum mismatch: {name}')
            (stage / name).write_bytes(payload)
        extracted = stage / 'extracted'
        subprocess.run([seven_zip, 'x', str(stage/'setup.exe'), f'-o{extracted}', '-y'], check=True, capture_output=True)
        private = stage / 'ocr'
        private.mkdir()
        for source in [extracted/'tesseract.exe', *extracted.glob('*.dll')]:
            shutil.copy2(source, private/source.name)
        shutil.copytree(extracted/'doc', private/'doc')
        (private/'tessdata').mkdir()
        for language in ('vie', 'eng'):
            shutil.copy2(stage/f'{language}.traineddata', private/'tessdata')
        result = subprocess.run([str(private/'tesseract.exe'), '--tessdata-dir', str(private/'tessdata'), '--list-langs'], check=True, capture_output=True, text=True)
        if not {'vie', 'eng'} <= set(result.stdout.splitlines()):
            raise RuntimeError('Vietnamese/English runtime validation failed')
        (private/'SOURCES.txt').write_text('\n'.join(f'{name}\n{url}\nSHA256 {digest}\n' for name, (url, digest) in ASSETS.items()), encoding='utf-8')
        shutil.copytree(private, target)
    print(f'Bundled Vietnamese and English OCR: {target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seven-zip', default=shutil.which('7z'))
    args = parser.parse_args()
    if not args.seven_zip:
        parser.error('Install full 7-Zip on the build machine or pass --seven-zip')
    prepare(args.seven_zip)
