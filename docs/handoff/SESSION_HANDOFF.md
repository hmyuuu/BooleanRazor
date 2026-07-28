# Session handoff

Focus: Ratify, implement, and evaluate the fair-scheduled Rust care-BDD order
search without changing the frozen blind-learning contract.

State:
- Repo/path: `/Users/hmyuuu/workspace/BooleanRazor`
- Branch/commit: `codex/task-11-12-integration` / `7e99409`
- Main: `main` / `61312ed`
- PR/issue: QuantumBFS/quantum.harness issue 71

Done:
- Exact disclosed-v1 controls remain A=37, B=49, C=168, D=127 reachable
  challenge gates; BDD candidates do not replace them.
- Survey, frozen blind benchmark commitment, two baselines, bounded runner,
  firewall, and opaque public importer are committed.
- Care-BDD Steps 1–7: `c757952`, provenance `6946bb4`; 16 focused tests pass,
  including exhaustive XAG equivalence and OxiDD finalist checks.
- SAT resynthesis is hardened through `61312ed`; DD/SAT integration is
  `0f62ae2`.
- DD audit `9f7e2a1` measured 70.273820 seconds for the synthetic 20-bit,
  32-evaluation cell and proved scheduler allocation `19/5/0/0`.
- The authoritative plan was reconciled at `7e99409`.
- Fail-closed Julia wrapper is separate at `codex/task-15-julia-wrapper`
  commit `6bf77f1`; fixture/full tests pass.

References:
- `GOAL.md`
- `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md`
- `LOG.md`
- `docs/LEADERBOARD.md`

Next:
1. Obtain explicit human ratification for the proposed fair `6/6/6/6`
   post-seed scheduler.
2. If approved, create a fresh hypothesis worktree from `7e99409`, add a root
   `LOG.md`, and use TDD while freezing folds, seeds, completion, beam, score,
   32-evaluation cap, and OxiDD oracle role.
3. Run the same synthetic 20-bit calibration and full verification; retain the
   candidate only if deterministic, exact, inside 300 seconds, and better by
   the frozen accuracy-first/XAG tie-break.
4. When the content-addressed public bundle exists, run the frozen baseline and
   candidate cells before any sealed evaluation.

Suggested Skills:
- `brainstorming`: preserve the design-ratification gate.
- `using-git-worktrees`: isolate the DD scheduling hypothesis.
- `test-driven-development`: require red/green evidence for scheduling.
- `verification-before-completion`: verify exactness, timing, diff, and tests.
- `using-slurm`: only for a separately ratified promoted hpccube cell.

Do Not Assume:
- The fair scheduler is approved, the public reblind bundle is present, Julia
  is installed, TN packages are installed, or any HPC submission is
  authorized.
- Synthetic cross-validation or leaked-v1 recovery demonstrates blind
  benchmark accuracy.

Ask Human If:
- Before implementing the fair scheduler, installing Julia/TN dependencies,
  attaching nonpublic data, or submitting any hpccube job.
