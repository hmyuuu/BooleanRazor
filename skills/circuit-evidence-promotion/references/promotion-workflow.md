# Promotion workflow

Use this workflow to validate an existing result. Do not modify the method or
rerun an altered hypothesis while promoting it.

## Track ceilings

| Track | Highest positive decision |
| --- | --- |
| `disclosed_control` | `promote_control` |
| `synthetic` | `advance_public_candidate` |
| `blind_visible` | `freeze_candidate` |
| `sealed_confirmation` | `promote_blind_result` |

No checker result may skip these ceilings. A disclosed control, synthetic
advance, or visible freeze is not a promoted blind result.

## Current repository status

Recheck the evidence files before acting. At this deliverability snapshot,
`research/BASELINES.csv` has no executed public rows and sealed results are
absent. The current blind-promotion decision is therefore `blocked`. Historical
official-Julia evidence covers disclosed v1 controls on its recorded branch
only; it is not current blind evidence.

All command blocks below assume:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
make -C "$REPO_ROOT" setup
test -x "$REPO_ROOT/.venv/bin/python"
```

## 1. Validate the native run

Use the tracked expected design and the complete run root:

```bash
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/research/check_gate.py" \
  --phase manifests \
  --run "$RUN_ROOT" \
  --expected-spec "$EXPECTED_DESIGN"
```

Require every `run_spec.json` cell to have exactly one terminal manifest. Do
not filter failed cells before validation.

Candidate-bearing states are:

| State | Verifier field | Meaning |
| --- | --- | --- |
| `SUCCESS` | `pass` | Valid candidate artifacts; the child metrics reported a verifier pass |
| `VERIFIER_NOT_RUN` | `not_run` | Valid candidate artifacts; official proof absent |
| `VERIFIER_FAILED` | `fail` | Valid candidate artifacts; official check failed |

Only `SUCCESS` is a successful runner result. Candidate-bearing states must
bind `train_exact=1.0`, internal exhaustive equivalence, canonical artifacts,
and their transitive hashes. Other terminal states retain no candidate-quality
claim. Even `SUCCESS` is not the immutable official proof consumed by
promotion; Step 3 must create and bind `official-verification.json`.

## 2. Prove deterministic pairs

Run each baseline and candidate twice in fresh cell directories. Pair each
left repeat with exactly one right repeat. Require:

- identical source commit, tree digest, dataset identity, method, quality, and
  gate count;
- byte-identical `completed-table.csv`, `circuit.txt`, and `artifact.json`;
- a complete pair partition of every candidate-bearing manifest in the native
  run.

Preserve unequal pairs and terminal failures. They are rejection evidence, not
rows to omit.

## 3. Create official records inside the custodian boundary

The proposer must not execute this step, receive its arguments, inspect its
official dataset or sealed paths, or receive raw official/sealed digests.
Transfer immutable candidate evidence through the reviewed boundary and let
the authorized custodian execute:

```bash
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/record-verification.py" \
  --manifest "$MANIFEST" \
  --julia-bin "$JULIA_BIN" \
  --verify-jl "$VERIFY_JL" \
  --dataset "$DATASET" \
  --output "$OFFICIAL_RECORD"
```

Every argument must be an absolute, lexically normalized path with no symlink
component. The output must not exist. The command validates the candidate and
artifact index, invokes the fail-closed Julia wrapper, rechecks files against
replacement races, and atomically writes one canonical pass record. Any
failure leaves the pass record absent.

Create one record for the left endpoint of each deterministic pair. Keep raw
records, official inputs, sealed inputs, and their digests in custodian-owned
storage.

## 4. Build one canonical request

Place the request beside its evidence root. It has exactly:

```text
schema_version
track
candidate_evidence
deterministic_pairs
official_verifications
frozen_comparison
sealed_results
```

Use unique relative non-symlink paths. Use the literal string `none` when a
field is unavailable or inapplicable. `sealed_results` must be `none` outside
`sealed_confirmation`.

The request must name the whole native run, not a favorable subset. Its frozen
comparison must bind the predeclared visible design, exact baseline/candidate
role partition, expected IDs, frozen candidate, and rule
`accuracy_first_then_gates`.

Any non-absent comparison also needs a separately selected canonical
`--trust-policy`. The custodian policy binds:

- the exact promotion-request bytes;
- the frozen-comparison bytes;
- the exact unique set of official-record byte digests;
- the sealed-result bytes for `sealed_confirmation`, otherwise literal
  `none`.

The checker verifies byte bindings only. Operator identity, authority,
selection, chronology, and cryptographic authentication remain external
custodian duties.

## 5. Produce an immutable decision

Run this only where the request, official records, policy, and any sealed result
are authorized:

```bash
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/check-promotion.py" \
  --request "$PROMOTION_REQUEST" \
  --output "$PROMOTION_DECISION" \
  --trust-policy "$TRUST_POLICY"
```

For the all-`none` blocked request, omit `--trust-policy`. Never overwrite an
existing decision; use a new evidence root for a new request.

Interpret the result exactly:

| Decision | Meaning |
| --- | --- |
| `blocked` | Required evidence is absent or unavailable; no eligibility violation is established |
| `reject` | Supplied evidence violates an eligibility or binding requirement |
| `no_change` | Evidence is valid, but the frozen candidate is not strictly better under exact-row accuracy then gates |
| `promote_control` | Positive disclosed-control result only |
| `advance_public_candidate` | Positive synthetic result; proceed only to public-candidate consideration |
| `freeze_candidate` | Positive visible-only selection; no sealed-performance claim |
| `promote_blind_result` | Positive sealed confirmation at the final track ceiling |

For sealed promotion, require one uniform predeclared result mode:
`100x` against both baselines or scaling advantage against both baselines.
Never combine `100x` against one baseline with scaling advantage against the
other. Require the sealed baseline names to equal the methods in the actual
frozen baseline manifests, include failed cells in the normalized analysis,
and do not infer a family label.

## 6. Publish only permitted claims

Run:

```bash
make -C "$REPO_ROOT" report
make -C "$REPO_ROOT" report-check
```

Keep the immutable raw decision inside its authorized evidence boundary when
its input digest map is private. Return only the aggregate decision and fields
the reviewed boundary permits. Never copy a trust policy, sealed record,
official dataset path, private digest, per-example failure, family label, or
generator name into the proposer worktree or public report.

Update a leaderboard only after verifying its own schema, benchmark identity,
track requirement, and proof gate. A report update does not itself authorize a
leaderboard change.
