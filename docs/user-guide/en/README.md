# Documentation Bug Report

**Tester:** First-time user (simulated)
**Date:** 2026-08-07
**Documentation tested:** `docs/user-guide/en/` (01-installation, 02-quick-start, 03-uploading-documents)
**Actual result:** 14 bugs found, could not complete the full workflow without inspecting source code.

---

## Bug 1 — venv creation fails silently

**Document:** `01-installation.md`, Step 3
**Severity:** BLOCKER

### Description
The command `python3 -m venv .venv` fails on Ubuntu 24.04 because the `python3.12-venv` package is not installed. The error message says:

```
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.

    apt install python3.12-venv
```

### Why it's a bug
The troubleshooting section covers "Python 3.12 not found" but does **not** cover this "ensurepip not available" error, which is the most common venv failure on Debian/Ubuntu.

### Fix needed
Add a troubleshooting entry for "ensurepip not available" or add `sudo apt install python3.12-venv` as a prerequisite.

---

## Bug 2 — pip is not available inside the venv

**Document:** `01-installation.md`, Step 4
**Severity:** BLOCKER

### Description
Even if the user works around Bug 1 by running `python3 -m venv --without-pip .venv`, pip is **not available** inside the virtual environment:

```
$ source .venv/bin/activate
$ python3 -m pip install pydantic>=2.5
/home/vostro/.../.venv/bin/python3: No module named pip
```

### Why it's a bug
The troubleshooting section has a "pip not found" entry, but it says to run `python3.12 -m ensurepip --upgrade`. This also fails because `ensurepip` is not available either:

```
/home/vostro/.../.venv/bin/python3: No module named ensurepip
```

The user is stuck — they have a venv with no pip and no way to install pip inside it.

### Fix needed
Either:
- Add `sudo apt install python3.12-venv` as a prerequisite before Step 3, OR
- Document that the user should install pip manually: `wget https://bootstrap.pypa.io/get-pip.py && python3 get-pip.py`

---

## Bug 3 — PEP 668 blocks system pip install

**Document:** `01-installation.md`, Step 4
**Severity:** BLOCKER

### Description
On Ubuntu 23.04+ (PEP 668), running `pip install pydantic>=2.5` outside a properly-created venv fails with:

```
error: externally-managed-environment
This environment is externally managed
╰─> To install Python packages system-wide, try apt install python3-pydantic
```

The user is told to use a venv, but the venv creation itself fails (Bug 1).

### Why it's a bug
The documentation assumes a clean Python environment. It does not mention PEP 668 or the `--break-system-packages` flag.

### Fix needed
Add a note about PEP 668 and either:
- Document the `--break-system-packages` workaround, OR
- Ensure venv creation works (fix Bug 1 first)

---

## Bug 4 — pytest is not installed

**Document:** `01-installation.md`, Step 5
**Severity:** HIGH

### Description
Step 5 says to run `python3 -m pytest` to verify the installation. But `pytest` is not listed as a dependency in Step 4 (only `pydantic` is installed). The troubleshooting section says `pip install pytest` but this assumes pip is available (see Bug 2).

### Why it's a bug
A user following the instructions literally will hit `ModuleNotFoundError: No module named 'pytest'` and have no documented way to fix it.

### Fix needed
Either:
- Add `pytest` to the dependency installation command in Step 4, OR
- Add a troubleshooting entry that covers this specific scenario

---

## Bug 5 — Server fails with ModuleNotFoundError

**Document:** `02-quick-start.md`, Step 1
**Severity:** BLOCKER

### Description
The command to start the server:

```bash
python3 -c "
from legal_platform.api.server import PlatformAPI
api = PlatformAPI(host='0.0.0.0', port=8080)
api.start()
"
```

Fails with:

```
Traceback (most recent call last):
  File "<string>", line 2, in <module>
ModuleNotFoundError: No module named 'legal_platform'
```

### Why it's a bug
The `backend/` directory is not in Python's module search path. The documentation never mentions setting `PYTHONPATH`. The test suite works because `pyproject.toml` has `pythonpath = ["backend"]` in the pytest config, but the startup command doesn't use pytest.

A new user has no way to know they need `PYTHONPATH=/path/to/backend`.

### Fix needed
The startup command must either:
- Set `PYTHONPATH` explicitly, OR
- Be a proper entry point script (e.g., `python3 -m legal_platform.api.server`), OR
- Include a `__main__.py` and be installed as a package

---

## Bug 6 — curl command uses placeholder token

**Document:** `02-quick-start.md`, Step 3 (API section)
**Severity:** HIGH

### Description
The vault creation curl command shows:

```bash
curl -X POST http://localhost:8080/api/v1/vaults \
  -H "Authorization: Bearer ***" \
  -d '{"name": "My Documents", "vault_type": "DEPARTMENT"}'
```

The `***` is a placeholder. A new user who copies and pastes this command will get a 401 error.

### Why it's a bug
The login command above it returns a token, but there is no instruction to save it into a variable and use it. The `***` is not a valid token.

### Fix needed
Either:
- Show a complete example with a shell variable: `TOKEN=$(...)` then `-H "Authorization: Bearer $TOKEN"`, OR
- Add explicit instructions: "Replace `***` with the token from the login response"

---

## Bug 7 — No API upload command in Quick Start

**Document:** `02-quick-start.md`, Step 4
**Severity:** MEDIUM

### Description
Step 4 (Upload a Document) only describes the Web UI. If the user has been following the API path (login via curl, create vault via curl), they will not find the upload API command in the Quick Start guide. They must navigate to a different document (`03-uploading-documents.md`).

### Why it's a bug
The Quick Start guide should be self-contained for the basic workflow. A user following the API path is left hanging at Step 4.

