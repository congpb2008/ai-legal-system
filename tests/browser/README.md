# Browser regression checks

These checks start a disposable **loopback-only** server with synthetic accounts, 106 catalog records and 103 collections. They refuse a nonempty data directory and do not accept an existing server URL. No real documents, customer accounts, external AI service or paid provider is used. The catalog fixtures have no original source files; source extraction/download correctness is covered by `tests/test_user_journeys.py` and the packaged executable journey.

Install the source application's Python dependencies and editable package first. With Node.js 22+ and Python 3.12+ available, run from the repository:

```sh
npm install --prefix tests/browser
npx --prefix tests/browser playwright install chromium
npm test --prefix tests/browser
```

The Python executable defaults to `python`. Set `LEGAL_LIBRARY_TEST_PYTHON` to the absolute path of the intended virtual environment interpreter if necessary. `LEGAL_LIBRARY_BROWSER_EXECUTABLE` can select an installed Chromium-based browser such as Microsoft Edge. `LEGAL_LIBRARY_PLAYWRIGHT_MODULE` is an optional absolute module-directory override for environments with a preinstalled Playwright runtime; ordinary installations leave it unset.

The test checks complete dashboard counts, collection lists beyond 100, pagination, Vietnamese title matching, archive discovery, mobile width, reader/contributor actions, metadata saves, delayed-answer isolation and sign-out during a held upload batch. Delayed HTTP responses are deliberately controlled in the browser so the race checks are reproducible. The upload cancellation fixture is never forwarded to ingestion.

Evidence is kept under `.artifacts/browser-*/`: desktop/mobile screenshots, `result.json` on success, and `host.log`. The browser and server are stopped in `finally`; the server also has a three-minute maximum lifetime. A failed run exits nonzero and retains its test folder for investigation. This optional Node toolchain does not ship with or run inside the Windows application.

CI runs this flow on Linux after the Python suite. Local Windows verification can use Edge; neither proves elevated Windows service installation, a reboot, certificate trust on a second LAN device, or public HTTPS deployment.
