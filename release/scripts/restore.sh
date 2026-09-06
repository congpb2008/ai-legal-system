#!/usr/bin/env bash
# Restore portable archives to a new, empty destination. Never overwrites.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: release/scripts/restore.sh --source SOURCE.tar.gz [--data DATA.tar.gz] --target DIRECTORY

The target directory must not already exist. The source archive restores to
DIRECTORY/legal-platform; the data archive restores its storage tree beneath it.
EOF
}

source_archive=""
data_archive=""
target_dir=""
while (($#)); do
  case "$1" in
    --source) source_archive="$2"; shift 2 ;;
    --data) data_archive="$2"; shift 2 ;;
    --target) target_dir="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$source_archive" && -n "$target_dir" ]] || { usage >&2; exit 2; }
[[ -f "$source_archive" ]] || { echo "Source archive not found: $source_archive" >&2; exit 1; }
[[ ! -e "$target_dir" ]] || { echo "Refusing to overwrite existing target: $target_dir" >&2; exit 1; }

mkdir -p "$target_dir"
tar -xzf "$source_archive" -C "$target_dir"
app_dir="$target_dir/legal-platform"
[[ -f "$app_dir/pyproject.toml" ]] || { echo "Source archive did not contain legal-platform/pyproject.toml" >&2; exit 1; }

if [[ -n "$data_archive" ]]; then
  [[ -f "$data_archive" ]] || { echo "Data archive not found: $data_archive" >&2; exit 1; }
  [[ ! -e "$app_dir/storage" ]] || { echo "Refusing to overwrite restored storage: $app_dir/storage" >&2; exit 1; }
  tar -xzf "$data_archive" -C "$target_dir"
  [[ -d "$target_dir/legal-platform-data/storage" ]] || { echo "Data archive has no storage tree" >&2; exit 1; }
  mv "$target_dir/legal-platform-data/storage" "$app_dir/storage"
  if [[ -f "$target_dir/legal-platform-data/DATA_BUNDLE_README.md" ]]; then
    mv "$target_dir/legal-platform-data/DATA_BUNDLE_README.md" "$app_dir/DATA_BUNDLE_README.md"
  fi
  rmdir "$target_dir/legal-platform-data"
fi

echo "Restored source to: $app_dir"
[[ -n "$data_archive" ]] && echo "Restored persistent data to: $app_dir/storage"
