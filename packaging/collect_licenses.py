"""Collect installed distribution notices alongside a Windows bundle.

This copies supplied notices; it does not determine the product's licensing.
Run using the same environment that built the executable.
"""
from importlib import metadata
from pathlib import Path
import json
import re
import shutil
import sys


def collect(destination):
    target = Path(destination) / "licenses"
    target.mkdir(parents=True, exist_ok=True)
    inventory = []
    for distribution in sorted(metadata.distributions(), key=lambda d: d.metadata.get("Name", "")):
        name = distribution.metadata.get("Name", "unknown")
        folder = target / re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        copied = []
        for item in distribution.files or []:
            if not any(word in item.name.lower() for word in ("license", "licence", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(item))
            if not source.is_file() or source.suffix.lower() in {".py", ".pyc", ".pyd", ".so"}:
                continue
            folder.mkdir(exist_ok=True)
            filename = f"{len(copied) + 1}-{source.name}"
            shutil.copy2(source, folder / filename)
            copied.append(filename)
        inventory.append({"name": name, "version": distribution.version, "notices": copied})
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, target / "Python-LICENSE.txt")
    tcl_root = Path(sys.base_prefix) / "tcl"
    if tcl_root.exists():
        for source in tcl_root.glob("*/license*"):
            if source.is_file():
                shutil.copy2(source, target / f"{source.parent.name}-{source.name}")
    (target / "build-environment-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    (target / "README.txt").write_text(
        "Notices copied from the build environment. The inventory includes build/test tools "
        "as well as runtime dependencies; inclusion does not imply every package is bundled. "
        "See THIRD-PARTY-NOTICES.md for outstanding distribution decisions.\n", encoding="utf-8")


if __name__ == "__main__":
    collect(sys.argv[1])
