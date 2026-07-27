# BooleanRazor Agent Instructions

BooleanRazor is a standalone exact Boolean-learning and circuit-synthesis
research workspace. Keep the disclosed v1 control and the genuinely blind
benchmark separate in code, evidence, and claims.

## First actions

1. Read `GOAL.md`, the active plan in `docs/plans/`, and
   `docs/handoff/SESSION_HANDOFF.md`.
2. Run `make setup`, `make skills`, and `make test` from a clean checkout.
3. Record any baseline failure before changing code.
4. Do not install heavy tools, attach private data, or submit remote compute
   without explicit human approval.

## Scientific contract

- Accuracy is primary; reachable gate count is secondary.
- A promoted blind result requires 100% training consistency, deterministic
  reruns, exhaustive equivalence against its completed truth table, and a
  differential check with the official Julia verifier.
- Negation is free. Score circuits with the challenge's one-gate XOR metric,
  not a conventional AIG cost.
- The public proposal side must never receive sealed rows, source-family
  labels, generator names, per-example evaluator failures, or private digests.
- Treat A=`x+y`, B=`abs(x-y)`, C=`x*y`, and D=`x²+y²` only as disclosed v1
  controls. Never present their recovery as blind-learning evidence.
- OxiDD is an oracle for reduced checks and ordering comparisons, not the
  production learner. Tensor-network models are gated candidates whose full
  predictions must be enumerated and passed through the same Rust XAG backend.

## Experiment discipline

- Freeze the survey, benchmark, folds, baselines, metric schema, and timeout
  before proposing algorithms.
- Give every hypothesis a fresh Git worktree and a root `LOG.md`; never reuse a
  worktree for a different hypothesis.
- Cap each algorithm cell at 300 seconds, including startup and cleanup.
- Use synthetic fixtures until the relevant protocol gate is reviewed.
- A result is evidence only when its source commit, clean tree digest,
  environment or image digest, frozen run spec, artifacts, logs, timing,
  memory, and verifier outcome are recorded.
- Preserve failed and timed-out cells. They are censored observations, not
  missing rows.

## Compute boundary

Local work is the default for cells estimated below 10 minutes and 16 GB.
`hpccube` Slurm is reserved for explicitly ratified promoted cells. Before any
submission, read `skills/using-slurm/SKILL.md` and the active cluster profile,
present the exact code revision, container or environment digest, dataset
boundary, partition, resources, array shape, wall time, and output paths, then
wait for approval. Submit, monitor, fetch, and classify failures through the
vendored harness adapters; a queued or running job is not a successful result.

## Development practice

- Follow the ratified plan and use test-driven development.
- Prefer small reviewed commits. Do not mix a new hypothesis with unrelated
  refactoring.
- Do not change the evaluator contract to make a candidate pass.
- Never commit `.venv`, Rust build output, run results, secrets, private data,
  sealed data, or custodian state.
- Before claiming completion, run the focused tests, `make test`, inspect the
  diff, and state any missing proof plainly.

## Repository map

- `src/`, `tests/`, `Cargo.toml` — Rust BDD/SAT/XAG core and exact controls.
- `research/`, `reblind/` — frozen public protocol and benchmark commitments.
- `autoresearch/`, `scripts/` — bounded experiment runner and HPC adapters.
- `.knowledge/` — tracked survey sources only; raw PDFs and hidden data stay
  outside the repository.
- `docs/plans/`, `docs/handoff/` — design authority and durable continuation
  context.
- `skills/` — vendored local workflow skills registered by `Ion.toml`.
