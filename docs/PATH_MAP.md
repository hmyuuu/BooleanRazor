# Path map

| Before migration | BooleanRazor |
| --- | --- |
| `tracks/qcs/solutions/hmyuuu/` | repository root |
| `tracks/qcs/solutions/hmyuuu/src/` | `src/` |
| `tracks/qcs/solutions/hmyuuu/tests/` | `tests/` |
| `tracks/qcs/solutions/hmyuuu/research/` | `research/` |
| `tracks/qcs/solutions/hmyuuu/reblind/` | `reblind/` |
| `tracks/qcs/solutions/hmyuuu/autoresearch/` | `autoresearch/` |
| `tracks/qcs/solutions/hmyuuu/scripts/` | `scripts/` |
| `docs/superpowers/plans/2026-07-23-occam-circuit-rust-bdd-tn.md` | `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md` |
| `.knowledge/literature/boolean-logic-synthesis/` | `.knowledge/literature/boolean-logic-synthesis/` |
| `.knowledge/literature/mps-based-algorithm/` | `.knowledge/literature/mps-based-algorithm/` |
| harness Slurm adapters in `scripts/` | standalone `scripts/` |
| harness and cached workflow skills | vendored `skills/` |
| ignored Task 10 report | `docs/handoff/TASK_10_REPORT.md` |
| ignored Task 11/12 preflight | `docs/handoff/TASK_11_12_PREFLIGHT.md` |
| private custodian root | excluded; remains outside the repository |

Commands and documentation must use the standalone paths after migration. Do
not add compatibility symlinks back into the quantum.harness checkout.