### Fix needed
Add an API upload example to Step 4, or add a cross-reference: "To upload via the API, see [Uploading Documents](03-uploading-documents.md)."

---

## Bug 8 — Upload curl command also uses placeholder token

**Document:** `03-uploading-documents.md`, API section
**Severity:** HIGH

### Description
Same as Bug 6 — the upload curl command shows `"Authorization: Bearer ***"` instead of a working example with a variable.

### Fix needed
Same as Bug 6.

---

## Bug 9 — vault_id in upload example is a fake UUID

**Document:** `03-uploading-documents.md`, API section
**Severity:** MEDIUM

### Description
The upload curl example uses `"vault_id": "550e8400-e29b-41d4-a716-446655440000"`. This is a well-known example UUID (v4 nil UUID). A new user who copies this verbatim will get a "Vault not found" error.

### Why it's a bug
There is no explicit callout that this UUID must be replaced with the user's actual vault ID. The note in the Quick Start says "Save the vault ID" but the upload document doesn't remind the user.

### Fix needed
Add a warning: "Replace the vault_id with the actual ID of your vault from Step 3."

---

## Bug 10 — Server startup blocks the terminal

**Document:** `02-quick-start.md`, Step 1
**Severity:** MEDIUM

### Description
The server startup command runs in the foreground and blocks the terminal. A new user following the guide literally will have their terminal stuck and cannot proceed to Step 2 (which requires running curl commands).

The note says "use a terminal multiplexer like tmux or screen" but:
1. A new user may not have tmux/screen installed
2. The guide doesn't explain how to use them
3. There's no mention of `&` (backgrounding) or `nohup`

### Fix needed
Either:
- Add a `&` to background the process: `api.start() &` or similar, OR
- Provide a one-liner that backgrounds the server, OR
- Add a note about opening a second terminal

---

## Bug 11 — No screenshots or placeholders

**Document:** All files
**Severity:** LOW

### Description
The documentation requirements said "Include screenshots/placeholders where appropriate" but no screenshots or image placeholders exist anywhere in the documentation.

### Fix needed
Add screenshot placeholders (e.g., `![Login screen](screenshots/login.png)`) or remove the promise from the requirements. Screenshots are not yet available — see Task 023 for visual QA.

---

## Bug 12 — Search returns empty without explanation

**Document:** `02-quick-start.md`, Step 5
**Severity:** HIGH

### Description
After uploading a document and searching, the result is empty (`"evidence": []`). The Quick Start does not explain why this happens. The user just uploaded a document and now can't find it.

The Uploading Documents guide (03) mentions that the processing pipeline is not automated in the MVP, but the Quick Start does not reference this. A new user following the Quick Start linearly will be confused.

### Why it's a bug
The Quick Start should either:
- Warn the user before they search that results may be empty, OR
- Explain the processing pipeline limitation, OR
- Provide a way to trigger processing

### Fix needed
Add a note in Step 5: "Note: In the current MVP, uploaded documents are registered but may not be fully indexed for search. The automated processing pipeline is planned for a future release."

---

## Bug 13 — No startup script or CLI entry point

**Document:** `02-quick-start.md`, Step 1
**Severity:** MEDIUM

### Description
The startup command is a complex `python3 -c "..."` one-liner. There is no `main.py`, no `__main__.py`, no `setup.py` entry point, no shell script. A new user has to type or paste a multi-line Python command.

### Why it's a bug
This is fragile (quoting issues, indentation errors) and unfriendly. Every other major project has a simple `python3 -m mypackage` or `./start.sh` or `docker-compose up`.

### Fix needed
Create a proper entry point, e.g.:
- `python3 -m legal_platform` (with a `__main__.py`)
- A `start.sh` script
- A `docker-compose.yml`

---

## Bug 14 — Server output path mismatch

**Document:** `02-quick-start.md`, Step 1 (expected output)
**Severity:** LOW

### Description
The documentation says the expected output includes:

```
API v1:  http://0.0.0.0:8080/api/v1/...
```

But the actual server output is:

```
API v1:  http://0.0.0.0:8080/v1/...
```

The `/api` prefix is missing from the printed message. (The actual routing works correctly — `/api/v1/...` is handled — but the printed message is wrong.)

### Fix needed
Update the server's startup message or the documentation to match.

---

## Summary

| # | Bug | Document | Severity |
|---|-----|----------|----------|
| 1 | venv creation fails (ensurepip missing) | 01-installation.md | BLOCKER |
| 2 | pip not available in venv | 01-installation.md | BLOCKER |
| 3 | PEP 668 blocks system pip | 01-installation.md | BLOCKER |
| 4 | pytest not installed | 01-installation.md | HIGH |
| 5 | Server fails with ModuleNotFoundError | 02-quick-start.md | BLOCKER |
| 6 | curl command uses placeholder token `***` | 02-quick-start.md | HIGH |
| 7 | No API upload command in Quick Start | 02-quick-start.md | MEDIUM |
| 8 | Upload curl uses placeholder token | 03-uploading-documents.md | HIGH |
| 9 | vault_id is a fake UUID without warning | 03-uploading-documents.md | MEDIUM |
| 10 | Server startup blocks terminal | 02-quick-start.md | MEDIUM |
| 11 | No screenshots or placeholders | All files | LOW |
| 12 | Search returns empty without explanation | 02-quick-start.md | HIGH |
| 13 | No startup script or CLI entry point | 02-quick-start.md | MEDIUM |
| 14 | Server output path mismatch (/api prefix) | 02-quick-start.md | LOW |

**4 BLOCKER** — user cannot proceed past this point
**4 HIGH** — user will be confused or get errors
**4 MEDIUM** — user experience degraded
**2 LOW** — cosmetic or nice-to-have