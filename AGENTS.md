# BooleanRazor Agent Guide

BooleanRazor is an evidence-first workspace for exact Boolean learning and
circuit synthesis. Keep disclosed controls, synthetic development, visible
blind selection, and sealed confirmation separate in data access, artifacts,
verification, and claims.

## Current answer

- [Current status](docs/STATUS.md) — the short scientific answer and next gate.
- [Methods](docs/METHODS.md) — implemented methods, lessons, and stop rules.
- [Experiment index](docs/EXPERIMENT_INDEX.md) — every retained research round,
  including failed, invalid, tied, rejected, and superseded runs.
- [Evidence ledger](research/EVIDENCE_LEDGER.md) — claims, proof, limitations,
  and missing proof.
- [Offline web report](reports/site/index.html) — the human-readable overview;
  the full round-by-round trace is on `reports/site/experiments.html`.

Verified main: disclosed controls and exact core/infrastructure. Verified
branch-only: the historical v1 Julia run, GreedyExactConflict,
ProjectedSupportBDD R2, and the tensor-network pilot. ProjectedSupportBDD R2 is
the current internal synthetic frontier: 104,857/104,857 exact rows and 72
reachable gates on its recorded synthetic fixture. It is not a public, blind,
sealed, or global SOTA result. The fair scheduler was deterministic but
rejected as a quality improvement. Public baseline results, a visible freeze,
sealed confirmation, and blind advantage are blocked or absent. Blind
advantage has not been demonstrated.

## First actions

1. Read `GOAL.md`, `docs/STATUS.md`, the active plan in `docs/plans/`, and
   `docs/handoff/SESSION_HANDOFF.md`.
2. From a clean checkout, run `make setup`, `make skills`, `make test`, and
   `make report-check`. Record any baseline failure before editing.
3. Inspect `git status --short` and preserve unrelated or user-authored work.
4. Choose the activity and evidence track below before opening data or
   changing a claim.
5. Do not install heavy tools, attach nonpublic data, access sealed material,
   or submit remote compute without explicit human approval.

## Choose the activity

| Activity | Start here | Required finish |
| --- | --- | --- |
| Understand the current result | `docs/STATUS.md`, then the web report | State the evidence ceiling and missing proof |
| Reproduce disclosed v1 | `solve-v1`; `tests/official_v1.rs` | Rust exact checks; Julia record if making an official-verifier claim |
| Propose an optimization | `skills/exact-circuit-optimization/SKILL.md` | Fresh worktree, root `LOG.md`, frozen run, deterministic evidence |
| Run a bounded cell | `autoresearch/README.md`; `scripts/run-experiment.py` | Preserve terminal manifest, including failures and timeouts |
| Record official verification | `scripts/record-verification.py` | Immutable `official-verification.json` bound to exact inputs |
| Decide promotion | `skills/circuit-evidence-promotion/SKILL.md` | Canonical request and replayable decision within the track ceiling |
| Update the deliverable | Edit only `reports/data/project.json` | `make report` and `make report-check` |
| Use Slurm | `skills/using-slurm/SKILL.md` | Human-approved resource card before submission |

Use test-driven development for code or contract changes. Give each research
hypothesis its own Git worktree and root `LOG.md`; never reuse a worktree for a
different hypothesis.

## Choose the evidence track

| Track | Permitted evidence | Highest legal next step |
| --- | --- | --- |
| `disclosed_control` | Known v1 mappings and disclosed datasets | `promote_control` |
| `synthetic` | Generated fixtures with no public or sealed rows | `advance_public_candidate` |
| `blind_visible` | Reviewed public bundle through the importer only | `freeze_candidate` |
| `sealed_confirmation` | Frozen candidate evaluated by the custodian | `promote_blind_result` |

Never upgrade a claim by wording. A synthetic exact result remains synthetic;
a historical branch record remains branch-only; internal exhaustive
equivalence is not Official Julia verification; and an absent sealed decision
cannot be inferred from public accuracy.

Treat A=`x+y`, B=`abs(x-y)`, C=`x*y`, and D=`x²+y²` only as disclosed v1
controls. Their 37, 49, 168, and 127 reachable gate counts are constructive
upper bounds, not minimality proofs or blind-learning evidence. Negation is
free; score with the challenge's one-gate XOR metric, not conventional AIG
cost.

## Data-access gate

Before a run, write the permitted-data boundary in `LOG.md` and the frozen run
specification.

- Synthetic and disclosed work may not mount the public archive implicitly.
- A visible-blind proposer may read only the tracked contract and the reviewed
  content-addressed public extraction through `OCCAM_REBLIND_PUBLIC_ROOT`.
- The proposer must never receive sealed rows, generator or family labels,
  source names, private digests, per-example evaluator failures, or custodian
  state.
- The sealed evaluator returns only the frozen aggregate contract. It does not
  feed diagnostics back into proposal work.
- Use synthetic fixtures until the relevant public or sealed gate is reviewed.

If the required dataset is absent, record `blocked`; do not fabricate a result,
substitute disclosed v1, or convert the planned study into a trace node.

## Candidate routes

- **Truth table → XAG:** the production exact path and common output contract.
- **Complemented ROBDD / care-BDD:** learn or complete tables; compare orders
  under the frozen evaluation budget.
