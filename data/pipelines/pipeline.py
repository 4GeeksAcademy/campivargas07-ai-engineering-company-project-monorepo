#!/usr/bin/env python3
"""
pipeline.py — Brasaland · Inventory Health Business Performance Pipeline CLI Entrypoint

Executes the Prefect 3 business performance pipeline directly as a script.

Usage:
    uv run --project services/api python data/pipelines/pipeline.py [--full-reconciliation] [--db-url URL]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Sequence

# Ensure monorepo root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from data.pipelines.inventory_health.flow import inventory_health_business_flow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline_cli")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Brasaland Inventory Health Business Performance Pipeline (Prefect 3)"
    )
    parser.add_argument(
        "--full-reconciliation",
        action="store_true",
        default=False,
        help="Execute full reconciliation across all historical ledger movements regardless of watermark.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (defaults to DATABASE_URL or TEST_DATABASE_URL environment variable).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable debug logging output.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting Brasaland Inventory Health Business Pipeline...")
    logger.info(
        "Configuration: full_reconciliation=%s, db_url=%s",
        args.full_reconciliation,
        "***" if args.db_url else "(from env)",
    )

    try:
        result = inventory_health_business_flow(
            db_url=args.db_url,
            is_full_reconciliation=args.full_reconciliation,
        )

        status = result.get("status")
        run_id = result.get("flow_run_id")
        snapshots_loaded = result.get("snapshots_loaded", 0)
        quarantined = result.get("records_quarantined", 0)
        events_read = result.get("events_read", 0)

        print("\n" + "=" * 60)
        print("BRASALAND INVENTORY HEALTH PIPELINE — RUN SUMMARY")
        print("=" * 60)
        print(f"Flow Run ID:         {run_id}")
        print(f"Status:              {status}")
        print(f"Source Events Read:  {events_read}")
        print(f"Snapshots Loaded:    {snapshots_loaded}")
        print(f"Records Quarantined: {quarantined}")
        if result.get("metrics"):
            print(f"Aggregated Metrics:  {result.get('metrics')}")
        print("=" * 60 + "\n")

        if status == "COMPLETED":
            logger.info("Pipeline executed successfully.")
            return 0
        elif status == "SKIPPED":
            logger.warning("Pipeline execution was skipped (concurrency lock active).")
            return 0
        else:
            logger.error("Pipeline finished with non-successful status: %s", status)
            return 1

    except Exception as exc:
        logger.exception("Pipeline execution failed with unhandled exception: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
