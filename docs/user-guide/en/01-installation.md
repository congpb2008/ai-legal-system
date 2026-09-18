> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Installation Guide

This guide explains how to install and set up the Legal Knowledge Platform on your system.

---

## Prerequisites

Before installing, ensure your system meets these requirements:

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.12 | 3.12 or newer |
| RAM | 2 GB | 4 GB or more |
| Disk space | 500 MB | 2 GB (for documents + index) |
| Operating system | Linux, macOS | Linux (Ubuntu 22.04+) |

---

## Step 1: Verify Python Installation

Open a terminal and check your Python version:

```bash
python3 --version
```

Expected output:
```
Python 3.12.3
```

If Python 3.12 is not installed, download it from [python.org](https://python.org) or use your system's package manager:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv

# macOS (Homebrew)
brew install python@3.12
```

---

## Step 2: Download the Project

Clone the repository or extract the project archive:

```bash
git clone <repository-url> legal-platform
cd legal-platform
```

Or if you received the project as an archive:

```bash
unzip legal-platform.zip
cd legal-platform
```

---

## Step 3: Create a Virtual Environment

A virtual environment keeps the project's dependencies isolated from other Python projects.

```bash
# Create the virtual environment
python3 -m venv .venv

# Activate it
# On Linux/macOS:
source .venv/bin/activate

# On Windows:
# .venv\Scripts\activate
```

Your terminal prompt should now show `(.venv)` at the beginning.

---

## Step 4: Install Dependencies

The project is packaged as an installable Python package. From the project root, install it (including its dependencies) into the active virtual environment:

```bash
pip install -e .
```

This installs the `legal-platform` package, its runtime dependencies, and the `legal-platform` command-line entrypoint. There is **no need to set `PYTHONPATH`**.

> **Note:** The core runtime dependencies are `pydantic`, `pymupdf`, `pdf2image`, and `pytesseract`. To also install the test tooling (`pytest`), use:
>
> ```bash
> pip install -e ".[test]"
> ```

> **Note:** Scanned-document OCR additionally requires the `tesseract` system binary. See [Troubleshooting](08-troubleshooting.md).

---

## Step 5: Verify the Installation

Run the test suite to confirm everything is working:

```bash
python3 -m pytest
```

Expected output:
```
...
619 passed in 2.36s
```

If all 619 tests pass, the installation is successful.

---

## Step 6: Configure Persistent Storage (Optional)

By default, the platform stores all data **in memory**. This means:
- All documents and data are lost when the server stops
- Uploaded files are stored in a temporary directory

To configure persistent storage, you need to modify the startup script (see the Configuration guide).

> **Important:** The current MVP stores data in SQLite in-memory databases. Persistent storage configuration is planned for a future release.

---

## Directory Structure

After installation, the project directory contains:

```
legal-platform/
├── backend/
│   └── legal_platform/
│       ├── api/          # HTTP API server
│       ├── contracts/    # Data contracts
│       ├── modules/      # Business logic modules
│       └── storage/      # Database and audit log
├── frontend/
│   ├── index.html        # Web interface
│   ├── css/              # Styles
│   └── js/               # JavaScript
├── tests/                # Test suite
├── docs/                 # Documentation
├── tasks/                # Task specifications
├── 00-product/           # Product specifications
├── 01-domain/            # Domain model
├── 02-contracts/         # Contract specifications
├── 03-architecture/      # Architecture documents
├── 04-decisions/         # Architecture Decision Records
├── design/               # Design documents
└── examples/             # Example files
```

---

## Troubleshooting Installation

### "Python 3.12 not found"

Install Python 3.12:
```bash
# Ubuntu
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv
```

### "The virtual environment was not created successfully"

On Debian/Ubuntu, the `python3-venv` package may not be installed:
```bash
sudo apt install python3.12-venv
# Then retry:
python3 -m venv .venv
```

### "pip not found" or "No module named ensurepip"

If `pip` is not available inside the virtual environment, install it:
```bash
# Install pip for Python 3.12
sudo apt install python3-pip
# Or use the ensurepip module if available:
python3 -m ensurepip --upgrade
```

### "error: externally-managed-environment" (PEP 668)

On newer Ubuntu/Debian versions, system-wide pip installs are blocked. Always use a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### "pytest not found"

Install the package with test dependencies:
```bash
pip install -e ".[test]"
```

### "ModuleNotFoundError: No module named 'legal_platform'"

Ensure you are running commands from the project root directory and the virtual environment is activated:
```bash
cd legal-platform
source .venv/bin/activate
python3 -m pytest
```

If the error persists, reinstall the package:
```bash
pip install -e .
```

---

## Next Steps

Once installation is complete, proceed to the [Quick Start Guide](02-quick-start.md) to learn how to start the server and use the platform.