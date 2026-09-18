"""Real image-only Vietnamese PDF through the application's OCR engine."""
import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
from legal_platform.modules.ocr_service import config


def test_private_runtime_wins_over_path(tmp_path, monkeypatch):
    (tmp_path/'ocr').mkdir()
    bundled = tmp_path/'ocr/tesseract.exe'
    bundled.touch()
    monkeypatch.delenv('LEGAL_PLATFORM_TESSERACT', raising=False)
    monkeypatch.setattr(config, 'asset_root', lambda: tmp_path)
    monkeypatch.setattr(config.shutil, 'which', lambda _: 'broken-system.exe')
    assert config.tesseract_executable() == str(bundled)
    monkeypatch.setenv('LEGAL_PLATFORM_TESSERACT', 'explicit.exe')
    assert config.tesseract_executable() == 'explicit.exe'


def test_real_vietnamese_scan(tmp_path, monkeypatch):
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont
    from legal_platform.modules.ocr_service.engine import Pdf2ImageTesseractEngine
    root = Path(os.environ.get('LEGAL_PLATFORM_TEST_OCR_ROOT', Path(__file__).resolve().parents[1]))
    if not (root/'ocr/tesseract.exe').exists():
        pytest.skip('Run packaging/prepare_ocr.py first (Windows build gate)')
    monkeypatch.setattr(config, 'asset_root', lambda: root)
    monkeypatch.delenv('LEGAL_PLATFORM_TESSERACT', raising=False)
    monkeypatch.setenv('TESSDATA_PREFIX', str(tmp_path/'wrong-data'))
    monkeypatch.chdir(tmp_path)
    status = config.ocr_status()
    assert status['tesseract_available'] and {'vie', 'eng'} <= set(status['languages'])
    image = Image.new('RGB', (1800, 600), 'white')
    font = ImageFont.truetype(str(Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/arial.ttf'), 48)
    expected = 'Cộng hòa xã hội chủ nghĩa Việt Nam'
    ImageDraw.Draw(image).text((65, 130), expected, font=font, fill='black')
    png = io.BytesIO()
    image.save(png, format='PNG')
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=200)
        page.insert_image(page.rect, stream=png.getvalue())
        assert not page.get_text().strip()
        result = Pdf2ImageTesseractEngine().extract(content=pdf.tobytes(), document_id=uuid4(), version_id=uuid4())
    assert expected.casefold() in result.pages[0].text.casefold(), result.warnings
