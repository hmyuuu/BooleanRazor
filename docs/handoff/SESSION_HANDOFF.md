# Session handoff

## Current answer

Blind advantage has not been demonstrated. ProjectedSupportBDD R2 is the
current internal tracked-formula synthetic frontier at 104,857/104,857 exact
rows and 72 reachable gates, but it is historical branch-only evidence—not a
public, blind, sealed, external, or global SOTA result.

Use the generated views for the current state:

- `docs/STATUS.md`
- `docs/METHODS.md`
- `docs/EXPERIMENT_INDEX.md`
- `research/EVIDENCE_LEDGER.md`
- `reports/site/index.html`

## Integrated scope

The accepted integration includes the exact Rust/XAG core, disclosed controls,
public importer, care-BDD and bounded-SAT tools, bounded runner with truthful
verifier states, fail-closed Julia wrapper, immutable verification-record
tool, evidence-bounded promotion checker, deterministic offline report, and
the optimization/promotion skills.

Historical fair, GreedyExactConflict, ProjectedSupportBDD, TN, and real-Julia
outcomes remain branch evidence. Their algorithm implementations were not
silently merged into the accepted method set. The report preserves their
failures, invalid cells, superseded runs, decisions, and exact commit/path
locators.

## Evidence boundary

- `research/BASELINES.csv` has no executed public rows.
- The content-addressed public bundle is not mounted in this repository.
- `research/CURRENT_PROMOTION_REQUEST.json` contains no candidate evidence,
  deterministic pairs, frozen comparison, or official records.
- Its replayed decision is `blocked`; the maximum visible-only next step is
  `freeze_candidate`.
- Sealed confirmation and `promote_blind_result` are absent.
- No private custodian material, public archive, sealed row, or cluster
  authorization is bundled here.

Internal exhaustive Rust equivalence is separate from Official Julia
verification. `VERIFIER_NOT_RUN` retains a candidate but is a runner failure
with code 67. A child-reported `verifier="pass"` becomes promotion proof only
through a separately bound `official-verification.json`.

## Next safe work

1. From a clean accepted checkout, run:

   ```bash
   make setup
   make skills
   make test
   make report-check
   ```

2. Obtain the exact content-addressed public archive through the reviewed
   custodian boundary. Do not request sealed rows or private digests.
3. Freeze one public candidate integration decision, then run the two baseline
   methods and matched candidate repeats through the bounded runner.
4. Require byte-identical pairs, internal equivalence, immutable official
   records, and a complete frozen comparison before `freeze_candidate`.
5. Keep sealed confirmation external and later. Do not use it to tune the
   proposer.

HPC remains unauthorized. Local work is the default; a later `hpccube`
submission needs a separately ratified exact revision, environment/image
digest, public data boundary, partition, resources, array, wall time, and
output paths.

## Navigation

- `AGENTS.md` — choose activity, evidence track, verification rung, and
  promotion action.
- `autoresearch/README.md` — fresh-worktree and five-minute runner protocol.
- `reblind/README.md` — public/sealed publication boundary.
- `skills/exact-circuit-optimization/SKILL.md` — new optimization hypothesis.
- `skills/circuit-evidence-promotion/SKILL.md` — validation and promotion.
- `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md` — scientific authority.
- `docs/superpowers/specs/2026-07-30-booleanrazor-deliverability-verifier-design.md`
  — deliverable/verifier architecture.
