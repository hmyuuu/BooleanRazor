# Task 11/12 preflight (2026-07-27)

No private custodian data or public training archive was inspected.

## Task 11

- Reuse Task 13 fold assignments. Seeds are exactly 64 lowercase hex decoded
  to 32 bytes; do not define an integer-seed fold dialect in `care_bdd`.
- Five care-set fold fits evaluate only held-out visible rows. Do not enumerate
  `2^n` assignments or synthesize an XAG per fold.
- Full-visible XAG extraction is allowed only for retained candidates when a
  gate tie-break is needed. Enumerate and exhaustively verify only the winner.
- Freeze a deterministic maximum order-evaluation budget after a synthetic
  20-bit timing test; do not assume beam `32×12` fits 300 seconds.
- Refactor the current internal ROBDD builder rather than mutating a finalized
  `SharedRobdd`. Preserve complemented-edge normalization, multi-root sharing,
  reachability, and topological serialization.
- Keep OxiDD to synthetic/reduced differential fixtures or an explicit
  optional final oracle pass, never fold scoring.
- Add a provenance-free 180-cell development design spec to the synthetic-only
  hypothesis commit. Emit the exact Task 10 metrics and canonical table,
  circuit, and artifact index. Derive development CSV rows only from checked
  manifests.

## Task 12

- Keep standalone resynthesis synthetic/tool-only. A successful benchmark cell
  must compose resynthesis inside a `PublicSuite`-backed learner so the final
  table, training consistency, visible-CV metrics, circuit, and artifact index
  satisfy Task 10.
- Put SAT diagnostics in canonical `sat-report.json` or hashed logs, not the
  exact-key `metrics.json`.
- Enumerate cuts deterministically with explicit maximum cut and solver-call
  budgets. Each bound is `original_cut_gates - 1`; all calls share one
  285-second absolute deadline. Verify the whole circuit once after the
  deterministic rewrite sequence.
- Fix test snippets: `CompleteTable::from_fn` indices are `usize`, and
  integration tests use public `reachable_gate_count()` rather than private
  graph/output fields. Add multi-output-sharing and exact-bound reachability
  tests.
- Map CaDiCaL interruption to `Timeout` only when this deadline fired;
  otherwise `Unknown`. Solver-reported UNSAT establishes only the frozen
  encoding/bound; do not claim a checked proof certificate without a pinned
  proof verifier.

## Both tasks

- Create a fresh hypothesis worktree from the accepted Task 13 commit, fill
  and commit `LOG.md`, then commit synthetic-only code before any public data
  mount. Public execution occurs only from a clean commit.
