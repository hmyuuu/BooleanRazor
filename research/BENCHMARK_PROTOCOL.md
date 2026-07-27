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

## Timing and hardware

Every candidate and matched baseline cell has a hard 300-second wall cap.
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
one terminal blind result per matrix row and rejects any sealed field.

`--phase manifests --run <run>` is read-only. It joins `<run>/spec.csv` to
exactly one `cells/**/manifest.csv` record per comparison ID, checks provenance,
terminal status, evidence hashes, verifier state, and absence of sealed fields.
A successful cell requires `verifier=pass` and a valid artifact hash. Failed
cells retain provenance and evidence but set unavailable candidate metrics and
artifact hash to `none`.

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
