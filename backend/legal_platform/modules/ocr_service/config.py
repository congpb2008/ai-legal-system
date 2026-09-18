"""Independent OCR settings: enabling vision does not enable AI answers."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile

from legal_platform.paths import data_root, asset_root
from legal_platform.provider_http import validate_provider_url


@dataclass
class OcrConfig:
    mode: str = 'tesseract'
    base_url: str = 'http://localhost:11434/v1'
    model: str = ''
    api_key: str = ''
    allow_lan: bool = False
    timeout_seconds: int = 120
    max_tokens: int = 8192
    max_vision_pages: int = 50

    def safe_dict(self):
        result = asdict(self)
        result['has_api_key'] = bool(result.pop('api_key'))
        return result


def load_ocr_config():
    path = data_root() / 'ocr_config.json'
    if not path.exists():
        return OcrConfig()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        config = OcrConfig(**data)
        if any(not isinstance(getattr(config, key), str) for key in ('mode', 'base_url', 'model', 'api_key')):
            raise ValueError('Invalid OCR text settings.')
        if any(type(getattr(config, key)) is not int for key in ('timeout_seconds', 'max_tokens', 'max_vision_pages')):
            raise ValueError('Invalid OCR limits.')
        if config.mode not in ('tesseract', 'vision', 'tesseract_then_vision') or not isinstance(config.allow_lan, bool):
            raise ValueError('Invalid OCR mode or network scope.')
        if not 5 <= config.timeout_seconds <= 300 or not 512 <= config.max_tokens <= 32768 or not 1 <= config.max_vision_pages <= 200:
            raise ValueError('Invalid OCR limits.')
        return config
    except (ValueError, TypeError) as exc:
        raise ValueError('OCR settings could not be read. Ask the administrator to repair ocr_config.json.') from exc


def merge_ocr_config(current, body):
    config = OcrConfig(**asdict(current))
    if 'base_url' in body:
        address = str(body['base_url']).strip().rstrip('/')
        if address != config.base_url.rstrip('/'):
            config.api_key = ''
        config.base_url = address
    for key in ('mode', 'model', 'api_key'):
        if key in body:
            setattr(config, key, str(body[key] or '').strip())
    if 'allow_lan' in body:
        if not isinstance(body['allow_lan'], bool):
            raise ValueError('LAN access must be enabled or disabled.')
        config.allow_lan = body['allow_lan']
    for key in ('timeout_seconds', 'max_tokens', 'max_vision_pages'):
        if key in body:
            try:
                if isinstance(body[key], (bool, float)):
                    raise ValueError('A whole number is required.')
                value = int(body[key])
            except (ValueError, TypeError) as exc:
                raise ValueError('Enter whole numbers for OCR limits.') from exc
            setattr(config, key, value)
    if config.mode not in ('tesseract', 'vision', 'tesseract_then_vision'):
        raise ValueError('Choose Tesseract, vision OCR, or Tesseract with vision fallback.')
    if not 5 <= config.timeout_seconds <= 300 or not 512 <= config.max_tokens <= 32768 or not 1 <= config.max_vision_pages <= 200:
        raise ValueError('OCR limits must be 5–300 seconds, 512–32768 output tokens and 1–200 scanned pages.')
    if config.mode != 'tesseract':
        valid, reason = validate_provider_url(config.base_url, allow_lan=config.allow_lan)
        if not valid:
            raise ValueError(reason)
        if not config.model or len(config.model) > 200:
            raise ValueError('Enter the name of an installed vision model.')
    return config


def save_ocr_config(config):
    from legal_platform.operations import restrict_file
    root = data_root();root.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.ocr-config-', dir=root)
    try:
        os.close(descriptor)
        path = Path(name)
        restrict_file(path)
        path.write_text(json.dumps(asdict(config), indent=2), encoding='utf-8')
        path.replace(root / 'ocr_config.json')
    finally:
        Path(name).unlink(missing_ok=True)


def tesseract_executable():
    configured = os.environ.get('LEGAL_PLATFORM_TESSERACT')
    if configured:
        return configured
    # The tested private runtime must win over an incomplete system install.
    for candidate in (asset_root()/'ocr/tesseract.exe', Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Tesseract-OCR/tesseract.exe'):
        if candidate.is_file():
            return str(candidate)
    return shutil.which('tesseract')


def tesseract_data_args(executable):
    """Resolve data explicitly, independent of service cwd and TESSDATA_PREFIX."""
    data = Path(executable).resolve().parent / 'tessdata'
    return ['--tessdata-dir', str(data)] if data.is_dir() else []


def recognize_image(image, language):
    """Pass paths as argument-array entries; pytesseract retains quotes on Windows.

    TSV stdout avoids a global executable setting and supports concurrent jobs.
    Explicit data paths also work in service accounts and directories with spaces.
    """
    import csv
    import io
    import subprocess
    executable = tesseract_executable()
    if not executable:
        raise RuntimeError('Tesseract is unavailable')
    with tempfile.TemporaryDirectory(prefix='legal-ocr-page-') as directory:
        source = Path(directory) / 'page.png'
        image.save(source)
        result = subprocess.run(
            [executable, str(source), 'stdout', *tesseract_data_args(executable),
             '-l', language, '-c', 'tessedit_create_tsv=1'],
            capture_output=True, timeout=60,
            creationflags=0x08000000 if os.name == 'nt' else 0,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
        rows = list(csv.DictReader(io.StringIO(result.stdout.decode('utf-8')), delimiter='\t', quoting=csv.QUOTE_NONE))
        return {key: [row[key] for row in rows] for key in ('text', 'conf', 'block_num', 'par_num', 'line_num')}


def ocr_status():
    import subprocess
    executable = tesseract_executable()
    if not executable:
        return dict(tesseract_available=False, languages=[], message='Tesseract was not found. Install it on the library server or choose vision OCR below.')
    try:
        result = subprocess.run([executable, *tesseract_data_args(executable), '--list-langs'], capture_output=True, text=True, timeout=5,
                                creationflags=0x08000000 if os.name == 'nt' else 0)
        languages = result.stdout.splitlines()[1:] if result.returncode == 0 else []
        return dict(tesseract_available=result.returncode == 0, languages=languages,
                    message='Tesseract is ready for Vietnamese and English.' if {'vie','eng'} <= set(languages)
                    else 'Tesseract needs both Vietnamese (vie) and English (eng) language data, or choose vision OCR.')
    except (OSError, subprocess.TimeoutExpired):
        return dict(tesseract_available=False, languages=[], message='Tesseract could not start. Check its installation or choose vision OCR.')
