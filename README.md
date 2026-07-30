# BooleanRazor

BooleanRazor is a standalone research workspace for learning and synthesizing
small exact Boolean circuits from partial observations. Accuracy is the primary
objective. Reachable gate count under the challenge's one-gate XOR metric is
secondary and is compared only after exactness.

Start with the generated [offline research report](reports/site/index.html).
Its landing page summarizes the answer and its experiments page shows the
evidence-backed lineage of every recorded research round, including dead ends
and turning points.

## Current scientific answer

Blind advantage has not been demonstrated. The content-addressed public
training archive is not mounted, the frozen public baseline/candidate matrix
has not run, and sealed confirmation is absent.

ProjectedSupportBDD R2 is the strongest recorded *internal synthetic* result:
104,857/104,857 exact rows and 72 reachable gates on its bound synthetic
fixture, versus 0/104,857 and 34,917 gates for that round's
GreedyExactConflict control. This is a useful research turning point, not a
public, blind, sealed, or global SOTA claim.

The disclosed v1 mappings remain exact constructive controls:

| Instance | Function | Reachable gates | Claim boundary |
| --- | --- | ---: | --- |
| A | `x + y` | 37 | Disclosed control; not a minimality proof |
| B | `abs(x - y)` | 49 | Disclosed control; not a minimality proof |
| C | `x * y` | 168 | Disclosed control; not a minimality proof |
| D | `x² + y²` | 127 | Disclosed control; not a minimality proof |

## Evidence tracks

The two user-facing tracks are implemented as four claim ceilings:

| Track | What it may use | Maximum decision |
| --- | --- | --- |
| `disclosed_control` | Known v1 mappings and datasets | `promote_control` |
| `synthetic` | Generated development fixtures | `advance_public_candidate` |
| `blind_visible` | Reviewed public bundle only | `freeze_candidate` |
| `sealed_confirmation` | Frozen candidate at the custodian boundary | `promote_blind_result` |

The proposer never receives sealed rows, source-family or generator labels,
private digests, or per-example evaluator diagnostics.

## Architecture

```text
Rust exact core
  -> bounded experiment runner
  -> immutable Official Julia verification record
  -> evidence-bounded promotion decision
  -> canonical project evidence
  -> deterministic Markdown + offline web report
```

Internal exhaustive equivalence is produced by the Rust artifact path.
Official Julia verification is a separate, input-bound record. Neither a zero
exit nor a free-standing `verifier: "pass"` collapses those two authorities.

## Verification levels

| Level | Required evidence | Current blind state |
| --- | --- | --- |
| Visible training consistency | Exact restoration of visible rows | Infrastructure implemented; candidate absent |
| Internal exhaustive equivalence | `artifact.json` with `equivalence=pass` | Infrastructure implemented |
| Deterministic rerun | Byte-identical fresh artifacts | Required; pair absent |
| Official Julia verification | Immutable `official-verification.json` | Wrapper integrated; current blind record absent |
| Sealed confirmation | Frozen custodian/evaluator decision | Absent |

## Result status

| Scope | Status | What may be concluded |
| --- | --- | --- |
| Disclosed controls and exact infrastructure | Verified on main | Constructive control counts and implemented tools |
| Historical v1 Julia run | Verified branch-only | Official checks passed for disclosed v1 at its cited revision |
| GreedyExactConflict | Verified branch-only | Synthetic gate reduction; no exact-row gain |
| ProjectedSupportBDD R2 | Verified branch-only | Current internal synthetic frontier |
| Tensor-network pilot | Verified branch-only | Deterministic fully observed parity pipeline only |
| Fair scheduler R1 | Rejected | Deterministic tie; no quality improvement |
| Public baseline and visible-blind study | Blocked | Public archive/results absent |
| Sealed confirmation and blind advantage | Absent | No claim permitted |

## Setup and audit

```bash
make setup
make skills
make test
make report-check
```

`make report` regenerates the HTML and concise Markdown views from
`reports/data/project.json`; `make report-check` rejects stale output,
unreplayable claims, remote runtime dependencies, and broken internal links.

