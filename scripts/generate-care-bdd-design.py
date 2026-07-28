#!/usr/bin/env python3
"""Generate the proposer-safe 180-cell care-BDD design from tracked metadata."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reblind/manifest.csv"
COMMITMENT = ROOT / "reblind/COMMITMENT.txt"
OUTPUT = ROOT / "research/CARE_BDD_DESIGN.json"
MANIFEST_FIELDS = [
    "opaque_id",
    "input_bits",
    "output_bits",
    "train_rows",
    "test_policy",
    "observed_fraction",
    "public_sha256",
]
HEX_64 = re.compile(r"[0-9a-f]{64}")
METHOD = "care-bdd-reuse-sibling"


def design() -> dict[str, object]:
    commitment = COMMITMENT.read_text(encoding="ascii")
    if not commitment.endswith("\n") or not HEX_64.fullmatch(commitment[:-1]):
        raise ValueError("COMMITMENT.txt must be one lowercase 64-hex line")
    commitment = commitment[:-1]

    with MANIFEST.open(encoding="utf-8", newline="") as manifest_file:
        manifest_text = manifest_file.read()
    reader = csv.DictReader(io.StringIO(manifest_text))
    if reader.fieldnames != MANIFEST_FIELDS:
        raise ValueError("manifest.csv has the wrong header")
    rows = list(reader)
    if len(rows) != 180:
        raise ValueError("manifest.csv must contain exactly 180 rows")
    if len({row["opaque_id"] for row in rows}) != len(rows):
        raise ValueError("manifest.csv contains duplicate opaque IDs")

    cells: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: item["opaque_id"]):
        opaque_id = row["opaque_id"]
        input_bits = int(row["input_bits"])
        if input_bits % 2 != 0:
            raise ValueError(f"{opaque_id} has an odd input width")
        cell_id = f"care-bdd-{opaque_id}"
        algorithm_seed = hashlib.sha256(
            f"{commitment}{METHOD}{opaque_id}".encode()
        ).hexdigest()
        cells.append(
            {
                "cell_id": cell_id,
                "params": {
                    "algorithm_seed": algorithm_seed,
                    "blind": "true",
                    "comparison_id": cell_id,
                    "dataset_id": opaque_id,
                    "evaluation_scope": "visible_cv_only",
                    "hardware": "local-darwin-arm64-rust-1.93.0",
                    "method": METHOD,
                    "method_version": "1",
                    "observation_fraction": row["observed_fraction"],
                    "repeat": "0",
                    "role": "candidate",
                    "tier": f"n={input_bits // 2}",
                    "timeout_seconds": "300",
                },
            }
        )
    return {"cells": cells, "schema_version": 1}


def main() -> None:
    raw = (
        json.dumps(design(), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    OUTPUT.write_bytes(raw)


if __name__ == "__main__":
    main()
