# Scanned PDFs and Ollama on another computer

Available from Legal Library **0.2.3**. An administrator configures these options in **Server settings**. Text PDFs and Word files still work immediately. OCR settings are separate from AI-assisted answers: you can use a vision model to read scans and keep search and answers in local mode.

## Connect to Ollama on another LAN computer

1. On the computer running Ollama, install the models you want to use. Record the exact installed model names; chat, embeddings and vision may need different models.
2. Make Ollama listen on the network. On Windows, quit Ollama from the tray, open **Edit environment variables for your account**, and create `OLLAMA_HOST` with value `0.0.0.0:11434`. Restart Ollama. You can bind to that computer's specific LAN address instead if your administrator prefers. See the [official Ollama network instructions](https://docs.ollama.com/faq).
3. Have your administrator allow incoming TCP port **11434** on that computer's Private network profile, limited to the library server's address. Keep it inside the trusted network. The library's own **Allow LAN access** launcher button opens the library port; it does not configure Ollama's firewall.
4. On the library, open **Server settings → Optional AI provider**. Enter an address such as `http://192.168.1.50:11434/v1`, replacing the example IP with the Ollama computer's address. Check **Allow this provider on my local network**.
5. Enter the installed chat and embedding model names. A standard local Ollama installation normally needs no API key; a gateway in front of it may require one. Approve the destination, choose **Test connection**, then **Save and enable**.

`localhost` means the computer hosting Legal Library. It does not refer to your browser or another PC. `0.0.0.0` is a listening setting, not a destination URL. With Docker, `localhost` refers to the container; use a reachable host or LAN address. Requests travel from the library server to Ollama, so browser CORS wildcards are not required.

The library's AI search integration uses Ollama's native embedding endpoints as well as its compatible chat API. A service exposing only OpenAI chat endpoints is not sufficient for this combined setting. The independent vision OCR setting below needs only compatible image chat completions.

## Read scans without Tesseract

1. Open **Server settings → Reading scanned PDFs (OCR)**.
2. Choose **Vision model (no Tesseract required)**.
3. Enter the vision provider's compatible API address, including `/v1` where the provider requires it. Ollama can use the same LAN address above; enable its separate LAN checkbox. Enter the exact name of a model that supports images. Ordinary text-only chat models cannot read a scan.
4. Enter a vision API key if required. It is stored separately from the answer-provider key. Blank keeps an existing key only at the same address; changing the address clears it unless you enter a replacement.
5. Approve sending scanned page images to this destination. **Test OCR** sends only a generated test image, never a library document. Success confirms that the model read that image, not that it is accurate on your documents.
6. Choose **Save OCR settings**. In **Documents**, open failed uploads and choose **Retry processing**, or upload a new scan. Already-ready documents are not silently reprocessed; upload a new version to replace their extracted content while preserving the old source version.

Ollama documents image inputs in its [OpenAI-compatible API](https://docs.ollama.com/api/openai-compatibility). Other providers must support `POST /chat/completions`, image data URLs, non-streamed text output, and the configured output-token limit. Use the provider's final URL; redirects are not followed.

## Use local OCR with an optional fallback

The three choices are:

| Method | Behavior |
| --- | --- |
| Tesseract on this server | Local recognition only; no scan images go to a vision provider. |
| Vision model | Sends pages needing image recognition directly to the configured model. No Tesseract installation is required. |
| Tesseract, then vision if needed | Tries Tesseract for each scanned page. Uses the approved vision destination only if local recognition fails or returns no readable text. |

Fallback does not measure whether a plausible Tesseract transcription is correct. Review difficult scans whichever method you use.

For local OCR, install Tesseract with **Vietnamese (`vie`) and English (`eng`)** language data on the library host. The settings page checks availability. The app finds the standard `C:\Program Files\Tesseract-OCR\tesseract.exe` location or the executable set by `LEGAL_PLATFORM_TESSERACT`. Restart the server after changing that environment variable. A Windows service must also be able to access the executable and language files. Follow [Tesseract's installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html).

## What is sent and how to review it

For mixed PDFs, embedded text pages stay on the server during extraction. Pages with fewer than 50 extracted characters are treated as needing OCR, so very short digital pages may also be sent. Vision OCR receives one rendered page image per request. It does not receive the whole PDF or other library files. Images use RGB PNG, up to 160 DPI and a 2048-pixel longest edge. This size bounds processing, but very small print may need a better scan.

Defaults are **120 seconds per vision page**, **8192 output tokens per page**, and **50 vision pages per document**. Settings allow 5–300 seconds, 512–32768 tokens and 1–200 pages. Large scanned documents may take many minutes. A failure may occur after earlier pages have already been sent; retrying can resend them and incur provider charges. Direct vision mode checks the page limit before sending; fallback counts the pages actually sent. PDF processing has a separate 500-page cap.

Unreadable, blank, empty or truncated responses leave the document needing attention. Check the reported page, improve the scan or settings and retry. Vision models can still omit or invent words, numbers and table structure without reporting a failure. Source inspection shows an explicit vision warning and records affected page numbers. Confidence is shown as unavailable, not a made-up accuracy percentage. Compare important quotations with **Download original**; matching extracted text does not establish that the transcription matches the image.

## Troubleshooting and upgrades

| Symptom | Check |
| --- | --- |
| Private address rejected | Enable LAN access in the relevant AI or OCR form. Each has its own setting. |
| Cannot connect | Ollama is running; `OLLAMA_HOST` was applied after restart; the IP/port and firewall are correct from the library server. |
| Model not found or image test fails | Exact installed model name, image support, endpoint suffix and key. |
| OCR stops on a dense page | Increase output tokens within the model's capacity; improve the scan. A text-only model is not a substitute. |
| Redirect or certificate error | Use the final endpoint and a certificate trusted by the library host. HTTPS certificate checks stay enabled. |
| Tesseract missing after service installation | Install it machine-wide or configure a path/language data readable by the service. Alternatively choose vision OCR. |

LAN permission covers private IPv4 ranges and IPv6 unique-local addresses. Metadata, link-local, multicast and reserved destinations remain blocked. DNS must resolve from the library host. Connections use the validated address, do not follow redirects, and do not use ambient HTTP proxy environment variables. Configure an approved direct endpoint or reverse proxy if your network requires one.

Make an encrypted backup, stop the server/service, replace the full application folder, and retain your data directory when upgrading. No database migration is required by 0.2.3. OCR configuration and its key are included in encrypted backups. Restore backups containing `ocr_config.json` with **0.2.3 or later**; earlier versions reject that new archive entry. Older backups can still be restored into 0.2.3. Restoring creates a separate data folder; follow the quickstart before switching hosts.

The release tests use synthetic images and controlled HTTP providers. They verify image requests, LAN policy, permissions, failure handling, mixed pages, backup restore and browser controls. They do not replace a trial with your actual Ollama computer or a review of representative Vietnamese scans.
