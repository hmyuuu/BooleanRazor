# Frozen reblinded benchmark protocol

Status: proposer-safe protocol freeze. No public training row, baseline outcome,
hidden mapping, generator, secret seed, complete table, or sealed metric was
available when this file and the baseline source were committed.

## Entry gate

An experiment is eligible only when its hypothesis, allowed research lane,
fixed hyperparameter grid, software/source versions, algorithm seed rule,
resource card, and synthetic-test-only code already exist in a clean commit.
That commit must precede the experiment’s first access to the public bundle.
The custodian records both hashes.

The predeclared lanes are BDD ordering and XAG rewriting, bounded exact SAT,
structural arithmetic primitives, and TT/MPS table completion followed by the
common XAG backend. The lane list is not an experiment proposal. Each proposer
must state a falsifiable mechanism and fixed grid without public row bytes,
baseline results, or sealed results.

Only after the algorithm commit is frozen may the custodian mount the exact
content-addressed directory through `OCCAM_REBLIND_PUBLIC_ROOT`. No manual or
automated code, hypothesis, grid, feature, seed, or selection-rule change is
allowed after any sealed aggregate feedback. A changed proposal is a new study
and requires a newly committed benchmark decided before access.

## Visible-only selection and final fit

Selection uses five folds formed solely from visible training rows. The
predeclared algorithm seed deterministically assigns a canonical input row to a
fold; all model choice, early stopping, thresholding, rank/order choice, and
rewrite choice uses only these folds. Exact-row validation accuracy is the
selection objective; gates break an exact accuracy tie. A remaining tie uses
the lexicographically smaller canonical configuration record.

After selection, run one final fit on all visible rows. Restore every observed
output exactly before circuit extraction. Do not inspect an unobserved label,
family identity, generator identity, secret seed, hidden mapping, complete
table, or evaluator-derived field. Per-bit accuracy may be reported as a
diagnostic but never replaces exact-row selection.

## Frozen blind baselines

Both comparators have `method_version=1`, `blind=true`, repeat `0`, and are
retained regardless of their results.

- `zero-fill`: copy every observation and emit the all-zero vector elsewhere.
- `hamming-1nn`: copy the observation minimizing Hamming distance, then numeric
  input value, then original visible-row index.

Both enumerate the complete domain, restore all observations, synthesize shared
ROBDD/XAG circuits in grouped order and operand-interleaved order, verify each
against the completed table, and retain the lower reachable XOR-plus-AND gate
count. Grouped order wins an exact gate tie. The Hamming implementation is the
frozen O(input_bits × 2^input_bits) multi-source transform, not a
training_rows × 2^input_bits scan.

The execution matrix is later formed without opening `train.csv`: exactly
`{zero-fill,hamming-1nn} × 180 opaque IDs`, sorted by `(method,dataset_id)`.
Each row uses tier `n=<input_bits/2>`, the manifest’s observed fraction,
timeout `300`, one declared local hardware card, and
`SHA256(COMMITMENT || method || opaque_id)` over the UTF-8 text as the
lowercase algorithm seed.

## Frozen design and execution provenance

A tracked JSON benchmark declaration is a provenance-free canonical design spec
with exactly `schema_version` and `cells`. It never attempts to hash the commit
that contains itself. Every cell has exactly `cell_id` and `params`; the latter
has the canonical string fields `comparison_id`, `role`, `method`,
`method_version`, `blind`, `evaluation_scope`, `hardware`, `dataset_id`, `tier`,
`observation_fraction`, `algorithm_seed`, `repeat`, and `timeout_seconds`.
`comparison_id=cell_id`, `blind=true`, and
`evaluation_scope=visible_cv_only`. A generic candidate role may declare any
nonblank method and version; the two frozen-method restrictions apply only to
the canonical baseline matrix.

The ignored execution `RUN_ROOT/run_spec.json` adds one top-level `provenance`
object to that exact design projection. Its fields are exactly
`source_commit`, `runner_commit`, `tree_digest`, `image_sha256`, and `compiler_digest`.
For a local run, the worktree is clean including untracked files,
`source_commit=runner_commit=HEAD`, `image_sha256=none`, and `tree_digest` is
the SHA-256 of the raw bytes from:

