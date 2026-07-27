# Frozen pre-benchmark survey

This survey was frozen before any reblinded public rows, baseline outcomes, hidden
mapping, or sealed metric was available. “Source claim” marks a statement drawn
from the rendered literature; “local evidence” marks a checked repository or
installed-tool fact. The literature packet is intentionally modest, so missing
evidence is recorded instead of being filled from memory.

## Partial MCSP / Occam learning

- **Source claim.** The rendered record identifies Blumer, Ehrenfeucht, Haussler,
  and Warmuth’s 1987 *Occam’s Razor*, but contains citation metadata only; this
  survey therefore does not import an unverified numerical PAC sample-complexity
  bound. `.knowledge/literature/boolean-logic-synthesis/10-1016-0020-0190-87-90114-1.md`
- **Source claim.** Hirahara proves randomized-reduction NP-hardness for learning
  efficient programs and for the partial-function form of the minimum circuit
  size problem (partial MCSP). This rules out treating globally minimum
  completion-plus-synthesis as a routine polynomial-time primitive.
  `.knowledge/literature/boolean-logic-synthesis/10-1109-focs54457-2022-00095.md`
- **Implication.** Circuit size is still a legitimate Occam bias, but this
  benchmark tests predeclared heuristics. It does not claim a general exact
  learner or infer sample sufficiency merely from a small returned circuit.

## BDD ordering

- **Source claim.** An ordered binary decision diagram can change exponentially
  with variable order, and finding the minimum order is NP-hard; the best
  classical exact bound summarized in the rendered paper is O*(3ⁿ).
  `.knowledge/literature/boolean-logic-synthesis/1909.12658_quantum-algorithm-for-finding-the-optimal-variable-ordering.md`
- **Source claim.** The Friedman–Supowit catalog entry records the more explicit
  O(n²3ⁿ) exact-ordering algorithm. It is an exact reference point, not a
  practical plan for the 12–20 input-bit tiers.
  `.knowledge/literature/boolean-logic-synthesis/friedman_1986_finding.md`
- **Source claim.** Bryant’s rendered record establishes integer multiplication
  as the canonical application for graph-representation lower-bound analysis,
  while the local synthesis notes warn that a compact arithmetic circuit need
  not induce a compact ordered BDD.
  `.knowledge/literature/boolean-logic-synthesis/10-1109-12-73590.md`
  `.knowledge/literature/boolean-logic-synthesis/NOTES.md`
- **Evidence limit.** Sifting and window permutation are sensible practical
  ordering lanes, but the current rendered packet contains no primary
  description of either heuristic. They may be predeclared as heuristics; no
  optimality or approximation guarantee is attributed to them here.

## Exact SAT synthesis

- **Source claim.** The reviewed synthesis notes support bounded exact SAT as a
  way to certify a stated gate bound on a stated care set, while warning that
  whole-circuit minimum proofs become expensive and depend on the precise gate
  basis. `.knowledge/literature/boolean-logic-synthesis/NOTES.md`
- **Protocol consequence.** A SAT lane must fix the XOR/AND basis, complemented
  edges, shared multi-output roots, care set, bound, solver version, timeout,
  and proof/verifier status. Timeout is evidence, not a proof that no smaller
  circuit exists.
- **Evidence limit.** No rendered primary exact-synthesis paper is present.
  RustSAT/CaDiCaL is therefore an available implementation lane, not a
  reproduced strong baseline in this freeze.

## XAG / logic synthesis

- **Source claim.** The synthesis notes identify the objective mismatch between
  BDD nodes, AIG AND nodes, and the challenge’s total XOR-plus-AND gates, and
  require challenge-native extraction with dead-code elimination.
  `.knowledge/literature/boolean-logic-synthesis/NOTES.md`
- **Source claim.** The same notes identify complemented edges and shared
  multi-root subgraphs as useful representation features, but do not equate BDD
  node count with final XAG gate count.
  `.knowledge/literature/boolean-logic-synthesis/NOTES.md`
- **Local evidence.** The frozen custom backend uses shared complemented ROBDD
  roots, extracts a compact XOR–AND graph (XAG), verifies the complete table,
  and serializes only the reachable union. Baseline selection scores the
  verified XAG, not the intermediate BDD.

## Arithmetic circuits

- **Source claim.** Multiplication is a representation stress case: the
  arithmetic circuit and ordered-BDD costs can have qualitatively different
  scaling. `.knowledge/literature/boolean-logic-synthesis/10-1109-12-73590.md`
  `.knowledge/literature/boolean-logic-synthesis/NOTES.md`
- **Local evidence.** The existing non-blind controls implement ripple
  add, absolute subtraction, compressor-tree unsigned multiplication, and
  sum-of-squares (including the square partial products) directly in the
  challenge XAG basis. Exhaustive tests pin the visible v1 controls at 37, 49,
  168, and 127 reachable gates respectively. These are `blind=false` controls;
  none is a reblinded baseline outcome.
