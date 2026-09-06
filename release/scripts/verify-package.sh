#!/usr/bin/env bash
# Verify checksums, archive layouts, and SQLite integrity without touching data.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: release/scripts/verify-package.sh --release-dir DIRECTORY
EOF
}

release_dir=""
while (($#)); do
  case "$1" in
    --release-dir) release_dir="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -n "$release_dir" ]] || { usage >&2; exit 2; }
release_dir="$(cd "$release_dir" && pwd)"
source_archive="$release_dir/legal-platform-source.tar.gz"
data_archive="$release_dir/legal-platform-data.tar.gz"
[[ -f "$source_archive" && -f "$data_archive" ]] || { echo "Expected source and data archives in $release_dir" >&2; exit 1; }
(
  cd "$release_dir"
  sha256sum -c checksums/SHA256SUMS
)
temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/legal-platform-verify.XXXXXX")"
trap 'rm -rf -- "$temp_dir"' EXIT
tar -tzf "$source_archive" > "$temp_dir/source.list"
tar -tzf "$data_archive" > "$temp_dir/data.list"
grep -Fqx 'legal-platform/pyproject.toml' "$temp_dir/source.list"
grep -Fqx 'legal-platform/.git/HEAD' "$temp_dir/source.list"
grep -Fqx 'legal-platform-data/storage/db/legal_platform.db' "$temp_dir/data.list"
grep -Fqx 'legal-platform-data/storage/files/' "$temp_dir/data.list"
if grep -q 'provider_config.json' "$temp_dir/data.list"; then
  echo "Provider configuration is present: treat this data bundle as secret-bearing." >&2
fi

tar -xzf "$data_archive" -C "$temp_dir" legal-platform-data/storage/db/legal_platform.db
python3 - "$temp_dir/legal-platform-data/storage/db/legal_platform.db" <<'PY'
import sqlite3
import sys
with sqlite3.connect(sys.argv[1]) as connection:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    raise SystemExit(f"SQLite integrity check failed: {result}")
print("SQLite integrity check: ok")
PY
echo "Package verification passed."
