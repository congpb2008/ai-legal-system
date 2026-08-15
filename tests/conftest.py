"""Global test hygiene for the Legal Knowledge Platform.

Production defaults intentionally use the workspace ``storage/`` directory.
Tests must never write synthetic documents, indexes, jobs, or provider config
into that real application-managed corpus.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_application_data(tmp_path):
    """Run every test against its own disposable application data root."""
    previous = os.environ.get("LEGAL_PLATFORM_DATA_DIR")
    test_root = tmp_path / "application-data"
    os.environ["LEGAL_PLATFORM_DATA_DIR"] = str(test_root)
    try:
        yield test_root
    finally:
        if previous is None:
            os.environ.pop("LEGAL_PLATFORM_DATA_DIR", None)
        else:
            os.environ["LEGAL_PLATFORM_DATA_DIR"] = previous