- **Bounded SAT resynthesis:** optimize verified circuit cuts under the
  285-second internal deadline; retain timeout/unknown as censored evidence.
- **OxiDD:** oracle for reduced checks and ordering comparisons only, never the
  production learner.
- **Tensor network:** a gated candidate only. Enumerate every prediction, then
  pass the completed table through the same Rust XAG and evidence pipeline.

Accuracy is primary and reachable gate count is secondary. Stop or reject a
candidate that loses exact-row accuracy, violates the five-minute cell cap,
cannot reproduce byte-identically, lacks required bindings, or fails to
improve the frozen accuracy-first/XAG comparison.

## Verification ladder

Do not skip or collapse these rungs:

```text
visible training consistency
-> artifact.json equivalence=pass
-> byte-identical deterministic rerun
-> official-verification.json status=pass
-> sealed evaluator/frozen analysis decision when the track requires it
```

`artifact.json equivalence=pass` is Internal exhaustive equivalence performed
by the Rust path. `official-verification.json status=pass` is Official Julia
verification recorded against the exact manifest, run specification, circuit,
dataset, verifier, Julia version, and digests. A string such as
`verifier: "pass"` outside that bound record is not interchangeable proof.

For a promoted blind result require 100% training consistency, deterministic
reruns, exhaustive completed-table equivalence, official Julia verification,
and the frozen sealed decision. State any missing rung plainly.

## Runner rules

Each algorithm cell is capped at 300 seconds including startup and cleanup.
The child runs in its cell directory. Therefore repository binaries, manifests,
public roots, helper scripts, output directories, and metrics arguments in
child commands must use absolute paths.

| Terminal status | Candidate artifacts | Runner result |
| --- | --- | --- |
| `SUCCESS` | Retained; official verifier reported pass | success / code 0 |
| `VERIFIER_NOT_RUN` | Retained; verifier is absent | failure / code 67 |
| `VERIFIER_FAILED` | Retained; verifier reported fail | failure / code 66 |
| Any other terminal status | No candidate-quality or artifact claim | classified failure |

Preserve failed, invalid, superseded, rejected, equal, and timed-out cells.
They are observations, not missing rows. A queued or running scheduler job is
not a successful result.

## Promotion state machine

Promotion is computed from evidence; it is not an editorial decision.

```text
candidate run
-> deterministic pair
-> official verification record
-> frozen comparison
-> canonical promotion request
-> scripts/check-promotion.py
-> promote, advance, freeze, reject, no_change, or blocked
```

The request's track fixes the maximum decision. Mixed revisions, tree digests,
dataset boundaries, hardware, timeouts, candidate identities, or method
bindings fail closed. Official and sealed proof must be replayable and bound to
the claimed record.

The committed visible request currently contains no candidate evidence,
deterministic pairs, official records, or comparison, so its decision is
`blocked` and its highest legal next step is `freeze_candidate`. Only a
complete `sealed_confirmation` request can produce `promote_blind_result`.

## HPC gate

Local work is the default below 10 minutes and 16 GB. `hpccube` Slurm is
reserved for an explicitly ratified promoted cell. Before submission, read
`skills/using-slurm/SKILL.md` and the active cluster profile, then present the
exact revision, clean tree digest, container or environment digest, dataset
boundary, partition, resources, array shape, wall time, and output paths.
Wait for human approval. Submit, monitor, fetch, and classify through the
vendored adapters; configured access is not authorization.

## Report and documentation updates

`reports/data/project.json` is the only hand-edited report source. Generated
HTML and Markdown are derived artifacts.

1. Add the executed research round with its real parent revision(s), runs,
   decisions, limitations, and evidence. Never add a planned public or sealed
   run to the executed trajectory.
2. Update the current frontier only if the frozen comparison and evidence
   ceiling support it.
3. Run `make report`.
4. Run `make report-check`; it checks canonical source, Git-bound evidence,
   promotion replay, deterministic bytes, offline assets, and internal links.
5. Run focused tests and `make test`, inspect the diff, and state missing proof.

Do not hand-edit `docs/STATUS.md`, `docs/METHODS.md`,
`docs/EXPERIMENT_INDEX.md`, `research/EVIDENCE_LEDGER.md`, or
`reports/site/`. Do not turn `docs/LEADERBOARD.md` into a provisional public
leaderboard.

## Repository map

- `src/`, `tests/`, `Cargo.toml` — Rust BDD/SAT/XAG core and disclosed controls.
- `research/`, `reblind/` — frozen public protocol, commitments, promotion
  request/decision, and generated evidence ledger.
- `autoresearch/` — five-minute runner protocol and failure-preserving tools.
- `scripts/` — Julia recording, promotion, report generation/checking, and HPC
  adapters.
- `reports/data/project.json` — canonical deliverable evidence model.
- `reports/site/` — generated offline report.
- `docs/STATUS.md`, `docs/METHODS.md`, `docs/EXPERIMENT_INDEX.md` — generated
  human navigation.
- `docs/plans/`, `docs/handoff/` — design authority and continuation context.
- `skills/` — vendored optimization, promotion, and operational workflows
  registered by `Ion.toml`.
- `.knowledge/` — tracked survey sources only; raw PDFs and hidden data stay
  outside the repository.
