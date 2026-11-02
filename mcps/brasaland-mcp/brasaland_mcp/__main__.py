"""Entrypoint: `uv run python -m brasaland_mcp` (or `brasaland-mcp` script)."""

from __future__ import annotations

import logging
import sys

from .app import serve
from .config import ConfigError, load_settings


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    serve(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