```bash
git ls-tree -rz --full-tree HEAD
```

A container run instead supplies a canonical, independently checked provenance
JSON whose five values equal the run spec. Image verification occurs before
runner invocation; the runner records that result and does not claim to
measure its own container.

## Timing and hardware

Every candidate and matched baseline cell has a declared hard wall cap in
`(0,300]` seconds; the frozen baseline value is `300`. The monotonic deadline
includes child startup. The runner reserves bounded termination grace inside
the declared cap, sends `SIGTERM`, sends `SIGKILL` no later than the deadline,
and reaps the process group. A timeout records the declared cap as its censored
elapsed value and separately records measured post-deadline cleanup.
Compilation, dependency installation, environment construction, archive
transfer, and input staging occur before the clock. Parsing visible input,
training/completion, model selection, the final fit, observation restoration,
ROBDD construction, XAG extraction/rewrite, verification, serialization, and
metrics emission occur inside the clock.

Local and HPC executions use explicit immutable hardware cards. A comparison is
valid only when candidate and each baseline have identical cards, timeout
semantics, runner/compiler digests, concurrency policy, and measurement scope.
GPU/TN candidates use the predeclared matched A800 card; CPU comparisons use the
single local card declared by the matrix. Compilation time is reported
separately and is never subtracted from in-cap learner work after staging.

Terminal states are `SUCCESS`, `TIMEOUT`, `OOM`, `NONZERO_EXIT`,
`INVALID_METRICS`, `VERIFIER_FAILED`, `VERIFIER_NOT_RUN`, `CANCELLED`, and
`MISSING_SUCCESS_MANIFEST`. Failure is retained as evidence. Unavailable values
are the literal `none`; blank fields are invalid.

Verifier values are exactly `pass`, `fail`, and `not_run`. `SUCCESS` requires
`pass`, `VERIFIER_FAILED` requires `fail`, and every other terminal failure
requires `not_run`. A successful `train_exact` is exactly `1.0`; visible
accuracies are finite canonical decimals in [0,1], gates and peak memory are
canonical nonnegative integers, and elapsed seconds is a finite canonical
nonnegative decimal no larger than the cell timeout. Failed quality metrics and
candidate artifact remain `none`; elapsed time and peak memory may be `none`,
but are checked with the same semantics when present.

`run-experiment.py` requires `--run-root`, one declared `--cell-id`, its direct
in-cell `--metrics-json`, optional independently checked
`--container-provenance`, and a nonempty argv after `--`. It rejects an
existing cell directory and never overwrites evidence.

A zero-exit child must write exact-key visible-only metrics plus the fixed
regular files `completed-table.csv`, `circuit.txt`, and `artifact.json`.
The compact sorted-key artifact index binds the table and circuit filenames,
their SHA-256 digests, `schema_version=1`, and `equivalence=pass`. The metrics
table digest, both index digests, both stable file hashes, and the manifest’s
hash of the index must all agree. Symlinks, path races, missing or extra keys,
nonfinite/out-of-range accuracies, a nonexact training fit, and the
`bit_accuracy` alias are invalid.

## Metrics and inference

The primary per-instance metric is exact-row accuracy across all unobserved
assignments. Gates are considered only after an accuracy tie. The report also
includes:

- micro exact-row accuracy and micro bit accuracy over all unobserved rows;
- macro mean of per-instance exact-row accuracy;
- each instance’s reachable XOR-plus-AND gates and the sum across instances;
- elapsed seconds and peak memory under the declared card.

There is no invented “official aggregate.” Every table labels its aggregation
and denominator.

The five independent benchmark seeds are the clusters. Paired method
comparisons use exact seed-cluster tests over their five paired seed summaries.
Uncertainty uses a 95% cluster bootstrap that resamples the five seeds with
replacement and keeps all instances from a sampled seed together. The analysis
script, replicate count, and bootstrap RNG derivation are fixed before sealed
evaluation. No row-level bootstrap may masquerade as independent evidence.

## Evidence and gate phases

