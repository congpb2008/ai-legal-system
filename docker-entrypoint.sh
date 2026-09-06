#!/bin/sh
set -e

# Ensure storage directory structure exists and then drop privileges.  Compose
# bind mounts may arrive owned by an arbitrary host UID; chown is intentionally
# limited to the configured durable data directory, never the application code.
DATA_DIR="${LEGAL_PLATFORM_DATA_DIR:-/app/storage}"
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR/db" "$DATA_DIR/files"
    chown -R appuser:appgroup "$DATA_DIR"
    exec setpriv --reuid=appuser --regid=appgroup --init-groups "$@"
fi

mkdir -p "$DATA_DIR/db" "$DATA_DIR/files"

# Execute application
exec "$@"
