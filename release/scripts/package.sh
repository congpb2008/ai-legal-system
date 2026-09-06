#!/usr/bin/env bash
# Create portable source and persistent-data archives without changing source
# documents or overwriting an existing release unless --force is supplied.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: release/scripts/package.sh [--data-dir PATH] [--force] [--include-provider-config]

Creates:
  release/legal-platform-source.tar.gz
  release/legal-platform-data.tar.gz
  release/checksums/SHA256SUMS

The data archive contains a consistent SQLite online backup, immutable source
files, and the setup sentinel. Provider configuration is excluded by default
because it may contain a private API key. --include-provider-config is an
explicit opt-in for a private, securely handled migration archive.
EOF
}

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
data_dir="${LEGAL_PLATFORM_DATA_DIR:-$root_dir/storage}"
force=0
include_provider_config=0

while (($#)); do
  case "$1" in
    --data-dir) data_dir="$2"; shift 2 ;;
    --force) force=1; shift ;;
    --include-provider-config) include_provider_config=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for command in tar gzip sha256sum python3; do
  command -v "$command" >/dev/null || { echo "Required command missing: $command" >&2; exit 1; }
done

data_dir="$(cd "$data_dir" && pwd)"
db_path="$data_dir/db/legal_platform.db"
[[ -f "$db_path" ]] || { echo "Persistent database not found: $db_path" >&2; exit 1; }
[[ -d "$data_dir/files" ]] || { echo "Persistent source file directory not found: $data_dir/files" >&2; exit 1; }

release_dir="$root_dir/release"
source_archive="$release_dir/legal-platform-source.tar.gz"
data_archive="$release_dir/legal-platform-data.tar.gz"
checksums_dir="$release_dir/checksums"

if (( ! force )) && [[ -e "$source_archive" || -e "$data_archive" || -e "$checksums_dir/SHA256SUMS" ]]; then
  echo "Release archive/checksum already exists. Re-run with --force to replace only generated package outputs." >&2
  exit 1
fi

if (( force )); then
  rm -f -- "$source_archive" "$data_archive" "$checksums_dir/SHA256SUMS"
fi
mkdir -p "$checksums_dir"
stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/legal-platform-package.XXXXXX")"
trap 'rm -rf -- "$stage_dir"' EXIT

echo "Creating source snapshot (including .git; excluding local state and caches)..."
mkdir -p "$stage_dir/source/legal-platform"
tar -C "$root_dir" \
  --exclude='./storage' --exclude='./storage/**' \
  --exclude='./.venv' --exclude='./.venv/**' --exclude='./venv' --exclude='./venv/**' \
  --exclude='./node_modules' --exclude='./node_modules/**' \
  --exclude='./__pycache__' --exclude='./**/__pycache__' --exclude='./**/*.pyc' \
  --exclude='./.pytest_cache' --exclude='./.mypy_cache' --exclude='./.ruff_cache' \
  --exclude='./build' --exclude='./dist' --exclude='./.eggs' --exclude='./**/*.egg-info' \
  --exclude='./.env' --exclude='./.env.*' \
  --exclude='./release/*.tar.gz' --exclude='./release/checksums' --exclude='./release/checksums/**' \
  --exclude='./release/.staging' --exclude='./release/restore-*' \
  --exclude='./Luat-DT-QH15' --exclude='./Luat-DT-QH15/**' \
  --exclude='./**/*.log' --exclude='./**/*.tmp' --exclude='./**/*.temp' \
  -cf - . | tar -C "$stage_dir/source/legal-platform" -xf -
# The broad private-.env exclusion above also matches the safe template.
# Put the template back explicitly; it is required for a portable deployment.
if [[ -f "$root_dir/.env.example" ]]; then
  cp -a "$root_dir/.env.example" "$stage_dir/source/legal-platform/.env.example"
fi
tar -C "$stage_dir/source" -czf "$source_archive" legal-platform

echo "Creating consistent persistent-data snapshot..."
data_stage="$stage_dir/data/legal-platform-data/storage"
mkdir -p "$data_stage/db"
python3 - "$db_path" "$data_stage/db/legal_platform.db" <<'PY'
import sqlite3
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
target.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
    result = dst.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    raise SystemExit(f"SQLite backup integrity check failed: {result}")
print(f"SQLite online backup verified: {target}")
PY
cp -a "$data_dir/files" "$data_stage/files"
if [[ -f "$data_dir/.configured" ]]; then
  cp -a "$data_dir/.configured" "$data_stage/.configured"
fi
if (( include_provider_config )) && [[ -f "$data_dir/provider_config.json" ]]; then
  cp -a "$data_dir/provider_config.json" "$data_stage/provider_config.json"
fi
file_count="$(find "$data_stage/files" -type f | wc -l | tr -d ' ')"
db_size="$(stat -c '%s' "$data_stage/db/legal_platform.db")"
cat > "$stage_dir/data/legal-platform-data/DATA_BUNDLE_README.md" <<EOF
# Legal Knowledge Platform persistent-data bundle

- SQLite online backup: storage/db/legal_platform.db (${db_size} bytes)
- Immutable uploaded/source files: ${file_count}
- Setup sentinel: $(test -f "$data_stage/.configured" && echo included || echo absent)
- provider_config.json: $(test -f "$data_stage/provider_config.json" && echo included-by-explicit-request || echo excluded-for-secret-safety)

Restore this storage tree at the host directory configured by
LEGAL_PLATFORM_HOST_DATA_DIR, which Docker maps to /app/storage.
EOF
tar -C "$stage_dir/data" -czf "$data_archive" legal-platform-data

(
  cd "$release_dir"
  sha256sum "$(basename "$source_archive")" "$(basename "$data_archive")" > "checksums/SHA256SUMS"
)
echo "Created: $source_archive"
echo "Created: $data_archive"
echo "Created: $checksums_dir/SHA256SUMS"