`research/check_gate.py --phase protocol` validates the reviewed survey, the
public manifest/commitment, canonical 360-row matrix plus digest, and the exact
header-only visible-results schema. `--phase baseline` additionally requires
one terminal blind result per matrix row and rejects any sealed field. Each
baseline `evidence_path` is repository-relative below `results/`, cannot escape
that root, names an existing JSON manifest, hashes exactly to
`manifest_sha256`, recursively contains no forbidden key, conforms to the
terminal-manifest schema, and agrees with the row’s provenance, status, and
metrics.

`--phase manifests --run <run> --expected-spec <path>` is read-only.
`<expected-spec>` must resolve to an existing file below this `research/`
directory. The native run layout is:

```text
<run>/run_spec.json
<run>/cells/<cell_id>/manifest.json
```

For a JSON expected spec, the checker canonicalizes the execution projection
`{"schema_version":1,"cells":[...]}` and requires those bytes to equal the
tracked design. Execution provenance is validated independently. For the
canonical `BASELINE_MATRIX.csv`, the native JSON `cells` array is semantically
the exact 360-row matrix: `cell_id=comparison_id`; `params` preserves every
matrix field verbatim and adds only `role=baseline`, `blind=true`, and
`evaluation_scope=visible_cv_only`. No empty or incomplete design is accepted.

Exactly one terminal JSON manifest must exist at the native path for every
expected cell, with no extra manifest. Every manifest binds the run-spec hash,
source provenance, row parameters, producer, argv, timestamps, stdout/stderr
hashes, scheduler metadata, cleanup, completed-table digest, circuit digest,
and artifact index. Runner logs use
`SHA256(frame(stdout) || frame(stderr))`, where each frame is an
eight-byte unsigned big-endian length followed by the raw bytes. Runner scheduler fields
are all `none`; scheduler-materialized evidence instead has empty argv,
unavailable timestamps, and populated raw-accounting fields. Successful cells
require `verifier=pass`; failed cells retain terminal evidence and use `none`
for all unavailable candidate quality and artifact fields.

For a Slurm task killed before runner evidence is written,
`materialize-slurm-failures.py` consumes separately captured raw parsable
accounting with the exact header:

```text
JobIDRaw|State|ExitCode|MaxRSS|ElapsedRaw
```

The capture uses `sacct --units=K`. One unique root allocation row
`<job-id>_<one-based-index>` is required per ordered cell; uniquely named
`.batch` and `.extern` rows may contribute to the maximum KiB observation.
`MaxRSS` is blank or a canonical integer followed by `K`; decimal and other
units are rejected. The complete raw bytes and exact
`RUN_ROOT/slurm-<job-id>_<one-based-index>.out` are hashed. Pending, unknown,
duplicate, incomplete, inconsistent, or log-less evidence fails before any
manifest is written. The materializer can emit only `TIMEOUT`, `OOM`,
`NONZERO_EXIT`, `CANCELLED`, or `MISSING_SUCCESS_MANIFEST`; it never emits
`SUCCESS`. The stable top-level harness remains unchanged, and the actual raw
capture integration is deferred to Task 14 resource-card ratification.

The visible-results schema is:

```text
comparison_id,role,method,method_version,blind,evaluation_scope,source_commit,runner_commit,tree_digest,image_sha256,compiler_digest,hardware,dataset_id,tier,observation_fraction,algorithm_seed,repeat,timeout_seconds,status,exit_code,timed_out,train_exact,visible_cv_exact,visible_cv_bit_accuracy,gates,elapsed_seconds,peak_memory_kib,verifier,artifact_sha256,manifest_sha256,evidence_path
```

`evaluation_scope` is always `visible_cv_only`. No sealed accuracy, test
accuracy, evaluator label, hidden family, or official aggregate is permitted.

## Claims boundary

ABC, CUDD, and Espresso were not installed or reproduced at protocol freeze.
Accordingly, the strongest permitted result is a matched claim against each
complete frozen baseline curve, supported by the seed-cluster analysis. A
“100× versus SOTA” claim is prohibited unless a later, separately frozen study
first reproduces the named external baseline under matched conditions.
