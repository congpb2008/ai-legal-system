"""Administrator-only OCR configuration and a small synthetic vision probe."""
from io import BytesIO
from legal_platform.api.models import ApiResponse
from .config import load_ocr_config, merge_ocr_config, save_ocr_config, ocr_status
from .engine import OcrEngineError
from .vision import VisionOcrEngine


def handle_ocr_settings(method, path, body, auth, uid):
    if not auth.is_admin(uid):
        return auth.error('Administrator access required.', 403)
    if method == 'GET' and path == '/v1/ocr/config':
        return ApiResponse.ok(data=dict(load_ocr_config().safe_dict(), runtime=ocr_status()))
    if method != 'POST' or path not in ('/v1/ocr/config', '/v1/ocr/test'):
        return auth.error('OCR operation not found.', 404)
    try:
        config = merge_ocr_config(load_ocr_config(), body)
        if config.mode != 'tesseract' and body.get('consent') is not True:
            return auth.error('Approve sending scanned page images to the configured OCR provider.')
        if path.endswith('/config'):
            save_ocr_config(config)
            return ApiResponse.ok(data=dict(config.safe_dict(), runtime=ocr_status()))
        if config.mode == 'tesseract':
            status = ocr_status()
            return ApiResponse.ok(data=dict(reachable=status['tesseract_available'] and {'vie','eng'} <= set(status['languages']), message=status['message']))
        # This test sends only a generated probe, never any library document.
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (900, 160), 'white')
        ImageDraw.Draw(image).text((30, 45), 'LIBRARY OCR TEST 4827', fill='black', font=ImageFont.load_default(size=42))
        output = BytesIO();image.save(output, format='PNG')
        config.timeout_seconds = min(config.timeout_seconds, 45)
        config.max_tokens = min(config.max_tokens, 1024)
        text = VisionOcrEngine(config).transcribe_image(output.getvalue())
        recognized = 'LIBRARYOCRTEST4827' in ''.join(c for c in text.upper() if c.isalnum())
        return ApiResponse.ok(data=dict(reachable=recognized, message=
            'The model read the test image. Review real Vietnamese scans before relying on its transcriptions.' if recognized else
            'The provider replied, but did not read the test image correctly. Choose a vision-capable model and check its settings.'))
    except (ValueError, OcrEngineError) as exc:
        return auth.error(str(exc))
