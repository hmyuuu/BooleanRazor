# Goal

/goal Over 4–5 days, build and audit a reproducible Boolean-circuit discovery
system as specified in
`docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md`. Keep two evidence tracks:
exactly verify and optimize the disclosed v1 controls A=`x+y`,
B=`|x-y|`, C=`x*y`, and D=`x²+y²`; and develop a sealed blind Rust
BDD/SAT/XAG learner, using OxiDD only as an oracle and admitting a
tensor-network candidate only after its predictions are fully enumerated into
the same truth-table and XAG backend. Accuracy is primary and reachable gate
count is secondary. Every promoted result must have 100% training consistency,
deterministic reruns, exhaustive equivalence on its completed tables, and a
differential comparison with the official Julia verifier.

Freeze a research survey and strong two-tier benchmark before proposing new
algorithms, and keep hidden datasets unavailable to proposing agents. Give
each hypothesis its own Git worktree and `LOG.md`; cap every algorithm cell at
five minutes including startup and cleanup. Use `hpccube` Slurm only for an
explicitly ratified promoted cell. Stage approved remote work under
`~/BooleanRazor` in the `hpccube` account home; the configured path is not
compute authorization. Record the source revision, environment or image
digest, frozen run specification, monitored execution, fetched artifacts, and
classified failure evidence.

Promote every independently verified new SOTA to `main` and push it promptly
as a small reviewed commit. “SOTA” means an improvement under the frozen
metric and benchmark with all required reproducibility, exactness, verifier,
and regression checks—not a provisional or unreviewed experiment. Record the
promoted commit and evidence in `LOG.md` and the leaderboard documentation
before beginning the next hypothesis.

Conclude one of exactly three outcomes: at least 100× matched-quality
improvement over both frozen baselines; a statistically supported two-tier
scaling advantage; or an honest “advantage not demonstrated.”