## Command matrix

Disclosed controls:

```bash
cargo run --locked --release --bin occam-circuit-hmyuuu -- \
  solve-v1 "$DATA_ROOT" "$OUTPUT_ROOT"
```

Frozen public baseline:

```bash
cargo run --locked --release --bin occam-circuit-hmyuuu -- \
  frozen-baseline "$PUBLIC_ROOT" "$OPAQUE_ID" "$OUTPUT_DIR" \
  --method zero-fill --metrics-json "$OUTPUT_DIR/metrics.json"
```

Visible-only care-BDD candidate:

```bash
cargo run --locked --release --bin occam-circuit-hmyuuu -- \
  learn-care "$PUBLIC_ROOT" "$OPAQUE_ID" "$OUTPUT_DIR" \
  --folds 5 --seed "$ALGORITHM_SEED" --policy reuse-sibling \
  --max-order-evals 32
```

Bounded SAT resynthesis:

```bash
cargo run --locked --all-features --release \
  --bin occam-circuit-hmyuuu -- \
  resynthesize "$INPUT_CIRCUIT" "$OUTPUT_DIR" \
  --max-cut-inputs 6 --deadline-seconds 285 \
  --metrics-json "$OUTPUT_DIR/metrics.json"
```

Native five-minute runner. All child arguments are absolute because the child
runs in its cell directory:

```bash
repo_root=$(git rev-parse --show-toplevel)
run_root="$repo_root/results/$RUN_ID"
"$repo_root/.venv/bin/python" "$repo_root/scripts/run-experiment.py" \
  --run-root "$run_root" --cell-id "$CELL_ID" \
  --metrics-json "$run_root/cells/$CELL_ID/metrics.json" -- \
  "$repo_root/target/release/occam-circuit-hmyuuu" \
  learn-care "$PUBLIC_ROOT" "$OPAQUE_ID" \
  "$run_root/cells/$CELL_ID" --folds 5 \
  --seed "$ALGORITHM_SEED" --policy reuse-sibling --max-order-evals 32
```

Fail-closed Julia wrapper:

```bash
"$REPO_ROOT/scripts/verify-julia.sh" \
  "$JULIA_BIN" "$VERIFY_JL" "$CIRCUIT" "$DATASET" \
  "$EXPECTED_GATES" "$INSTANCE"
```

Immutable official-verification record:

```bash
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/record-verification.py" \
  --manifest "$MANIFEST" --julia-bin "$JULIA_BIN" \
  --verify-jl "$VERIFY_JL" --dataset "$DATASET" \
  --output "$OFFICIAL_RECORD"
```

Evidence-bounded promotion decision:

```bash
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/check-promotion.py" \
  --request "$PROMOTION_REQUEST" --output "$PROMOTION_DECISION"
```

## Navigate the repository

- [`docs/STATUS.md`](docs/STATUS.md) — current answer, blockers, and next gate.
- [`docs/METHODS.md`](docs/METHODS.md) — methods and later optimization paths.
- [`docs/EXPERIMENT_INDEX.md`](docs/EXPERIMENT_INDEX.md) — compact research
  trace.
- [`research/EVIDENCE_LEDGER.md`](research/EVIDENCE_LEDGER.md) — proof and
  limitations behind each claim.
- [`AGENTS.md`](AGENTS.md) — activity/evidence/verifier decision router.
- [`autoresearch/README.md`](autoresearch/README.md) — bounded research cells.
- [`reblind/README.md`](reblind/README.md) — public/sealed data boundary.
- [`docs/handoff/SESSION_HANDOFF.md`](docs/handoff/SESSION_HANDOFF.md) —
  continuation state.
- [`docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md`](docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md)
  — ratified scientific plan.

No public training archive, sealed rows, private custodian state, or cluster
authorization is bundled here. `hpccube` use requires separate human approval
of the exact revision, data boundary, environment, resource card, and output
paths.
