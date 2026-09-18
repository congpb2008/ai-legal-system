"""Legal Knowledge Platform — canonical entrypoint.

Usage:
    python -m legal_platform [--host HOST] [--port PORT]

Environment variables:
    LEGAL_PLATFORM_HOST  — host to bind to (default: 0.0.0.0)
    LEGAL_PLATFORM_PORT  — port to listen on (default: 8080)

Examples:
    python -m legal_platform
    python -m legal_platform --host 127.0.0.1 --port 9000
    LEGAL_PLATFORM_HOST=127.0.0.1 LEGAL_PLATFORM_PORT=9000 python -m legal_platform
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional


def main(argv: Optional[list[str]] = None) -> None:
    """Start the Legal Knowledge Platform API server.

    Args:
        argv: command-line arguments (defaults to sys.argv[1:]).
    """
    parser = argparse.ArgumentParser(
        description="Legal Knowledge Platform — evidence-grounded legal Q&A",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LEGAL_PLATFORM_HOST", "0.0.0.0"),
        help=(
            "Host to bind to "
            "(default: 0.0.0.0, env: LEGAL_PLATFORM_HOST)"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LEGAL_PLATFORM_PORT", "8080")),
        help=(
            "Port to listen on "
            "(default: 8080, env: LEGAL_PLATFORM_PORT)"
        ),
    )

    args = parser.parse_args(argv)

    # Late import so --help is fast even if platform deps are missing
    from legal_platform.api.server import PlatformAPI

    from legal_platform.operations import installation_lock
    from legal_platform.paths import data_root
    with installation_lock(data_root()):
        api = PlatformAPI(host=args.host, port=args.port)
        try:
            api.start()
        except KeyboardInterrupt:
            print("\nShutdown requested.")
        finally:
            api.stop()


if __name__ == "__main__":
    main()