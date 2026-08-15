#!/bin/sh
set -e

# Ensure storage directory structure exists with correct permissions
DATA_DIR="${LEGAL_PLATFORM_DATA_DIR:-/app/storage}"
mkdir -p "$DATA_DIR/db" "$DATA_DIR/files" 2>/dev/null || true

# Execute application
exec "$@"
