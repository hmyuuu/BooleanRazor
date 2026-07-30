# BooleanRazor evidence contract

Use this reference for every optimization hypothesis. Accuracy and evidence
eligibility are hard gates; gate count is a secondary optimization target.

## Evidence tracks

| Track | Permitted interpretation | Maximum positive decision |
| --- | --- | --- |
| `disclosed_control` | Constructive recovery of the disclosed v1 arithmetic controls | `promote_control` |
| `synthetic` | Internal method and pipeline evidence | `advance_public_candidate` |
| `blind_visible` | Selection using only the committed visible boundary | `freeze_candidate` |
| `sealed_confirmation` | Custodian confirmation of a previously frozen candidate | `promote_blind_result` |

Treat A=`x+y`, B=`abs(x-y)`, C=`x*y`, and D=`x²+y²` only as disclosed
controls. Never use their recovery, their labels, or their gate counts as
blind-learning evidence.

## Freeze before proposing

Freeze the survey, benchmark, folds, baselines, metric schema, seed policy,
completion policy, algorithm budget, and 300-second cell deadline before
proposing a method. Put these fields in the root `LOG.md` before implementation:

- branch, full parent and `HEAD`, and clean-tree status;
- one falsifiable hypothesis and one independent variable;
- permitted and forbidden data;
- frozen controls and comparator;
- expected failure signal and stopping rule;
- local or approved remote compute boundary.

Create a fresh worktree per hypothesis. Preserve its log and evidence even when
the hypothesis fails; do not recycle it for the next idea.

## Eligibility and scoring

Require all of the following before comparing quality:

1. `train_exact=1.0` on every visible training row;
2. exhaustive equality between the emitted XAG and its completed table over
   the declared input domain;
3. transitive agreement of run-spec, manifest, artifact, table, and circuit
   hashes;
4. two fresh deterministic builds with byte-identical completed table,
   circuit, and artifact index;
5. a terminal record that preserves the complete native run.

Rank eligible candidates lexicographically:

1. higher exact-row accuracy;
2. fewer reachable challenge-native XAG gates.

Bit accuracy, BDD node count, conventional AIG cost, tensor rank, and runtime
are diagnostics. A higher exact-row score wins regardless of gate count. Only
an exact-row tie reaches the gate comparison. XOR costs one gate and negation
is free.

Internal exhaustive equivalence proves only that the circuit implements the
candidate's completed table. It is not an official Julia pass and does not
show that unobserved predictions are correct.

## Method boundaries

- Use OxiDD only for reduced independent checks and ordering comparisons. Do
  not use it as the production learner.
- Admit a tensor-network proposal only after enumerating every prediction and
  passing it through the same Rust completed-table and XAG backend.
- Treat a SAT `UNSAT` result as proof only for the exact frozen encoding and
  bound. Preserve `Timeout` and `Unknown` as censored observations.
- Stop increasing one local SAT bound after two successive
  `Timeout`/`Unknown` outcomes.
- Do not change the evaluator, metric, or evidence schema to make a candidate
  pass.

## Evidence record

Record the source commit, clean tree digest, environment or image digest,
compiler/runtime identity, frozen run spec, raw logs, canonical manifests,
artifacts, elapsed time, peak memory, terminal state, and verifier state.
Preserve failed and timed-out cells instead of dropping them from an aggregate.

Only `SUCCESS` is a successful runner result. `VERIFIER_NOT_RUN` and
`VERIFIER_FAILED` may retain otherwise valid candidate artifacts, but neither
is an official pass. A `SUCCESS` terminal preserves a child-reported
`verifier=pass`, but promotion still requires the separately generated,
input-bound `official-verification.json`. Timeout, nonzero exit, invalid
metrics, cancellation, missing manifest, OOM, and scheduler-only failures
retain no candidate-quality claim.

## Information and compute boundaries

The proposer must not receive sealed rows, source-family labels, generator
names, per-example evaluator failures, private digests, or custodian state.
Use synthetic fixtures until the relevant protocol gate is reviewed.

Run locally by default for work estimated below ten minutes and 16 GB. Before
any cluster submission, read `skills/using-slurm/SKILL.md`, present the exact
revision, environment/image digest, dataset boundary, partition, resources,
array shape, wall time, and output paths, and obtain explicit approval. A
queued or running job is not evidence.

## Decision record

Conclude with one of:

- strict improvement eligible for the next track-specific gate;
- equal or worse under the frozen comparator;
- failed eligibility;
- censored timeout or unknown;
- blocked because required evidence is absent.

Never convert a synthetic advance, visible freeze, or disclosed-control result
into a blind promotion.
