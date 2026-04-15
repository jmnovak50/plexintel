#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from api.db.schema import ensure_app_schema
from api.services.digest_service import run_scheduled_digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scheduled PlexIntel digest emails.")
    parser.add_argument("--force", action="store_true", help="Send immediately even if digest sending is disabled.")
    parser.add_argument("--triggered-by", default="script", help="Identifier stored with the digest run.")
    args = parser.parse_args()

    ensure_app_schema()
    result = run_scheduled_digest(force=args.force, triggered_by=args.triggered_by)
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
