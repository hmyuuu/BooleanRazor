from __future__ import annotations

import csv
import hashlib
import io
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN = Path(__file__).with_name("CARE_BDD_DESIGN.json")
MANIFEST = ROOT / "reblind/manifest.csv"
COMMITMENT = ROOT / "reblind/COMMITMENT.txt"
PARAM_FIELDS = {
    "comparison_id",
    "role",
    "method",
    "method_version",
    "blind",
    "evaluation_scope",
    "hardware",
    "dataset_id",
    "tier",
    "observation_fraction",
    "algorithm_seed",
    "repeat",
    "timeout_seconds",
}


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


class CareBddDesignTests(unittest.TestCase):
    def test_design_is_canonical_provenance_free_and_exactly_covers_manifest(self) -> None:
        raw = DESIGN.read_bytes()
        design = json.loads(raw)
        self.assertEqual(raw, canonical_json_bytes(design))
        self.assertEqual(set(design), {"schema_version", "cells"})
        self.assertEqual(design["schema_version"], 1)
        self.assertEqual(len(design["cells"]), 180)

        manifest = list(
            csv.DictReader(io.StringIO(MANIFEST.read_text(encoding="utf-8")))
        )
        self.assertEqual(len(manifest), 180)
        by_id = {row["opaque_id"]: row for row in manifest}
        commitment = COMMITMENT.read_text(encoding="ascii").strip()
        seen: set[str] = set()
        for cell in design["cells"]:
            self.assertEqual(set(cell), {"cell_id", "params"})
            params = cell["params"]
            self.assertEqual(set(params), PARAM_FIELDS)
            opaque_id = params["dataset_id"]
            self.assertIn(opaque_id, by_id)
            self.assertNotIn(opaque_id, seen)
            seen.add(opaque_id)
            row = by_id[opaque_id]
            self.assertEqual(cell["cell_id"], f"care-bdd-{opaque_id}")
            self.assertEqual(params["comparison_id"], cell["cell_id"])
            self.assertEqual(params["role"], "candidate")
            self.assertEqual(params["method"], "care-bdd-reuse-sibling")
            self.assertEqual(params["method_version"], "1")
            self.assertEqual(params["blind"], "true")
            self.assertEqual(params["evaluation_scope"], "visible_cv_only")
            self.assertEqual(
                params["tier"], f"n={int(row['input_bits']) // 2}"
            )
            self.assertEqual(
                params["observation_fraction"], row["observed_fraction"]
            )
            self.assertEqual(
                params["algorithm_seed"],
                hashlib.sha256(
                    f"{commitment}care-bdd-reuse-sibling{opaque_id}".encode()
                ).hexdigest(),
            )
            self.assertEqual(params["repeat"], "0")
            self.assertEqual(params["timeout_seconds"], "300")
        self.assertEqual(seen, set(by_id))

    def test_design_does_not_embed_execution_or_provenance_fields(self) -> None:
        design = json.loads(DESIGN.read_bytes())
        serialized = canonical_json_bytes(design).decode()
        for forbidden in (
            "source_commit",
            "runner_commit",
            "tree_digest",
            "image_sha256",
            "compiler_digest",
            "train_rows",
            "public_sha256",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
