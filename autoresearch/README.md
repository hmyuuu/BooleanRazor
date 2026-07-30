# Five-minute autoresearch protocol

Each hypothesis gets a fresh worktree from the latest accepted commit and a
root log. Run this from the accepted checkout:

```bash
experiment_id=${1:?supply an opaque experiment ID}
accepted_commit=$(git rev-parse HEAD)
git worktree add "../booleanrazor-exp-${experiment_id}" \
  -b "codex/booleanrazor-exp-${experiment_id}" "$accepted_commit"
cp autoresearch/LOG_TEMPLATE.md \
  "../booleanrazor-exp-${experiment_id}/LOG.md"
```

Never reuse a worktree for another hypothesis. Before attaching any data, fill
the hypothesis, parent commit and diff digest, permitted-data boundary, frozen
controls, command, seed, environment, hardware, and timeout in `LOG.md`.
Include that log in the synthetic-test-only algorithm commit. Record each later
run or decision in a separate evidence commit so a clean
`git status --porcelain=v1` can be bound without discarding failures.

The accepted branch advances only through a reviewed promotion decision. A
failed worktree remains evidence until its manifest and lessons are represented
in the canonical research trace.

## Native bounded runner

Build the exact binary first, then invoke the runner with a frozen native run
root. The child runs in its cell directory, so the repository binary, public
root, output directory, and metrics path passed to the child must all be
absolute.

```bash
repo_root=$(git rev-parse --show-toplevel)
run_id=${2:?supply a frozen run ID}
cell_id=${3:?supply a frozen cell ID}
opaque_id=${4:?supply an opaque instance ID}
algorithm_seed=${5:?supply a 64-lowercase-hex seed}
run_root="$repo_root/results/$run_id"
public_root=${OCCAM_REBLIND_PUBLIC_ROOT:?supply an absolute reviewed public root}
cell_dir="$run_root/cells/$cell_id"

cargo build --locked --release --manifest-path "$repo_root/Cargo.toml"
python "$repo_root/scripts/run-experiment.py" \
  --run-root "$run_root" \
  --cell-id "$cell_id" \
  --metrics-json "$cell_dir/metrics.json" -- \
  "$repo_root/target/release/occam-circuit-hmyuuu" \
  learn-care "$public_root" "$opaque_id" "$cell_dir" \
  --folds 5 --seed "$algorithm_seed" \
  --policy reuse-sibling --max-order-evals 32
```

The run root must already contain the canonical frozen run specification
required by `scripts/run-experiment.py`. The runner creates the cell directory,
captures logs and resource evidence, enforces the 300-second wall including
startup and cleanup, validates the metrics/artifact binding, and writes one
terminal manifest.

Runner terminal states preserve the verifier distinction:

| Status | Meaning | Exit |
| --- | --- | ---: |
| `SUCCESS` | Candidate retained; verifier pass reported | 0 |
| `VERIFIER_FAILED` | Candidate retained; verifier failed | 66 |
| `VERIFIER_NOT_RUN` | Candidate retained; verifier absent | 67 |
| `INVALID_METRICS` | Output contract invalid; no candidate claim | 65 |
| Other failure/timeout | Classified terminal observation | nonzero |

Never rewrite `VERIFIER_NOT_RUN` as success. A runner-level verifier field is
not a substitute for the immutable official record created by
`scripts/record-verification.py`.

## Proposal/evaluator firewall

The three roles have disjoint evidence access:

1. The **custodian** generates the sealed complete tables, opaque IDs, public
   training rows, and checksums. Per-example mismatches and source-family
   labels remain in an ignored, custodian-only results root.
2. The **proposer** receives only the reviewed contract, public rows, test
   domain policy, and aggregate lessons. It writes a completed table and
   circuit without access to sealed rows, mappings, or evaluator diagnostics.
3. The **evaluator** checks the frozen candidate and returns only
   `experiment_id`, train exact accuracy, sealed exact accuracy, bit accuracy,
   reachable gates, elapsed time, peak memory, and terminal status.

Before transfer, recursively inspect the proposer bundle. Reject it if a path,
CSV header, or JSON key contains `family`, `generator`, `ground_truth`,
`test_outputs`, or a sealed digest. Values outside the reviewed return
contract, including per-example failures and family labels, never cross back
to the proposer.

## Evidence and decision discipline

- Freeze the benchmark, folds, baselines, metric schema, seed, timeout, and
  permitted data before proposing the algorithm.
- Preserve failed, timed-out, invalid, tied, rejected, and superseded runs.
- A result becomes evidence only with its source revision, clean tree digest,
  environment or image digest, run spec, artifacts, logs, timing, memory, and
  verifier state.
- Synthetic exactness can advance a method only to public-candidate
  consideration. It cannot establish visible or sealed accuracy.
- Run `scripts/check-promotion.py` on a canonical request; do not self-promote
  in prose or by editing a leaderboard.

`materialize-slurm-failures.py` may fill a missing terminal manifest only from
separately captured raw Slurm accounting and the exact task log. It never
creates a successful observation. Slurm remains unavailable until a human
ratifies the exact promoted cell and resource card.
