# Bundled Vietnamese OCR and audit checkpoint — 2026-09-10

## Build and use

The Windows application now carries a private Tesseract runtime and Vietnamese/English models. Users extract the whole folder and select local Tesseract (the default); there is no runtime download or installer. Vision-only and consented Tesseract-to-vision fallback are preserved. Earlier published bundles still require replacement.

On a Windows build machine with Python dependencies and full 7-Zip installed:

```powershell
python packaging/prepare_ocr.py --seven-zip "C:/Program Files/7-Zip/7z.exe"
python -m pytest tests/test_bundled_ocr.py -q
python -m PyInstaller --noconfirm packaging/LegalLibrary.spec
$env:LEGAL_PLATFORM_TEST_OCR_ROOT = (Resolve-Path dist/LegalLibrary/_internal).Path
python -m pytest tests/test_bundled_ocr.py -q
```

The preparation script verifies SHA-256 pins before extraction, never runs the Tesseract installer, stages all runtime DLLs and the two language files, verifies language discovery, and preserves supplied documentation. It refuses an existing `ocr` directory; use a fresh checkout to rebuild. Binaries are generated assets excluded from Git. CI repeats preparation, real OCR, packaging, and OCR from the packaged location. The spec refuses to create a Windows release without OCR.

## Audit findings addressed

1. **Missing engine in Windows releases:** previous runtime discovery supported a bundle that packaging never created. The build now includes and requires it.
2. **System installation wins over bundle:** an incomplete installation on PATH could override private OCR. The explicit administrator override remains first; bundled OCR now precedes system discovery.
3. **False-positive readiness / Windows quoting:** an actual scanned PDF exposed that pytesseract retained quotes around the data directory, while the health check succeeded. Recognition now passes separate subprocess arguments and decodes UTF-8 TSV directly, without shell invocation or mutable global executable configuration.
4. **Service environment dependence:** language data is resolved beside the executable and passed explicitly for both discovery and recognition. Per-page temporary folders are cleaned up, subprocesses are hidden on Windows, and the 60-second page timeout is retained.

## Evidence and limits

The focused OCR suite passed 58 tests, including actual Vietnamese text extracted from an image-only PDF with deliberately invalid TESSDATA_PREFIX and a changed working directory. The complete Python regression suite also passed with one optional live-Caddy proxy test skipped. The real OCR test passed again using the packaged runtime. This is a clean synthetic printed-text case, not an accuracy benchmark for customer scans.

Audit continuation priorities: inspect account/recovery and sharing boundaries, upload/retry behavior, settings usability in Vietnamese, and backup/service operations. Exercise a clean Windows host and second LAN machine, rotated/blurred scans, tables, stamps, handwritten text and live vision/Ollama. Vision fallback triggers on failure/empty output, not on subtly incorrect recognition. Do not claim a complete product audit or legal transcription accuracy from the focused check. Native DLL licensing inventory and existing release licensing decisions remain open before public distribution.

See RELEASE-HANDOFF.md for earlier app validation and remaining deployment limitations. This checkpoint supersedes its statement that new Windows builds use external-only Tesseract.