- **Scope.** Direct arithmetic templates are a useful sanity control when the
  semantics are already known. They are prohibited as hidden-family oracles in
  the reblinded study.

## TT / MPS completion

- **Source claim.** Binary Matrix Products are discrete analogues of tensor
  trains (TTs) and matrix product states (MPSs), and the rendered work gives a
  direct translation from that discrete form to BDDs; variable order controls
  both representations’ complexity.
  `.knowledge/literature/mps-based-algorithm/2505.01930_a-matrix-product-state-representation-of-boolean-functions.md`
- **Source claim.** Guaranteed TT recovery in the reviewed factorization work
  assumes linear sensing with a restricted-isometry property and suitable
  initialization. Ordinary coordinate completion generally lacks that
  property, so the paper presents coordinate-completion evidence numerically
  rather than extending its guarantee.
  `.knowledge/literature/mps-based-algorithm/2401.02592_guaranteed-nonconvex-factorization-approach-for-tensor-train.md`
- **Source claim.** Grokking can yield delayed perfect generalization after
  memorization on some small algorithmic neural-network datasets, but that is an
  empirical phenomenon rather than a sparse Boolean-table recovery theorem.
  `.knowledge/literature/mps-based-algorithm/2201.02177_grokking-generalization-beyond-overfitting-on-small-algorith.md`
- **Source claim.** MPS classifiers have also shown grokking-like transitions
  on image and gene-expression binary classification tasks; those tasks do not
  establish exact multi-output arithmetic extrapolation.
  `.knowledge/literature/mps-based-algorithm/2503.10483_grokking-as-an-entanglement-transition-in-tensor-network-mac.md`
- **Protocol consequence.** A TT/MPS lane produces a completed table, restores
  every observed row after thresholding, and then uses the same verified
  ROBDD/XAG backend. Selection uses exact-row visible cross-validation, not
  per-bit loss.

## Available software

The inventory below was captured locally on 2026-07-27 without installing a
dependency.

| Software | Frozen version / state | Available capability | Status in this study |
|---|---|---|---|
| OxiDD | 0.12.0, default Cargo feature | Independent BCDD construction and exhaustive evaluation | Installed; differential oracle |
| Custom ROBDD/XAG | crate 0.1.0, Rust 1.93.0 | Shared complemented ROBDD, grouped/interleaved extraction, canonical XAG netlist | Installed; common backend |
| RustSAT + CaDiCaL | both pinned 0.7.5, optional `sat` feature | Bounded SAT integration lane | Source-pinned; not a reproduced baseline |
| CUDD | executable/library not found | Mature BDD package and dynamic reordering | Not installed |
| ABC | executable not found | Industrial AIG rewriting and technology-independent synthesis | Not installed |
| Espresso | executable not found | Two-level logic minimization | Not installed |
| JAX / TN stack | JAX not found in the active Python 3.14.6 environment | Differentiable TT/MPS completion | Not installed |

Because ABC, CUDD, and Espresso are not installed or reproduced, this work may
claim improvement only against the matched frozen baselines and visible
controls below. It may not claim “100× versus SOTA.”

## Reproduced baselines

| Control | Blind | What is reproduced before the freeze | Allowed use |
|---|---:|---|---|
| Semantic arithmetic v1 | false | Exhaustive complete-table semantics and canonical XAG gate counts for four visible controls | Regression and metric sanity only |
| Custom shared ROBDD/XAG | false | Grouped/interleaved builds, complete-table equivalence, dead-code-free gate counts | Common extraction backend |
| OxiDD BCDD | false | Exhaustive agreement with the custom ROBDD for both frozen orders | Independent differential check |
| Zero fill v1 | true | Algorithm and tests only; no benchmark rows or outcomes attached | Frozen comparator |
| Hamming 1-nearest-neighbor v1 | true | O(input_bits × 2^input_bits) deterministic completion and tests only | Frozen comparator |

The two blind baselines always restore observations. Zero fill assigns an
all-zero output to every unseen input. Hamming 1-nearest-neighbor selects the
observed input at minimum Hamming distance, then minimum numeric input, then
original row index. Both evaluate grouped and operand-interleaved shared
ROBDD/XAG extractions and retain the lower verified gate count, with grouped
order winning an exact tie.

## Unresolved gap

The unresolved problem is not whether a compact representation can fit visible
rows; it is whether a precommitted learner can complete arbitrary sparse
coordinate samples with high exact-row accuracy and still extract a smaller
shared XAG under a fixed 300-second cap. Partial MCSP hardness blocks a generic
exact shortcut, BDD order may dominate representation size, and TT recovery
theory does not cover these coordinate samples. The sealed study therefore
tests fixed hypotheses against both frozen baselines without adaptive access to
public rows or sealed feedback.
