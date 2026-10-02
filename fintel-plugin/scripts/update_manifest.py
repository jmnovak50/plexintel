#!/usr/bin/env python3
"""Add or replace one FIntel release in the Jellyfin repository manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PLUGIN_GUID = "d84462bb-88da-4af1-952c-c10887752a28"
TARGET_ABI = "12.1.0.0"
CHECKSUM_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--checksum", required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--changelog", required=True)
    return parser.parse_args()


def version_key(value: str) -> tuple[int, int, int, int]:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid four-part plugin version: {value}")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def main() -> None:
    args = parse_args()
    version_key(args.version)
    if not CHECKSUM_PATTERN.fullmatch(args.checksum):
        raise ValueError("Jellyfin checksum must be a 32-character MD5 hex digest")
    if not args.source_url.startswith("https://github.com/") or not args.source_url.endswith(".zip"):
        raise ValueError("sourceUrl must be an HTTPS GitHub ZIP URL")

    packages = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else []
    if not isinstance(packages, list):
        raise ValueError("Jellyfin repository manifest must be a JSON array")

    plugin = next((entry for entry in packages if entry.get("guid") == PLUGIN_GUID), None)
    if plugin is None:
        plugin = {
            "guid": PLUGIN_GUID,
            "name": "FIntel",
            "description": (
                "Adds user-specific FIntel movie rankings to Jellyfin's native More Like This "
                "results without modifying Jellyfin clients."
            ),
            "overview": "Personalized movie similarity from the FIntel recommendation service",
            "owner": "FIntel",
            "category": "General",
            "versions": [],
        }
        packages.append(plugin)

    release = {
        "version": args.version,
        "changelog": args.changelog,
        "targetAbi": TARGET_ABI,
        "sourceUrl": args.source_url,
        "checksum": args.checksum.lower(),
        "timestamp": args.timestamp,
    }
    versions = [entry for entry in plugin.get("versions", []) if entry.get("version") != args.version]
    versions.append(release)
    plugin["versions"] = sorted(versions, key=lambda entry: version_key(entry["version"]), reverse=True)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(packages, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
