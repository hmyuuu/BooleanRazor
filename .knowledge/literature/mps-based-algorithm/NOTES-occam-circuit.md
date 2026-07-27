# Tensor-network Boolean learning — Issue #71 survey notes

Built by `/survey` on 2026-07-26 as the tensor-network branch of the Occam's
Circuit feasibility audit. This note is intentionally separate from the general
MPS method guidance. References use BibTeX cite keys; see `INDEX.md` and
`../ref.bib`.

## Field landscape

- **MPS classifiers.** Matrix-product-state models can learn binary
  classification functions through a product feature map and a trainable
  low-rank chain. Grokking has been observed in MPS classifiers on Fashion-MNIST
  and gene-expression data (*Literal:*
  `2503.10483_grokking-as-an-entanglement-transition-in-tensor-network-mac.md:22`)
  [@pomarico_2025_grokking], but this is not evidence of exact arithmetic
  extrapolation.
- **Tensor-train recovery.** Rigorous recovery results assume linear sensing,
  restricted-isometry conditions, and suitable initialization
  [@qin_2024_guaranteed]. The same paper says ordinary coordinate completion
  generally does not satisfy its RIP assumption and reports completion only
  numerically (*Literal:*
  `2401.02592_guaranteed-nonconvex-factorization-approach-for-tensor-train.md:1295`).
- **Exact discrete representation.** Binary Matrix Products are analogous to
  tensor trains and translate directly into BDDs (*Literal:*
  `2505.01930_a-matrix-product-state-representation-of-boolean-functions.md:26`)
  [@usturali_2025_matrix]. The correspondence depends on the discrete matrix
  form; it is not a generic real MPS-to-BDD conversion.
- **Algorithmic generalization.** Delayed generalization on small algorithmic
  datasets is established for neural networks [@power_2022_grokking], but it
  does not supply a recovery guarantee for sparse Boolean truth tables.

## Key open problems

- **Exact-row generalization.** Per-bit loss can look strong while a multi-bit
  output row is wrong. Model selection must use exact-row validation accuracy.
- **Rank and variable order.** A low-rank representation may appear only after
  a useful bit order. Order search should therefore share candidates with the
  BDD branch.
- **From real scores to exact logic.** Thresholded MPS predictions are a
  completed truth table, not a circuit. Exhaustive enumeration is the safe
  interface to an exact Boolean synthesizer.
- **Training consistency.** Observed rows must be restored after thresholding so
  the downstream completion is exactly consistent with the provided examples.

## Key bottlenecks

- **No generic completion guarantee.** Sparse coordinate observations can be
  incompatible with the assumptions behind tensor-sensing theory.
- **Numerical nondeterminism.** GPU reductions and optimization can perturb
  threshold decisions. Completed-table digests must be reproduced before a
  candidate is trusted.
- **Dependency and compile cost.** JAX-based MPS training can spend more time
  compiling than fitting these small domains; compile and steady-state time
  should be reported separately.
- **Limited role in the leaked public instance.** When a semantic arithmetic
  candidate already provides exact outputs, a learned tensor network cannot
  improve accuracy. Its value is confined to a reblinded benchmark or an
  independent completion experiment.
