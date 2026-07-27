# Session handoff

Focus: Continue the standalone BooleanRazor implementation, beginning with
Task 13 after confirming the migrated Task 10 baseline.

State:
- Repo/path: `/Users/hmyuuu/workspace/BooleanRazor`
- Branch/commit: `main` / resolve with `git rev-parse HEAD`
- PR/issue: QuantumBFS/quantum.harness issue 71

Done:
- Tasks 1–9: contract/leakage audit, exact disclosed-v1 controls, Rust
  truth-table/XAG/BDD foundation, survey, frozen two-tier blind protocol, and
  sealed benchmark commitment.
- Task 10: Steps 1–8 complete in standalone commits `a824e5a`, `93ffdd2`,
  and `336f478`; final independent review passed. Step 9 remains blocked on
  Task 13.

References:
- `GOAL.md`
- `docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md`
- `docs/MIGRATION.md`
- `docs/handoff/MIGRATION_VERIFICATION.md`
- `docs/handoff/TASK_10_REPORT.md`
- `docs/handoff/TASK_11_12_PREFLIGHT.md`

Next:
1. Run `make setup`, `make skills`, and `make test`; record any migration-only
   failure.
2. Confirm Task 10's migrated review report and protocol gate.
3. Implement and review Task 13 on synthetic data, then freeze the Task 11/12
   experiment contracts from the preflight notes.

Suggested Skills:
- `superpowers:executing-plans`: follow the ratified task order.
- `superpowers:subagent-driven-development`: preserve implementer/reviewer
  separation.
- `superpowers:test-driven-development`: keep every implementation step
  red/green/refactor.
- `using-slurm`: only after a promoted `hpccube` cell is ratified.

Do Not Assume:
- No public training archive, sealed evaluation data, private custodian state,
  publishable blind advantage, or HPC authorization is present.

Ask Human If:
- Before attaching restricted data, installing a heavy dependency, changing
  the frozen evaluation contract, or submitting any `hpccube` job.
