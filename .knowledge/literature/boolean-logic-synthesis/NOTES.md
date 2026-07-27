# Boolean logic synthesis — survey notes

Built by `/survey` on 2026-07-26 for the Occam's Circuit feasibility audit.
References use BibTeX cite keys; see `INDEX.md` for the catalog and
`../ref.bib` for full entries.

## Field landscape

- **Ordered binary decision diagrams (OBDDs).** Variable order can change an
  OBDD exponentially, and finding the minimum order is NP-hard
  [@tani_2025_quantum]. The best classical exact bound summarized by Tani is
  O*(3ⁿ) (*Literal:*
  `1909.12658_quantum-algorithm-for-finding-the-optimal-variable-ordering.md:26`);
  practical packages therefore rely mainly on reordering heuristics.
- **Shared, complemented decision diagrams.** Multi-root forests can share
  subgraphs across output bits, while complemented edges represent negation
  without adding a logic node. These properties make a complemented BDD a useful
  intermediate representation, but its node count is not automatically the cost
  of a downstream XOR–AND graph.
- **Circuit minimization from partial tables.** Partial minimum circuit size is
  NP-hard under randomized polynomial-time reductions
  [@hirahara_2022_np]. Practical systems consequently combine heuristic
  completion, structural synthesis, local rewriting, and bounded exact SAT
  checks rather than attempt whole-circuit global optimality.
- **Arithmetic functions are a stress case.** Bryant's integer-multiplication
  analysis is a canonical warning that compact circuits need not have compact
  OBDDs under a chosen representation [@bryant_1991_complexity].
- **Binary matrix products.** The Binary Matrix Product normal form has a direct
  translation to BDDs (*Literal:*
  `2505.01930_a-matrix-product-state-representation-of-boolean-functions.md:26`)
  [@usturali_2025_matrix]. This is an exact, discrete correspondence; it does not
  imply that an arbitrary real-valued learned matrix-product state converts
  compactly to a deterministic BDD.

## Key open problems

- **Objective mismatch.** Most BDD tools minimize diagram nodes, and most AIG
  tools minimize AND nodes. Neither objective is the same as total XOR plus AND
  gates when XOR and AND each cost one gate and edge negation is free.
- **Multi-output optimization.** Choosing variable orders and rewrites that
  maximize sharing across all output roots remains more important than
  optimizing each output independently.
- **Completion versus synthesis.** With partial truth tables, the completion
  that is easiest to learn need not be the completion that admits the smallest
  circuit.
- **Certificates at useful scale.** SAT can certify bounded local improvements,
  but full minimum-circuit proofs become expensive quickly and must state the
  exact gate basis and care set.

## Key bottlenecks

- **Variable ordering.** Exact order search grows exponentially; heuristic order
  search must be deterministic and scored after extraction into the target gate
  basis.
- **Representation blow-up.** Multiplication-like functions can make a BDD
  intermediate much larger than a direct arithmetic circuit.
- **Metric fidelity.** Imported tools can silently optimize a conventional AIG
  metric that charges an XOR as several AND nodes. Final scoring therefore needs
  a challenge-native graph and dead-code elimination.
- **Independent validation.** A production backend should be checked against a
  separate BDD implementation, exhaustive truth-table evaluation, and the
  official verifier.
