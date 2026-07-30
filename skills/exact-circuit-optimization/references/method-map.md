# BooleanRazor method map

Use this map to choose a new independent variable without repeating a closed
hypothesis. Branch evidence below is historical, non-promoted evidence; it does
not establish the state of the accepted branch by itself.

## Tracked method roles

| Method | Repository role | Boundary |
| --- | --- | --- |
| Truth-table/XAG backend | Canonical completed-table evaluation, deterministic serialization, reachable XAG scoring | Challenge cost authority; exhaustive artifact equivalence is internal proof only |
| Arithmetic controls | Constructive circuits for A–D at 37, 49, 168, and 127 reachable gates | Disclosed v1 controls; upper bounds, not minimality or blind evidence |
| Complemented ROBDD | Shared multi-output exact representation and XAG extraction | Preserve complemented-edge semantics and exhaustive replay |
| Care-BDD | Visible-row completion and order search | Implemented method with synthetic/internal evidence; public results remain absent |
| ProjectedSupportBDD | Per-output projected-support completion under one shared global order | Strong synthetic branch result only; requires a separate public-candidate integration decision |
| Bounded SAT resynthesis | Exact local XAG rewriting at a frozen bound | Tool evidence; `Timeout`/`Unknown` are censored, and only exact-bound proof is `UNSAT` |
| OxiDD oracle | Reduced independent checks and order comparisons | Oracle only; never the production learner or gate metric |
| Bounded runner | Five-minute process-group execution, logs, manifests, and resource evidence | Only `SUCCESS` is runner success; retain truthful verifier state |
| Official Julia wrapper | Fail-closed external-verifier adapter | Wrapper implementation does not itself verify a candidate |
| Tensor-network pilot | Enumerated prediction candidate routed through the Rust backend | Branch-only synthetic pipeline evidence; no blind or SOTA claim |

Relevant implementation anchors are `src/xag.rs`, `src/robdd.rs`,
`src/care_bdd.rs`, `src/sat.rs`, `src/oxidd_oracle.rs`,
`scripts/run-experiment.py`, and `scripts/verify-julia.sh`.

## Historical branch outcomes

| Experiment | Exact revision | Preserved outcome | Status |
| --- | --- | --- | --- |
| Fair order R1 | `d019a3dc3d5afe1aef76a25f266afe27f9d66c6e` | The `6/6/6/6` scheduler was deterministic, but its rank-zero synthetic result tied the legacy result at `0/104857` exact rows and 36,084 gates. The strict-improvement rule rejected it. | Rejected; non-promoted |
| GreedyExactConflict R1 | `7ac3c3ba2430ed787bab5ca215c259e259fa1fb5` | Two synthetic repeats were byte-identical. Exact-row CV remained `0/104857`; the tie-break improved from 36,084 to 34,917 gates. It advanced only to separate public-candidate consideration. | Verified branch-only; non-promoted |
| ProjectedSupportBDD R2 | `8f6eda40e089a12faa8df3827207024afd719865` | Two executable-bound synthetic repeats were byte-identical and reached `104857/104857` exact-row CV with 72 reachable gates, versus the matched R1 control at `0/104857` and 34,917 gates. This supports only a synthetic advance to a separate public-candidate integration decision: the public reblinded bundle is absent, the official Julia verifier was not run, and no sealed evaluation occurred. | Verified branch-only; non-promoted |
| Tensor-network pilot | `96429f981170766575fd167713a528078f297d67` | A fixed local CPU, fully observed parity cell proved pipeline and artifact repeatability. It did not prove learned completion, generalization, public accuracy, GPU readiness, or SOTA. | Verified branch-only; non-promoted |
| Historical v1 Julia differential | `41518ce876b9c2a5939a525e538473165765203c` | The branch records exact official-Julia passes for the disclosed A–D control artifacts, using wrapper source `6bf77f1ae9a3d6b04218badaf66dab8e7d388014`. It is historical branch-bound evidence, not a fresh current-revision or blind result. | Verified branch-only; non-promoted |

## Current evidence boundary

Recheck the repository before each use. At this deliverability snapshot,
`research/BASELINES.csv` has no executed public rows, sealed results are
absent, and the blind-promotion decision is therefore blocked. The historical
Julia record above applies only to disclosed controls on its recorded branch;
it does not fill either missing blind-evidence gate.

## Productive next directions

- Treat ProjectedSupportBDD R2 as the leading synthetic public-candidate
  integration input, not as public, sealed, blind, or SOTA evidence. Do not
  infer public behavior from its tracked-formula fixture.
- Keep GreedyExactConflict as the matched R1 control and global-order
  component. Its gate reduction alone did not improve synthetic exact-row
  generalization.
- Revisit scheduler diversity only with a new, precommitted independent
  variable. Fair allocation alone fixed coverage but did not improve the
  frozen score.
- Apply bounded SAT only to an already exact candidate and require whole-XAG
  equivalence after reinsertion. Stop when the gate count does not strictly
  improve or the censored-outcome rule fires.
- Evaluate a tensor-network completion only on permitted visible inputs,
  enumerate its full prediction table, and route it through the Rust XAG
  backend before comparison.
- Prefer hypotheses that can change exact-row accuracy. Gate-only tuning of
  candidates with zero exact-row generalization is secondary evidence.
