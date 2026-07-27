# Occam's Circuit Rust BDD/XAG/TN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Checkboxes
> track the remaining Tasks 9–15; Tasks 1–8 retain their original TDD recipes
> under explicit completed-status lines and immutable commit IDs.

> **Migration note:** Completed-task hashes and recipes below are historical
> source-harness provenance. Their standalone equivalents are recorded in
> `docs/COMMIT_MAP.md`; source-only documentation paths are not expected to
> exist in this repository.

**Goal:** In a four-to-five-day autoresearch sprint, retain the exact v1
leaderboard solution as a leakage-disclosed control and develop a genuinely
blind, reproducible circuit learner whose publishable claim is either at least
100× lower matched-quality cost than both predeclared reproduced baselines or
a statistically supported scaling advantage over both on two larger reblinded
tiers.

**Architecture:** A team-local Rust crate owns bit encoding, complete truth
tables, a shared complemented ROBDD forest, a hash-consed XOR–AND graph (XAG),
semantic arithmetic circuits, deterministic order search, canonical challenge
serialization, and exhaustive verification. OxiDD 0.12.0 is an independent BCDD
oracle rather than the scoring authority; bounded RustSAT/CaDiCaL synthesis is
admitted only after proof-producing local tests. A separate uv/JAX project
learns a vector-output MPS on reblinded tables, enumerates every input, restores
observed rows, and passes the resulting complete table through the same Rust
ROBDD/XAG backend. A sealed evaluator and a hard-capped experiment runner keep
algorithm proposal, visible-only promotion, hidden-label confirmation, and
timing separate.

**Tech Stack:** Rust 1.93.0, Cargo edition 2024, OxiDD 0.12.0, RustSAT 0.7.5, rustsat-cadical 0.7.5, SHA-2 0.10.9, Python 3.11.13, uv, JAX 0.11.0, Optax 0.2.8, NumPy 2.5.1, pytest 9.1.1, the official Julia verifier, and Slurm through the vendored `using-slurm` workflow.

## Global Constraints

- All implementation and generated submission artifacts live in this
  repository; do not modify the source quantum.harness checkout.
- This ratified implementation plan supersedes older workflow time bands and
  cluster-routing suggestions in the feasibility audit; in particular, no
  algorithm-evaluation cell may exceed 300 seconds.
- The research sprint is limited to four to five days.
- Every algorithm-evaluation cell has a hard 300-second wall-clock limit. The
  timed region includes parsing, learning/search, completion, synthesis, and
  output writing; compilation, one-time environment construction, data
  shipping, queue delay, and external scoring are recorded but excluded.
- A timeout, OOM, nonzero exit, or verifier disagreement is a result. Never
  chain jobs or checkpoints to turn multiple five-minute cells into one longer
  algorithm run.
- Create one `codex/occam-exp-<id>` Git worktree per hypothesis and keep a
  `LOG.md` in it with parent commit, diff, command, seed, visible dataset IDs,
  hardware, elapsed time, peak memory, accuracy, gates, verifier result,
  failure classification, and next pivot.
- Source data is `https://github.com/QuantumBFS/quantum.harness/releases/download/occam-circuit-data-v1/occam-circuit.zip`, pinned by SHA-256 `c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b`.
- Treat v1 as a disclosed semantic circuit-minimization task; report blind-learning claims only on the reblinded benchmark.
- Exact-row accuracy is primary. A candidate is ineligible unless it is 100% consistent with every observed row.
- Count each reachable fan-in-two XOR or AND once across all outputs. Negated edges are free. Remove dead gates before serialization.
- Emit canonical `INPUTS`, topologically ordered gate lines, and one `OUTPUTS` line; do not exploit verifier parser quirks.
- Require deterministic stable ordering and byte-identical outputs on two reruns.
- Exhaustively compare every completed table with every emitted circuit over all inputs; the largest v1 domain is only 65,536 assignments.
- Prediction CSVs and circuits must agree for every hidden-test input.
- Compare emitted circuits and gate counts with the pinned official Julia verifier before submission.
- OxiDD node count, CUDD ordering cost, AIG AND count, and tensor rank are diagnostics; none replaces the challenge-native reachable XAG gate count.
- The proposing agent may see only the public contract, permitted training
  rows, and aggregate prior lessons. It may not see sealed labels, semantic
  family names, generator source, identifying metadata, or per-example
  evaluator feedback.
- Use `hpccube` only through the checked `hpccube.toml` profile and the
  `using-slurm` workflow. Do not submit until the exact partition, GRES, CPU,
  memory, array, and wall-time card has been shown to and accepted by the user.
- Use TDD for every production behavior: write one failing test, observe the intended failure, add minimal implementation, then rerun focused and full tests.

---

## Reviewed Challenge Contract

The hidden target is a vector Boolean function on two unsigned `n`-bit
operands. Input characters are `x` followed by `y`; both operands and every
output are least-significant-bit first. The solver receives a sparse partial
truth table, predicts the sealed rows, and emits a fan-in-two netlist using
`AND`, `OR`, `XOR`, `NAND`, `NOR`, or `XNOR`; `~` wire polarity is free.

| Instance | Input bits | Output bits | Train | Test | Observed domain |
|---|---:|---:|---:|---:|---:|
| practice-add-n4 | 8 | 5 | 120 | 136 | 47% |
| practice-mul-n4 | 8 | 8 | 120 | 136 | 47% |
| mystery-A | 16 | 9 | 2,000 | 2,000 | 3.1% |
| mystery-B | 14 | 7 | 1,500 | 2,000 | 9.2% |
| mystery-C | 12 | 12 | 1,200 | 1,500 | 29% |
| mystery-D | 10 | 11 | 400 | 624 | 39% |

The public ordering is exact-row test accuracy first and fewer gates second,
but aggregation, training eligibility, and circuit-versus-prediction authority
are underspecified. The binding safe policy is therefore:

1. require 100% training consistency;
2. require prediction/circuit agreement;
3. report all four instances independently, micro exact accuracy over all test
   rows, macro exact accuracy as the unweighted mean of four per-instance
   accuracies, per-instance gates, and summed gates; none of these derived
   aggregates is presented as an undocumented official leaderboard rule;
4. exhaustively check every v1 completed table (`2^16` rows at largest);
5. use the official Julia verifier as the external scoring authority while
   differentially checking it against Rust.

The public v1 generator, names, and widths leak the four families. The verified
mapping is A=`x+y`, B=`|x-y|`, C=`x*y`, and D=`x²+y²`; the deterministic
semantic circuits are respectively 37, 49, 168, and 127 gates. These are
competitive controls, not blind-learning evidence.

## Research Success Criteria

The issue proposes BDD, tensor-network, SAT/IP, conventional logic synthesis,
symbolic recognition, and hybrid approaches but does not provide a
leakage-resistant benchmark or an end-to-end blind learner. The publishable
claim must be made only on a custodian-generated reblinded suite with
non-identifying widths and paths, decoy families, multiple seeds, multiple
observation fractions, and at least two larger size tiers.

At matched exact-row accuracy and circuit quality, success requires either:

1. at least `100×` lower median end-to-end runtime or compute cost than both
   predeclared reproduced baselines; or
2. a statistically supported scaling advantage that solves at least two larger
   tiers inside 300 seconds where both baselines time out, exhaust memory, or
   lose exact accuracy.

For every promoted candidate, retain seeds, complete-table digest, exact-row
and bit accuracy, challenge-native reachable gates, elapsed time, peak memory,
and hardware. Report accuracy first; compare gates only among equally accurate,
training-consistent candidates.

## Current Verified State

As of commit `986d37bc8d0a8c16933975bfcd5e89c38cff7c7c`:

- Tasks 1–8 are implemented and committed in the isolated
  `codex/issue-71-occam-circuit` worktree.
- The four v1 prediction commitments match, the semantic circuits exhaustively
  match their full tables, and the official Julia verifier reports exact
  accuracy `1.0`.
- OxiDD and the custom shared ROBDD agree exhaustively.
- Beam `32×12` order search completed locally in 18.73 seconds total. Its best
  extracted XAG counts were A=58, B=240, C=2,982, and D=879, so none replaces
  the semantic control.
- Tasks 9–15 below remain: survey/benchmark freeze, experiment runner/firewall,
  blind care-set learning, bounded SAT, public-bundle import, the TN/HPC branch,
  and final comparative verification.

The checkbox steps retained under Tasks 1–8 are their original TDD execution
recipes; the explicit `Status: COMPLETE` lines and commits are authoritative.

The remaining task numbers group related implementation, but their binding
execution dependency is:

```text
Task 9 protocol/code/commit → Task 10 runner/commit
→ Task 13 public importer/commit
→ Tasks 11, 12, and 14 synthetic-test-only hypothesis commits
→ Task 10 frozen-baseline execution/release
→ Task 11 care-BDD public execution
→ Task 14 public TN/HPC gate → Task 15 sealed evaluation
```

In particular, Task 10 Step 9, Task 11 Step 8, and every Task 14 public-data
cell are blocked until Task 13's digest-checked `PublicSuite` is committed.
Baseline outcomes remain embargoed until the three candidate hypothesis commits
exist. Section order never authorizes reading a raw `TRAIN_CSV` directly.

## HPC Execution Contract

The read-only harness review on 2026-07-27 established:

- `ssh hpccube` and Slurm are reachable;
- `qdagnormal` was up with seven mixed-use nodes and one allocated node;
- the visible profile provides 64 CPU cores and eight A800 GPUs per node but
  requires at least `gpu:A800:1` for every job;
- the profile limits work to one node and arrays of at most 200 cells;
- login and compute internet are fail-closed unavailable;
- `~/BooleanRazor` does not exist remotely; and
- an exact five-minute scheduler dry run stopped at the missing checkout before
  reaching `sbatch`, so no job was queued.

This live `7 mix / 1 alloc` snapshot supersedes the older queue count in the
feasibility audit; all execution still reprobes because node state is transient.

Consequences:

- keep CPU-only BDD/XAG/order/SAT cells local unless a CPU partition is
  independently discovered and ratified; the sole exception is rerunning the
  already-frozen baseline inside the candidate's A800 allocation to obtain a
  matched-hardware comparison;
- use `hpccube` primarily for promoted GPU-backed JAX/TN cells;
- stage one exact clean source commit and a pinned Linux-compatible
  Apptainer image, wheelhouse, or binary set before the first job;
- use arrays only for independent `(instance, order, rank, seed)` cells, never
  to shard or continue one five-minute run;
- set `#SBATCH --time=00:05:00`, monitor `PD → R → terminal`, fetch artifacts,
  and classify every cell with `sacct` plus its manifest;
- preserve the sealed-data firewall on the cluster: only the evaluator job may
  read hidden labels, and fetched proposer-visible results contain aggregate
  metrics only.

The operational sequence is fixed:

```text
clean commit → stage checkout/runtime → precheck → probe-partitions
→ ratify exact job card → sbatch --test-only → submit → monitor
→ fetch → classify → append LOG.md
```

Queue delay and one-time staging do not count against the algorithm timer; all
on-node learner/completion/synthesis work does.

---

## File Map

The implementation creates these focused files:

```text

├── Cargo.toml                       # pinned Rust crate and optional SAT feature
├── Cargo.lock                       # reproducible dependency resolution
├── README.md                        # method, commands, exact results, gate table
├── src/
│   ├── lib.rs                       # public module boundary
│   ├── bits.rs                      # LSB-first bit parsing/encoding
│   ├── table.rs                     # partial/input/complete truth tables and CSV bytes
│   ├── xag.rs                       # hash-consed complemented XOR–AND graph
│   ├── netlist.rs                   # canonical challenge parser/serializer/evaluator
│   ├── arithmetic.rs                # add, absdiff, multiply, square/sum-square circuits
│   ├── instances.rs                 # immutable A–D contracts and semantic functions
│   ├── robdd.rs                     # shared complemented multi-root ROBDD
│   ├── oxidd_oracle.rs              # OxiDD 0.12 BCDD differential oracle
│   ├── order.rs                     # deterministic order seeds/search/scoring
│   ├── baseline.rs                  # frozen zero-fill/Hamming blind baselines
│   ├── care_bdd.rs                  # blind fixed-order care-set completion
│   ├── sat.rs                       # bounded exact local XAG synthesis
│   ├── reblind.rs                   # public-bundle importer and leakage checks
│   └── main.rs                      # `occam` command-line entry point
├── tests/
│   ├── bits_table.rs
│   ├── xag_netlist.rs
│   ├── arithmetic.rs
│   ├── robdd.rs
│   ├── oxidd_oracle.rs
│   ├── order.rs
│   ├── baseline.rs
│   ├── care_bdd.rs
│   ├── official_v1.rs
│   ├── sat.rs
│   └── determinism.rs
├── scripts/
│   ├── fetch-v1.sh                  # checksum-verified public archive fetch
│   ├── verify-julia.sh              # official verifier differential
│   ├── run-experiment.py            # process-group 300 s cap + result manifest
│   ├── materialize-slurm-failures.py # terminal evidence for pre-run failures
│   └── run-tn-cell.sh               # one harness-native end-to-end TN cell
├── autoresearch/
│   ├── LOG_TEMPLATE.md              # required per-worktree experiment record
│   ├── README.md                    # proposal/evaluator firewall and promotion
│   ├── test_run_experiment.py       # timeout/process-group/manifest tests
│   └── test_materialize_slurm_failures.py
├── research/
│   ├── SURVEY.md                    # reviewed SOTA and explicit research gap
│   ├── BASELINE_MATRIX.csv          # exact frozen 2 × 180 execution keys
│   ├── BASELINE_MATRIX.sha256       # canonical matrix commitment
│   ├── BASELINES.csv                # matched-hardware baseline evidence
│   ├── BENCHMARK_PROTOCOL.md        # sealed custodian/proposer/evaluator contract
│   ├── FROZEN_COMPARISON.json       # one candidate/config and two fixed baselines
│   ├── DEVELOPMENT_RESULTS.csv       # visible-only selection evidence
│   ├── RESULTS.csv                  # matched blind/candidate evaluation rows
│   ├── MANIFESTS.ndjson             # sanitized content-addressed run evidence
│   ├── MANIFESTS.sha256             # canonical evidence-file commitment
│   ├── run-specs/                    # tracked canonical experiment matrices
│   │   ├── tn-smoke.json
│   │   ├── tn-pilot.json
│   │   ├── candidate-r0.json
│   │   ├── candidate-r1.json
│   │   ├── baseline-zero-r0.json
│   │   ├── baseline-zero-r1.json
│   │   ├── baseline-hamming-r0.json
│   │   └── baseline-hamming-r1.json
│   ├── FINAL_REPORT.md              # evidence and research decision
│   ├── analyze.py                   # paired statistics and scaling decision
│   ├── test_analyze.py              # fail-closed statistical-contract tests
│   ├── check_gate.py                # fail-closed survey/baseline/schema validator
│   ├── test_check_gate.py            # frozen-matrix/evidence/leakage regressions
│   ├── accuracy-gate-runtime.png     # primary accuracy-first comparison
│   └── scaling.png                  # capped runtime/memory tier scaling
├── data/
│   └── README.md                    # external-data provenance, never hidden labels
├── mystery-A.txt                    # final reachable canonical circuit
├── mystery-B.txt
├── mystery-C.txt
├── mystery-D.txt
├── predictions/
│   ├── mystery-A/test_outputs.csv
│   ├── mystery-B/test_outputs.csv
│   ├── mystery-C/test_outputs.csv
│   └── mystery-D/test_outputs.csv
├── reblind/
│   ├── COMMITMENT.txt               # pre-experiment public suite commitment
│   ├── manifest.csv                 # opaque ID/shape/fraction/public digest only
│   ├── README.md                    # public schema and post-freeze reveal policy
│   └── revealed-after-freeze/
│       ├── generator.rs             # post-freeze reproducible custodian generator
│       ├── seeds.json               # revealed committed secret seeds
│       ├── mapping.csv              # opaque ID to family mapping
│       └── AUDIT.md                 # commitment regeneration and leakage audit
└── tn/
    ├── pyproject.toml               # isolated uv/JAX environment
    ├── uv.lock
    ├── src/occam_tn/
    │   ├── __init__.py
    │   ├── data.py                  # Rust-table interchange
    │   ├── model.py                 # vector-output open-boundary MPS
    │   ├── train.py                 # deterministic fitting primitives
    │   ├── pipeline.py              # timed train/enumerate/Rust-synthesis cell
    │   └── hpc_cell.py              # in-image run-spec/runner coordinator
    ├── hpc/
    │   ├── run_spec.template.json   # harness-native 1-based cells
    │   ├── job_card.json            # partition/GRES/CPU/memory/time contract
    │   ├── occam-tn.def             # pinned offline Apptainer recipe
    │   ├── .gitignore               # excludes *.sif images
    │   └── README.md                # image digest, CUDA/JAX, staging evidence
    └── tests/
        ├── test_model.py
        ├── test_train.py
        └── test_hpc_contract.py
```

## Core Interfaces

Later tasks must preserve these exact boundaries:

```rust
pub struct PartialTable {
    pub ninputs: usize,
    pub noutputs: usize,
    pub rows: Vec<(Vec<bool>, Vec<bool>)>,
}
pub struct InputTable { pub ninputs: usize, pub rows: Vec<Vec<bool>> }
pub struct CompleteTable { pub ninputs: usize, pub noutputs: usize, pub outputs: Vec<Vec<bool>> }

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Lit { base: Base, inverted: bool }
pub struct Xag { ninputs: usize, nodes: Vec<Node>, unique: HashMap<NodeKey, Lit> }
pub enum Family { Add, AbsDiff, Multiply, SumSquares }
pub struct Circuit { pub graph: Xag, pub outputs: Vec<Lit> }

pub struct BddEdge { pub node: u32, pub inverted: bool }
pub struct SharedRobdd { nvars: usize, order: Vec<usize>, nodes: Vec<BddNode> }
pub struct OrderScore { pub order: Vec<usize>, pub bdd_nodes: usize, pub xag_gates: usize }

pub enum EmptyCarePolicy { ReuseSibling, Zero }
pub struct BlindScore {
    pub order: Vec<usize>,
    pub policy: EmptyCarePolicy,
    pub validation_exact_rows: usize,
    pub validation_rows: usize,
    pub validation_bit_correct: usize,
    pub validation_bits: usize,
    pub refit_xag_gates: usize,
    pub refit_bdd_nodes: usize,
}
pub fn complete_care_set(
    table: &PartialTable,
    order: &[usize],
    policy: EmptyCarePolicy,
) -> Result<(CompleteTable, Circuit), String>;
```

The complete-table row at index `mask` is the output for the assignment whose
input bit `i` is `(mask >> i) & 1`; this matches the challenge's LSB-first
character positions.

---

### Task 1: Create the Team-Local Rust Crate and Pin the Challenge Contract

**Status:** COMPLETE in `61df571` plus contract-test hardening in `018973e`.

**Standalone note:** The recipe below is the preserved source-harness record.
Its `docs/qcs/...` audit path was not exported; the ratified conclusions now
live in `GOAL.md`, this plan, and `docs/handoff/SESSION_HANDOFF.md`.

**Files:**
- Create: `Cargo.toml`
- Create: `src/lib.rs`
- Create: `src/instances.rs`
- Create: `tests/official_v1.rs`
- Create: `data/README.md`
- Modify: `docs/qcs/2026-07-26-occam-circuit-contract-and-feasibility-audit.md`

**Interfaces:**
- Consumes: the pinned release digest and reconstructed family identities from the audit.
- Produces: `Family`, `InstanceSpec`, `MYSTERY_INSTANCES`, and `semantic_output`.

- [ ] **Step 1: Mark the design audit ratified**

Change its status line to:

```markdown
Status: scope ratified by the user on 2026-07-26; implementation proceeds in
the standalone BooleanRazor repository.
```

- [ ] **Step 2: Write a failing contract test**

```rust
use occam_circuit_hmyuuu::instances::{semantic_output, Family, MYSTERY_INSTANCES};

#[test]
fn v1_contract_is_exact_and_fixed() {
    let dims: Vec<_> = MYSTERY_INSTANCES
        .iter()
        .map(|s| (s.slug, s.input_bits, s.output_bits, s.family))
        .collect();
    assert_eq!(dims, vec![
        ("mystery-A", 16, 9, Family::Add),
        ("mystery-B", 14, 7, Family::AbsDiff),
        ("mystery-C", 12, 12, Family::Multiply),
        ("mystery-D", 10, 11, Family::SumSquares),
    ]);
    assert_eq!(semantic_output(Family::Add, 8, 255, 255), 510);
    assert_eq!(semantic_output(Family::AbsDiff, 7, 3, 90), 87);
    assert_eq!(semantic_output(Family::Multiply, 6, 63, 63), 3969);
    assert_eq!(semantic_output(Family::SumSquares, 5, 31, 31), 1922);
}
```

- [ ] **Step 3: Run the test and observe the intended failure**

Run:

```bash
cargo test --manifest-path Cargo.toml --test official_v1
```

Expected: failure because `Cargo.toml` and `instances` do not exist.

- [ ] **Step 4: Add the minimal crate and immutable instance definitions**

Use this manifest:

```toml
[package]
name = "occam-circuit-hmyuuu"
version = "0.1.0"
edition = "2024"
rust-version = "1.93"
publish = false

[features]
default = ["oxidd-oracle"]
oxidd-oracle = ["dep:oxidd"]
sat = ["dep:rustsat", "dep:rustsat-cadical"]

[dependencies]
oxidd = { version = "=0.12.0", default-features = false, features = ["manager-index", "bcdd", "apply-cache-direct-mapped"], optional = true }
rustsat = { version = "=0.7.5", optional = true }
rustsat-cadical = { version = "=0.7.5", optional = true }
sha2 = "=0.10.9"
```

Implement:

```rust
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Family { Add, AbsDiff, Multiply, SumSquares }

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InstanceSpec {
    pub slug: &'static str,
    pub input_bits: usize,
    pub output_bits: usize,
    pub family: Family,
    pub commitment: &'static str,
}

pub const MYSTERY_INSTANCES: [InstanceSpec; 4] = [
    InstanceSpec { slug: "mystery-A", input_bits: 16, output_bits: 9, family: Family::Add, commitment: "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7" },
    InstanceSpec { slug: "mystery-B", input_bits: 14, output_bits: 7, family: Family::AbsDiff, commitment: "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28" },
    InstanceSpec { slug: "mystery-C", input_bits: 12, output_bits: 12, family: Family::Multiply, commitment: "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d" },
    InstanceSpec { slug: "mystery-D", input_bits: 10, output_bits: 11, family: Family::SumSquares, commitment: "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580" },
];

pub fn semantic_output(family: Family, _n: usize, x: u64, y: u64) -> u64 {
    match family {
        Family::Add => x + y,
        Family::AbsDiff => x.abs_diff(y),
        Family::Multiply => x * y,
        Family::SumSquares => x * x + y * y,
    }
}
```

Export `pub mod instances;` from `src/lib.rs`.

- [ ] **Step 5: Document external-data provenance**

`data/README.md` must contain the exact download URL, archive digest, extraction
command, and the rule that hidden labels are never committed as benchmark
training input.

- [ ] **Step 6: Run focused and baseline tests**

Run:

```bash
cargo test --manifest-path Cargo.toml --test official_v1
source .venv/bin/activate && make test
```

Expected: Rust contract test passes; harness remains `223 passed`.

- [ ] **Step 7: Commit**

```bash
git add docs/qcs/2026-07-26-occam-circuit-contract-and-feasibility-audit.md \
  Cargo.toml \
  Cargo.lock \
  src/lib.rs \
  src/instances.rs \
  tests/official_v1.rs \
  data/README.md
git commit -m "feat(qcs): pin Occam Circuit v1 contract"
```

---

### Task 2: Implement LSB-First Bits, CSV Parsing, and Complete Truth Tables

**Status:** COMPLETE in `874595b` plus validation hardening in `af8b55f`.

**Files:**
- Create: `src/bits.rs`
- Create: `src/table.rs`
- Create: `tests/bits_table.rs`
- Modify: `src/lib.rs`

**Interfaces:**
- Consumes: `InstanceSpec` and `semantic_output`.
- Produces: `parse_bits`, `encode_bits`, `decode_lsb`, `PartialTable::parse`, `InputTable::parse`, `CompleteTable::from_fn`, `prediction_csv_bytes`, and `sha256_hex`.

- [ ] **Step 1: Write failing bit-order and byte-contract tests**

```rust
use occam_circuit_hmyuuu::bits::{decode_lsb, encode_lsb, parse_bits};
use occam_circuit_hmyuuu::table::{prediction_csv_bytes, CompleteTable, InputTable};

#[test]
fn lsb_first_round_trip_matches_release_example() {
    let bits = parse_bits("1011", 4).unwrap();
    assert_eq!(decode_lsb(&bits), 13);
    assert_eq!(encode_lsb(13, 4), bits);
}

#[test]
fn prediction_bytes_have_exact_header_order_and_final_newline() {
    let inputs = InputTable::parse("input\n0000\n1000\n", 4).unwrap();
    let table = CompleteTable::from_fn(4, 3, |mask| (mask & 3) + ((mask >> 2) & 3));
    let bytes = prediction_csv_bytes(&inputs, &table).unwrap();
    assert_eq!(bytes, b"input,output\n0000,000\n1000,100\n");
}
```

- [ ] **Step 2: Run and observe missing-module failures**

Run:

```bash
cargo test --manifest-path Cargo.toml --test bits_table
```

Expected: unresolved `bits` and `table` modules.

- [ ] **Step 3: Implement strict parsing and encoding**

`parse_bits` accepts only exactly `width` ASCII `0`/`1` bytes. `decode_lsb`
sets integer bit `i` from vector element `i`; `encode_lsb` returns exactly
`width` booleans and rejects overflow through a separate
`encode_lsb_checked(value, width) -> Result<Vec<bool>, String>`.

- [ ] **Step 4: Implement table invariants**

`PartialTable::parse` must require header `input,output`, one comma per row,
fixed widths, no duplicate input with conflicting output, and at least one row.
`InputTable::parse` accepts canonical `input` and the release's
`input`-only rows. `CompleteTable::from_fn` must enumerate masks in increasing
integer order and store each output as an LSB-first vector.

Use:

```rust
pub fn row_index(input: &[bool]) -> usize {
    input.iter().enumerate().fold(0usize, |mask, (i, bit)| {
        if *bit { mask | (1usize << i) } else { mask }
    })
}

pub fn prediction_csv_bytes(
    inputs: &InputTable,
    completed: &CompleteTable,
) -> Result<Vec<u8>, String> {
    if inputs.ninputs != completed.ninputs {
        return Err("input width does not match completed table".into());
    }
    let mut out = String::from("input,output\n");
    for input in &inputs.rows {
        let idx = row_index(input);
        out.push_str(&encode_bits(input));
        out.push(',');
        out.push_str(&encode_bits(&completed.outputs[idx]));
        out.push('\n');
    }
    Ok(out.into_bytes())
}
```

- [ ] **Step 5: Add malformed-input tests**

Cover wrong headers, non-binary characters, wrong widths, duplicate conflicts,
missing rows, table-width mismatch, and overflow. Each test must assert the
stable error substring.

- [ ] **Step 6: Run tests and commit**

```bash
cargo test --manifest-path Cargo.toml --test bits_table
cargo test --manifest-path Cargo.toml
git add src/bits.rs \
  src/table.rs \
  src/lib.rs \
  tests/bits_table.rs
git commit -m "feat(qcs): add strict Occam truth tables"
```

---

### Task 3: Build the Challenge-Native Complemented XAG and Canonical Netlist

**Status:** COMPLETE in `d2a5cd4` plus provenance hardening in `bd617a3`.

**Files:**
- Create: `src/xag.rs`
- Create: `src/netlist.rs`
- Create: `tests/xag_netlist.rs`
- Modify: `src/lib.rs`

**Interfaces:**
- Consumes: Boolean inputs in release order.
- Produces: `Lit`, `Xag::{input,and,xor,or,mux,evaluate,reachable_gate_count,compact}`, `Circuit::{evaluate,to_netlist}`, and `Netlist::parse`.

- [ ] **Step 1: Write failing algebra, sharing, and serialization tests**

```rust
use occam_circuit_hmyuuu::xag::{Circuit, Xag};

#[test]
fn xag_simplifies_and_hash_conses_in_challenge_metric() {
    let mut g = Xag::new(2);
    let a = g.input(0);
    let b = g.input(1);
    assert_eq!(g.xor(a, a), g.f());
    assert_eq!(g.and(a, !a), g.f());
    let p = g.xor(a, b);
    assert_eq!(p, g.xor(b, a));
    assert_eq!(g.reachable_gate_count(&[p]), 1);
}

#[test]
fn netlist_round_trip_counts_only_reachable_binary_gates() {
    let mut g = Xag::new(2);
    let a = g.input(0);
    let b = g.input(1);
    let dead = g.and(a, b);
    let out = g.xor(a, b);
    assert_ne!(dead, out);
    let text = Circuit::new(g, vec![out]).to_netlist().unwrap();
    assert_eq!(text, "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n");
}
```

- [ ] **Step 2: Run and observe missing-module failures**

```bash
cargo test --manifest-path Cargo.toml --test xag_netlist
```

- [ ] **Step 3: Implement complemented literals and hash-consing**

Use one internal false constant, input bases, and gate bases. Negation flips
only `inverted`; it never creates a node. Canonicalize commutative operands by
`Ord`. Required identities:

```text
a XOR 0 = a          a XOR 1 = ~a
a XOR a = 0          a XOR ~a = 1
a AND 0 = 0          a AND 1 = a
a AND a = a          a AND ~a = 0
OR(a,b) = ~(~a AND ~b)
MUX(s,t,e) = e XOR (s AND (t XOR e))
```

`and` and `xor` must return an existing node when the normalized `(op,a,b)` key
already exists.

- [ ] **Step 4: Implement exhaustive evaluation and reachable compaction**

`Circuit::evaluate(&[bool])` rejects a width mismatch and evaluates nodes once
in topological order. `compact` performs a reverse reachability walk from all
outputs, remaps only live gates, preserves free edge polarity, and returns a
topologically ordered graph.

- [ ] **Step 5: Implement canonical challenge serialization and parsing**

Emit only `AND` and `XOR`. Map inputs to `x1..xN`, compact gates to `w1..wK`,
prefix `~` for an inverted literal, and materialize constants only if an output
is constant (`0 = XOR x1 x1`, `1 = ~0`). The parser accepts the official six
gate names for differential checking but the serializer never emits the four
derived forms.

- [ ] **Step 6: Add exhaustive two- and three-input truth-table tests**

For every assignment, compare `and`, `xor`, `or`, `mux`, complemented outputs,
serialized parsing, and evaluation. Add a dead-gate test proving the serialized
line count equals `reachable_gate_count`.

- [ ] **Step 7: Run, format, and commit**

```bash
cargo fmt --manifest-path Cargo.toml
cargo test --manifest-path Cargo.toml --test xag_netlist
cargo test --manifest-path Cargo.toml
git add src/xag.rs \
  src/netlist.rs \
  src/lib.rs \
  tests/xag_netlist.rs
git commit -m "feat(qcs): add challenge-native XAG netlists"
```

---

### Task 4: Synthesize and Exhaustively Test the Four Semantic Arithmetic Circuits

**Status:** COMPLETE in `3741f4c` plus width hardening in `b76e52b`.

**Files:**
- Create: `src/arithmetic.rs`
- Create: `tests/arithmetic.rs`
- Modify: `src/lib.rs`

**Interfaces:**
- Consumes: `Xag`, `Lit`, `Family`.
- Produces: `ripple_add`, `unsigned_multiply`, `absolute_difference`, `synthesize_family`.

- [ ] **Step 1: Write failing exhaustive tests**

```rust
use occam_circuit_hmyuuu::arithmetic::synthesize_family;
use occam_circuit_hmyuuu::instances::{semantic_output, Family};

fn exhaustive(family: Family, n: usize, m: usize) {
    let circuit = synthesize_family(family, n, m).unwrap();
    for x in 0..(1u64 << n) {
        for y in 0..(1u64 << n) {
            let mut input = Vec::with_capacity(2 * n);
            input.extend((0..n).map(|i| ((x >> i) & 1) != 0));
            input.extend((0..n).map(|i| ((y >> i) & 1) != 0));
            let got = circuit.evaluate_u64(&input).unwrap();
            assert_eq!(got, semantic_output(family, n, x, y), "{family:?} x={x} y={y}");
        }
    }
}

#[test] fn add_n8_is_exact() { exhaustive(Family::Add, 8, 9); }
#[test] fn absdiff_n7_is_exact() { exhaustive(Family::AbsDiff, 7, 7); }
#[test] fn multiply_n6_is_exact() { exhaustive(Family::Multiply, 6, 12); }
#[test] fn sum_squares_n5_is_exact() { exhaustive(Family::SumSquares, 5, 11); }
```

- [ ] **Step 2: Run and observe the intended missing-function failure**

```bash
cargo test --manifest-path Cargo.toml --test arithmetic
```

- [ ] **Step 3: Implement the verified ripple primitives**

For a full-adder bit, create:

```rust
let propagate = g.xor(a, b);
let sum = g.xor(propagate, carry);
let generate = g.and(a, b);
let carried = g.and(propagate, carry);
let next = g.xor(generate, carried); // terms are mutually exclusive
```

The least-significant bit with false carry uses only `a XOR b` and `a AND b`.
An n-bit addition with carry output therefore starts at the known 5n−3-gate
ripple baseline before global sharing.

- [ ] **Step 4: Implement absolute difference without a semantic mux**

First ripple-subtract `d = x − y mod 2ⁿ` and retain final borrow `mask`.
Use:

```text
p_i      = x_i XOR y_i
d_i      = p_i XOR borrow_i
borrow'  = (~x_i AND y_i) XOR (~p_i AND borrow_i)
abs      = (d XOR mask) + mask
```

The two borrow terms are mutually exclusive. Conditionally negate `d` with the
prefix invariant `q_i = mask AND OR(d_0..d_(i−1))`:

```text
z_0 = d_0
q_1 = mask AND d_0
z_i = d_i XOR q_i
q_(i+1) = q_i OR (mask AND d_i)
```

Do not build `q_n` after the last output. This stage costs `3n−4`, giving the
verified `8n−7 = 49` gate upper bound for B.

- [ ] **Step 5: Implement multiplication and squaring**

For C, generate all 36 partial products and reduce weighted columns with
half-adders (two gates) and full-adders (five gates). The deterministic baseline
uses 24 full-adders and six half-adders, giving
`36 + 24×5 + 6×2 = 168` gates.

For D, do not materialize two generic multipliers. Use
`x_i² = x_i` and the doubled cross terms
`(x_i AND x_j) << (i+j+1)`. Place the x and y terms in one bit heap and reduce
them jointly. The deterministic baseline is 20 cross-term ANDs, 19 full-adders,
and six half-adders, giving `20 + 19×5 + 6×2 = 127` gates.

- [ ] **Step 6: Add structural regression assertions**

Assert:

- A's initial semantic circuit has exactly 37 reachable gates.
- B's initial semantic circuit has exactly 49 reachable gates.
- C's deterministic compressor circuit has exactly 168 reachable gates.
- D's joint square-sum compressor has exactly 127 reachable gates.
- every circuit emits the declared output width;
- C and D compressor identities satisfy `a+b = sum+2carry` at every cell;
- all four netlists parse back and remain exhaustively equivalent.

Treat all four counts as constructive upper bounds, not minimality claims.
After the deterministic baseline is green, search stable compressor schedules
and full-adder input pairings; C=165 and D=120 are targets from an independent
in-memory exploration, not accepted results.

- [ ] **Step 7: Run release-scale exhaustive tests and commit**

```bash
cargo test --release --manifest-path Cargo.toml --test arithmetic -- --nocapture
cargo test --manifest-path Cargo.toml
git add src/arithmetic.rs \
  src/lib.rs \
  tests/arithmetic.rs
git commit -m "feat(qcs): synthesize exact v1 arithmetic circuits"
```

Expected: all four domains pass; no single test exceeds the local ten-minute
threshold.

---

### Task 5: Generate Commitment-Matching Predictions and Final-Format Circuits

**Status:** COMPLETE in `08225d4` plus transaction hardening in `39b4bc7`.

**Files:**
- Create: `src/main.rs`
- Create: `scripts/fetch-v1.sh`
- Create: `tests/determinism.rs`
- Modify: `tests/official_v1.rs`
- Create after verification: `mystery-A.txt`
- Create after verification: `mystery-B.txt`
- Create after verification: `mystery-C.txt`
- Create after verification: `mystery-D.txt`
- Create after verification: `predictions/mystery-A/test_outputs.csv`
- Create after verification: `predictions/mystery-B/test_outputs.csv`
- Create after verification: `predictions/mystery-C/test_outputs.csv`
- Create after verification: `predictions/mystery-D/test_outputs.csv`

**Interfaces:**
- Consumes: public archive root, instance specs, semantic circuits/tables.
- Produces: `occam solve-v1 DATA_ROOT OUTPUT_ROOT` and byte-exact committed artifacts.

- [ ] **Step 1: Write a failing integration test against the pinned archive**

The test reads `OCCAM_V1_ROOT`; if absent, it prints a single skip line and
returns. When set, it must:

1. parse every `train.csv`;
2. assert every row equals the semantic function;
3. generate prediction bytes in test-input order;
4. hash them with SHA-256;
5. assert the digest equals `InstanceSpec::commitment`;
6. exhaustively compare the emitted circuit with the semantic table.

The digest assertion is:

```rust
assert_eq!(sha256_hex(&prediction_bytes), spec.commitment, "{}", spec.slug);
```

- [ ] **Step 2: Run and observe the missing CLI/generation failure**

```bash
OCCAM_V1_ROOT=/tmp/occam71-audit.03qN9w/extracted/occam-circuit \
cargo test --release --manifest-path Cargo.toml \
  --test official_v1 -- --nocapture
```

- [ ] **Step 3: Implement `solve-v1` with atomic output replacement**

Generate each artifact in a sibling temporary file, validate it, then rename it
to its final name. Abort before replacing any final file if training consistency,
prediction commitment, exhaustive circuit equivalence, or
prediction-versus-circuit equality fails.

Command:

```bash
cargo run --release --manifest-path Cargo.toml -- \
  solve-v1 /tmp/occam71-audit.03qN9w/extracted/occam-circuit \
  .
```

It prints one flushed line per instance:

```text
mystery-A exact=1 train=2000/2000 commitment=match gates=37
```

- [ ] **Step 4: Add checksum-verified fetch script**

The script downloads to a temporary directory, verifies the exact SHA-256, and
extracts only after a match. It never overwrites an existing extraction unless
that extraction contains the same recorded archive digest.

- [ ] **Step 5: Prove deterministic reruns**

Run `solve-v1` twice into two fresh temporary roots. The test recursively hashes
all eight submission artifacts and asserts identical relative paths and bytes.

- [ ] **Step 6: Run and commit exact outputs**

```bash
OCCAM_V1_ROOT=/tmp/occam71-audit.03qN9w/extracted/occam-circuit \
cargo test --release --manifest-path Cargo.toml \
  --test official_v1 --test determinism -- --nocapture
git add src/main.rs \
  scripts/fetch-v1.sh \
  tests/official_v1.rs \
  tests/determinism.rs \
  mystery-A.txt \
  mystery-B.txt \
  mystery-C.txt \
  mystery-D.txt \
  predictions/mystery-A/test_outputs.csv \
  predictions/mystery-B/test_outputs.csv \
  predictions/mystery-C/test_outputs.csv \
  predictions/mystery-D/test_outputs.csv
git commit -m "feat(qcs): generate commitment-matching v1 submission"
```

Expected: all four commitment digests report `match`.

---

### Task 6: Implement the Shared Complemented ROBDD Forest and XAG Extraction

**Status:** COMPLETE in `5c27627` plus bit-parallel validation in `c0074df`.

**Files:**
- Create: `src/robdd.rs`
- Create: `tests/robdd.rs`
- Modify: `src/lib.rs`
- Modify: `src/xag.rs`

**Interfaces:**
- Consumes: `CompleteTable`, fixed permutation of all input variables.
- Produces: `SharedRobdd::build`, `roots`, `shared_node_count`, `evaluate`,
  `evaluate_mask`, `validate_invariants`, and `extract_xag`.

- [ ] **Step 1: Write failing canonicalization and shared-root tests**

```rust
#[test]
fn complemented_forest_shares_outputs_and_extracts_exact_xag() {
    let table = CompleteTable::from_fn(3, 2, |mask| {
        let parity = (mask.count_ones() & 1) as usize;
        parity | ((parity ^ 1) << 1)
    });
    let forest = SharedRobdd::build(&table, vec![0, 1, 2]).unwrap();
    assert_eq!(forest.roots()[1], !forest.roots()[0]);
    assert_eq!(forest.shared_node_count(), forest.reachable_node_ids().len());
    let circuit = forest.extract_xag().unwrap();
    for mask in 0..8 {
        let input = encode_lsb(mask as u64, 3);
        assert_eq!(circuit.evaluate(&input).unwrap(), table.outputs[mask]);
    }
}
```

- [ ] **Step 2: Run and observe the missing-module failure**

```bash
cargo test --manifest-path Cargo.toml --test robdd
```

- [ ] **Step 3: Implement canonical complemented nodes**

Use one false terminal (`node == 0`) and a complement bit on every edge.
`mk(var, low, high)`:

1. returns `low` when `low == high`;
2. if `low` is complemented, complements both children, interns the normalized
   node, and complements the returned edge;
3. otherwise interns `(var, low, high)` exactly once.

Build every output root in one manager so all output bits share nodes.

- [ ] **Step 4: Extract using the challenge-efficient Shannon identity**

Memoize one XAG literal per non-complemented BDD node and use:

```text
f = low XOR (x_var AND (low XOR high))
```

Apply the incoming complement bit only to the returned literal. Compact the
result once across every output root. Use the remapped outputs returned by
compaction; the pre-compaction literals have a different XAG owner and must be
rejected by provenance checks. `extract_xag` returns `Result<Circuit, String>`.

- [ ] **Step 5: Add exhaustive order/property tests**

For all Boolean functions of zero to three variables and every permutation
(including the single empty order for zero variables):

- construction matches the complete table;
- reduction never retains `low == high`;
- normalized nodes never have a complemented low edge;
- the unique table has no duplicate keys;
- extracted XAG matches all rows;
- shared node count is a union, never a sum over roots.
- paired `[f, ¬f]` roots are complements and have the same shared count as `f`.

Add `Circuit::reachable_gate_count() -> Result<usize, String>` so the diagnostic
comparison does not infer reachability from serialized text.

- [ ] **Step 6: Compare semantic and ROBDD candidates**

For A–D, record `bdd_nodes` and extracted `xag_gates` for grouped and
least-significant-bit-interleaved orders, and exhaustively verify each extracted
circuit. This task is diagnostic only: do not replace the semantic submission.
Candidate provenance and the common promotion gate belong to Task 15.

- [ ] **Step 7: Run and commit**

```bash
cargo test --release --manifest-path Cargo.toml --test robdd -- --nocapture
git add src/robdd.rs \
  src/xag.rs \
  src/lib.rs \
  tests/robdd.rs
git commit -m "feat(qcs): add shared complemented ROBDD synthesis"
```

---

### Task 7: Add OxiDD 0.12 as an Independent BCDD Oracle

**Status:** COMPLETE in `173e21c`.

**Files:**
- Create: `src/oxidd_oracle.rs`
- Create: `tests/oxidd_oracle.rs`
- Modify: `src/lib.rs`

**Interfaces:**
- Consumes: `CompleteTable`, fixed order.
- Produces: `OxiddForest::build`, `evaluate_mask`, per-root `node_count`, and full-table differential results. It does not serialize circuits or define the score.

- [ ] **Step 1: Write a failing custom-versus-OxiDD test**

```rust
#[test]
fn oxidd_bcdd_agrees_with_custom_forest_on_every_assignment() {
    let table = CompleteTable::from_fn(6, 6, |mask| {
        let x = mask & 7;
        let y = (mask >> 3) & 7;
        x * y
    });
    let order = vec![0, 3, 1, 4, 2, 5];
    let custom = SharedRobdd::build(&table, order.clone()).unwrap();
    let oracle = OxiddForest::build(&table, order).unwrap();
    for mask in 0..64 {
        assert_eq!(oracle.evaluate_mask(mask), custom.evaluate_mask(mask));
    }
}
```

- [ ] **Step 2: Run and observe the missing adapter failure**

```bash
cargo test --manifest-path Cargo.toml --test oxidd_oracle
```

- [ ] **Step 3: Build one manager and fixed-order variables**

Use `oxidd::bcdd::new_manager(1 << 20, 1 << 18, 1)`. Allocate all variables
inside one `manager.with_manager_exclusive` closure using `m.add_vars`, and
construct owned `BCDDFunction::var(m, var)` values there. Leave the exclusive
closure before calling public function operations such as `ite`, which acquire
the manager again. Rank `r` receives `VarNo(r)`, while `order[r]` is the
corresponding logical input; retain both logical-input↔`VarNo` mappings.
Recursively build each truth-column root with
`condition.ite(&high, &low)` and keep all roots in the same manager. Use one
thread for deterministic construction.

- [ ] **Step 4: Use public function APIs only**

Use `Function::cofactors`, `Function::node_count`, and `BooleanFunction::eval`
for diagnostics. `cofactors()` returns `(high, low)`. Supply every `(VarNo,
value)` pair to `eval`; omitted variables default to false. Do not sum
`node_count()` and label it a shared-forest size. Under one
`with_manager_shared` lock, convert roots with `as_edge`, traverse children via
the manager, and insert tag-insensitive `Edge::node_id()` values into one
`HashSet<NodeID>`. Do not call public function methods from inside that lock.
OxiDD regularizes the high edge whereas the custom forest regularizes the low
edge, so compare exhaustive semantics and the shared node union—not raw edge
polarities or child structure.

- [ ] **Step 5: Add release-scale oracle checks**

Cross-check all four semantic complete tables sequentially for at least grouped
and interleaved orders so eight large managers are never live concurrently.
Add focused swapped-order, ITE/cofactor, complement-identity, invalid-order, and
malformed-table tests. Any OxiDD/custom semantic or shared-count disagreement is
a release blocker.

- [ ] **Step 6: Run with locked dependencies and commit**

```bash
cargo test --locked --release --manifest-path Cargo.toml --test oxidd_oracle -- --nocapture
git add src/oxidd_oracle.rs \
  src/lib.rs \
  tests/oxidd_oracle.rs
git commit -m "test(qcs): cross-check ROBDDs with OxiDD"
```

---

### Task 8: Search Variable Orders by Extracted XAG Cost

**Status:** COMPLETE in `986d37b`.

**Files:**
- Create: `src/order.rs`
- Create: `tests/order.rs`
- Modify: `src/lib.rs`
- Modify: `src/instances.rs`
- Modify: `src/main.rs`

**Interfaces:**
- Consumes: complete table and candidate permutation.
- Produces: `OrderScore`, table-owned `OrderScorer`, `seed_orders`,
  `adjacent_hill_climb`, `beam_search`, and stable CSV result rows.

- [ ] **Step 1: Write failing deterministic search tests**

```rust
#[test]
fn search_is_stable_and_scores_xag_not_only_bdd_nodes() {
    let table = CompleteTable::from_fn(6, 6, |mask| {
        let x = mask & 7;
        let y = (mask >> 3) & 7;
        x + y
    });
    let seeds = seed_orders(3).unwrap();
    let mut first = OrderScorer::new(&table).unwrap();
    let mut second = OrderScorer::new(&table).unwrap();
    let a = beam_search(&mut first, &seeds, 8, 3).unwrap();
    let b = beam_search(&mut second, &seeds, 8, 3).unwrap();
    assert_eq!(a, b);
    assert!(a.finalists.windows(2)
        .all(|w| w[0].ranking_key() <= w[1].ranking_key()));
}
```

Also prove with synthetic scores that XAG gates rank before BDD nodes, then BDD
nodes, then numeric lexicographic order. Test malformed permutations, exact
seed order/deduplication for operand widths zero through two, cache hits,
adjacency, hard round bounds, plateau stopping, callback errors, and exact CSV
bytes.

- [ ] **Step 2: Run and observe the missing search failure**

```bash
cargo test --manifest-path Cargo.toml --test order
```

- [ ] **Step 3: Implement order seeds and ranking**

For two n-bit operands generate, in this exact sequence:

- grouped LSB: `x0..x(n−1), y0..y(n−1)`;
- grouped MSB;
- interleaved LSB: `x0,y0,x1,y1,...`;
- interleaved MSB;
- the reverse of those four, in the same sequence.

Preserve first occurrence while deduplicating repeated seed permutations; a
duplicate variable inside one permutation remains an error. Rank exactly by
`(xag_gates, bdd_nodes, order_lexicographically)`. A table-owned scorer caches
scalar scores by the full permutation and never retains forests or managers.
Expose `unique_evaluations` so tests prove cache behavior.

- [ ] **Step 4: Implement adjacent hill climb and bounded beam search**

Adjacent hill climb uses best improvement: score every adjacent swap, accept
only a strict improvement, and stop at a local optimum. `max_rounds=0` scores
only the start.

Beam round zero scores/deduplicates the nonempty seeds and truncates to a
positive beam width. Each later round takes the elitist union of the current
beam and every adjacent-swap neighbor, deduplicates, sorts, truncates, and stops
when unchanged. `max_rounds` is a hard bound. Record the initial best and then
only strict global-best improvements. Add callback variants for the CLI; the
library wrappers use a no-op callback.

- [ ] **Step 5: Add CLI output and local feasibility run**

```bash
cargo run --locked --release --manifest-path Cargo.toml -- \
  search-order /tmp/occam71-audit.03qN9w/extracted/occam-circuit mystery-A \
  --beam 32 --rounds 12
```

`DATA_ROOT` is the same pinned extraction root accepted by `solve-v1`, and the
instance must be an exact mystery slug. Factor `instance_by_slug` and
`complete_table` into `instances.rs`; validate the commitment and every observed
training row before search.

Write machine-readable finalists to stdout only:

```text
instance,rank,xag_gates,bdd_nodes,order
mystery-A,0,282,116,0:8:1:9:...
```

Write and flush progress on stderr. Reject unknown/duplicate flags, zero beam,
and malformed inputs. The measured binding local envelope is beam 32 × 12
rounds, sequential A–D: conservative 2× projection ≤7.6 minutes and <16 GB.
Beam 64 × 16 across A–D is a no-go without a fresh pilot.

- [ ] **Step 6: Cross-check finalists and keep the task diagnostic**

For the top three unique finalists per instance, build OxiDD sequentially and
require exhaustive semantic agreement plus the same terminal-inclusive shared
node count. Drop each manager before the next. Do not use OxiDD in the scoring
loop and do not replace submission artifacts.

The measured local envelope does not justify hpccube, whose visible QDES
partition requires an A800 even for CPU work. Create no cluster profile, Slurm
script, remote file, or job in this task. If a later measured search crosses the
local threshold, use independent per-seed jobs plus a deterministic local merge;
do not claim chunked arrays are equivalent to one synchronized global beam.

- [ ] **Step 7: Run tests and commit local search**

```bash
cargo test --release --manifest-path Cargo.toml --test order
git add src/order.rs \
  src/lib.rs \
  src/instances.rs \
  src/main.rs \
  tests/order.rs
git commit -m "feat(qcs): search BDD orders by XAG score"
```

---

### Task 9: Freeze the Survey, Strong Baselines, and Sealed Benchmark Before Blind Proposals

**Status:** COMPLETE at `8f31f95` (survey/protocol/checker/baseline code and
sealed custodian benchmark, each independently reviewed).

**Files:**
- Create: `research/SURVEY.md`
- Create: `research/BASELINE_MATRIX.csv`
- Create: `research/BASELINE_MATRIX.sha256`
- Create: `research/BASELINES.csv`
- Create: `research/BENCHMARK_PROTOCOL.md`
- Create: `research/check_gate.py`
- Create: `research/test_check_gate.py`
- Create: `src/baseline.rs`
- Create: `tests/baseline.rs`
- Create: `reblind/COMMITMENT.txt`
- Create: `reblind/manifest.csv`
- Create: `reblind/README.md`
- Modify: `src/lib.rs`

**Interfaces:**
- Consumes: the rendered Boolean-synthesis and MPS literature, the completed
  contract/leakage audit, a custodian-only generator, and reproduced baseline
  manifests.
- Produces: a checked survey, a canonical baseline schema, a public benchmark
  bundle, two pinned non-novel blind baselines routed through the common XAG
  backend, and a pre-experiment hash commitment that must exist before a
  proposer receives any training rows.

- [x] **Step 1: Write the fail-closed research-gate checker**

`check_gate.py --phase protocol` exits nonzero unless:

- `SURVEY.md` contains sections for partial MCSP/Occam learning, BDD ordering,
  exact SAT synthesis, XAG/logic synthesis, arithmetic circuits, TT/MPS
  completion, available software, reproduced baselines, and the unresolved
  gap;
- every source claim names a rendered file under
  `.knowledge/literature/boolean-logic-synthesis/` or
  `.knowledge/literature/mps-based-algorithm/`;
- `BASELINE_MATRIX.csv` has exactly 360 unique rows: the Cartesian product of
  the two frozen baseline methods and all 180 opaque IDs in the committed public
  manifest. Each row has the manifest's tier/fraction, a commitment-derived
  algorithm seed, timeout `300`, and one declared hardware card. Its canonical
  LF bytes match `BASELINE_MATRIX.sha256`;
- `BASELINES.csv` has the exact visible-development header below. In
  `check_gate.py --phase baseline`, it additionally requires one row for every
  matrix key, no extras or duplicates, `blind=true`, and matching cap,
  hardware, source/compiler digest, terminal state, verifier, and evidence
  manifest. A successful row requires verifier pass; failed rows are retained
  with their terminal status and unavailable fields set to `none`. It rejects
  any sealed metric or evaluator-derived field;
- `COMMITMENT.txt` is one lowercase 64-hex SHA-256 value;
- every public manifest row has an opaque ID, declared shape/fraction, and
  public-bundle digest but contains no family, generator, secret seed, label,
  or sealed-table field.

`check_gate.py --phase manifests --run results/<run> --expected-spec <path>` is
a separate read-only mode. `<path>` must resolve under the tracked
`research/` directory. A JSON expected spec is the canonical provenance-free
design projection of `RUN/run_spec.json`; execution provenance is checked
independently, avoiding a self-referential commit hash. When the expected spec
is `BASELINE_MATRIX.csv`, the native JSON cells must be its exact 360-row
semantic image. The checker joins that frozen design to exactly one
`cells/<cell_id>/manifest.json` per ID,
validates the full Task 10 schema, source/image/compiler digests, canonical
numeric metrics, terminal status, recursive absence of sealed fields, and
evidence/artifact bytes. `SUCCESS` additionally requires `verifier=pass` and
valid artifact hashes. `TIMEOUT`, `OOM`, `NONZERO_EXIT`, `INVALID_METRICS`,
`VERIFIER_FAILED`, `VERIFIER_NOT_RUN`, `CANCELLED`, and
`MISSING_SUCCESS_MANIFEST` remain terminal evidence; they require frozen
provenance plus scheduler/log hashes and the literal `none` for unavailable
candidate artifacts. Missing, extra, nonterminal, or malformed records fail.

```text
comparison_id,role,method,method_version,blind,evaluation_scope,source_commit,runner_commit,tree_digest,image_sha256,compiler_digest,hardware,dataset_id,tier,observation_fraction,algorithm_seed,repeat,timeout_seconds,status,exit_code,timed_out,train_exact,visible_cv_exact,visible_cv_bit_accuracy,gates,elapsed_seconds,peak_memory_kib,verifier,artifact_sha256,manifest_sha256,evidence_path
```

Use the literal `none` for a genuinely inapplicable image or compiler field;
blank fields are never accepted, and `evaluation_scope` must be
`visible_cv_only`.

- [x] **Step 2: Run the checker and observe the missing-artifact failure**

```bash
python3 research/check_gate.py --phase protocol
python3 research/test_check_gate.py -v
```

Expected: the protocol command is nonzero with a sorted list of the missing
research artifacts; the focused synthetic checker suite passes after the
implementation is complete.

- [x] **Step 3: Write the reviewed SOTA and software survey**

Synthesize the already-rendered references on:

- Occam/PAC sample complexity and partial-MCSP hardness;
- Bryant-style multiplication lower bounds for ordered BDDs;
- Friedman–Supowit and practical sifting/window variable ordering;
- exact circuit synthesis and proof-producing bounded SAT;
- XAG rewriting with complemented edges and shared outputs;
- arithmetic add/subtract/multiply/square circuit baselines;
- Boolean MPS/Binary-Matrix-Product representations;
- TT completion assumptions and their mismatch with arbitrary coordinate
  sampling;
- grokking and TN generalization evidence.

The software table must distinguish OxiDD, the custom ROBDD/XAG, RustSAT with
CaDiCaL, CUDD/ABC/Espresso, and JAX/TN stacks. Record installed versions and
capabilities. If an external strong baseline such as ABC/CUDD is not installed
and the user declines installation, state that limitation and prohibit a
“100× versus SOTA” claim; only a matched reproduced-baseline claim remains.

- [x] **Step 4: Have a custodian build and commit to the strong benchmark**

Use a custodian process outside every proposer worktree. The custodian chooses
six deterministic Boolean/arithmetic families spanning carry, comparison,
bilinear, bitwise, and permutation behavior, but does not disclose the
inventory until final reveal. Build:

- operand widths `n=6` as the reference tier and `n=8`, `n=10` as two larger
  tiers;
- observation fractions `0.03` and `0.10`;
- five independent 256-bit benchmark seeds from a cryptographic RNG;
- identical public output width `2n+1`, identical row counts within each
  `(n, fraction)` stratum, opaque IDs, and shuffled generator assignment.

The frozen core matrix has exactly `6 × 3 × 2 × 5 = 180` instances. The
custodian retains complete tables, family mapping, generator source, and seed
material in storage that is not mounted into proposer worktrees. Because each
learner must emit a full table in increasing assignment order, test inputs are
defined implicitly as every unobserved assignment rather than materialized as
multi-gigabyte CSV files.

The custodian publishes:

- public `train.csv` bundles;
- `manifest.csv` containing only
  `opaque_id,input_bits,output_bits,train_rows,test_policy,observed_fraction,public_sha256`,
  where `test_policy` is the literal `all-unobserved`;
- `COMMITMENT.txt`, the SHA-256 of a canonical custodian manifest containing
  the public digests and private table/seed commitments.

Package the public rows as canonical
`occam-reblind-public-<COMMITMENT>.tar.zst` with layout:

```text
manifest.csv
instances/<opaque-id>/train.csv
```

Store the content-addressed archive and extraction under
`results/occam-reblind/public/<COMMITMENT>/`; this ignored directory is the
only proposer data root and is passed explicitly as
`OCCAM_REBLIND_PUBLIC_ROOT`. Commit only its digest and manifest, not the
bulk rows. The HPC stage copies this exact public directory and never the
custodian root.

`public_sha256` is not self-referential. It is SHA-256 over a canonical
length-framed sequence containing the six preceding public fields
(`opaque_id` through `observed_fraction`) followed by the exact `train.csv`
bytes; it excludes the `public_sha256` field, manifest header, and line
terminator. Each component is encoded as an eight-byte unsigned big-endian
length followed by that many UTF-8/CSV bytes.

No proposal agent receives the custodian manifest or secret storage path.
After the algorithm commits are frozen, reveal the generator, seeds, mappings,
and per-instance sealed digests under `reblind/revealed-after-freeze/` so an
independent party can reproduce the commitment.

- [x] **Step 5: Freeze the experiment and baseline protocol**

`BENCHMARK_PROTOCOL.md` requires an algorithm hypothesis and code commit before
that experiment receives a public training bundle. It defines:

- five-fold selection performed only inside the visible training rows;
- one final fit on all visible rows;
- no manual changes after sealed aggregate feedback;
- exact-row accuracy as primary and gates only after an accuracy tie;
- local and HPC 300-second cells with compilation/staging excluded and all
  learner/completion/synthesis work included;
- matched hardware and identical timeout for candidate/baseline comparisons;
- exact seed-cluster tests and cluster-bootstrap 95% intervals over the five
  independent benchmark seeds;
- micro accuracy, macro per-instance accuracy, per-instance gates, and summed
  gates, with no invented official aggregate.

This plan defines allowed research lanes, not a data-informed experiment
proposal. First finish the survey, baseline protocol, custodian suite, and
commitment. Then each proposer worktree writes its concrete hypothesis using
only the reviewed survey, contract, and nonidentifying manifest shapes—never
public row bytes or baseline/sealed outcomes—and commits synthetic-test-only
code. Only after that commit may the predeclared public bundle be mounted for
its fixed hyperparameter grid; sealed feedback cannot trigger another code or
hypothesis change.

- [x] **Step 6: Implement two frozen non-novel blind baselines with TDD**

Write `tests/baseline.rs` first. For a `PartialTable`, require:

```rust
pub enum FrozenBaseline { ZeroFill, HammingOneNearest }

pub fn complete_frozen_baseline(
    table: &PartialTable,
    method: FrozenBaseline,
) -> Result<(CompleteTable, Circuit), String>;
```

`ZeroFill` copies every observed output and assigns the all-zero vector to
unseen inputs. `HammingOneNearest` copies the output of the observed input with
minimum Hamming distance, breaking distance ties by numeric input value and
then original row index. Implement the latter as a deterministic multi-source
hypercube traversal in `O(input_bits × 2^input_bits)`, not a
`training_rows × 2^input_bits` scan; compare it exhaustively with the brute
force definition on small domains. Both enumerate the full domain, restore
every observed row, pass the resulting table through grouped and interleaved
shared ROBDD/XAG extraction, retain the lower verified challenge-gate result,
and emit canonical metrics. Tests exhaustively prove training consistency,
deterministic ties, complete-table/circuit equivalence, OxiDD agreement, and
byte-identical reruns.

Task 13 wires this public command only after `PublicSuite` exists:

```text
occam frozen-baseline PUBLIC_ROOT OPAQUE_ID OUTPUT_DIR \
  --method zero-fill|hamming-1nn \
  --metrics-json OUTPUT_DIR/metrics.json
```

The command accepts only a Task 13 `PublicSuite` root plus opaque ID; it never
opens a caller-supplied raw training path and knows no family, generator, test
label, or sealed digest.

- [x] **Step 7: Commit survey, protocol, and baseline code before data attachment**

```bash
cargo test --locked --release \
  --manifest-path Cargo.toml --test baseline
git add research/SURVEY.md \
  research/BASELINES.csv \
  research/BENCHMARK_PROTOCOL.md \
  research/check_gate.py \
  research/test_check_gate.py \
  src/baseline.rs \
  src/lib.rs \
  tests/baseline.rs \
  reblind/README.md
git commit -m "feat(qcs): freeze blind baseline protocol"
```

Record this clean commit in `LOG.md`. Only after it exists may the custodian
attach `OCCAM_REBLIND_PUBLIC_ROOT`.

- [x] **Step 8: Freeze the matched-baseline execution matrix**

Generate `BASELINE_MATRIX.csv` from the finalized opaque public manifest that
Step 10 commits atomically with the matrix, without opening any `train.csv`:
exactly two methods × 180 opaque IDs, sorted by `(method, opaque_id)`. Each row
fixes `comparison_id`, method/version,
opaque ID, input tier, observation fraction, algorithm seed derived from
`SHA256(COMMITMENT || method || opaque_id)`, repeat `0`, timeout `300`, and the
local hardware card. Reject a missing/extra ID, duplicate tuple, unknown
method, noncanonical sort, or digest mismatch.

```text
comparison_id,method,method_version,dataset_id,tier,observation_fraction,algorithm_seed,repeat,timeout_seconds,hardware
```

After Task 13 is committed, Task 10 executes this exact matrix with at most
four local workers and one five-minute-capped process per cell. Both baselines
remain a predeclared comparator portfolio regardless of their results; sealed
outcomes never choose or splice a baseline. The later `100×` and scaling tests
must pass independently against **both** complete baseline curves (each rerun
on matched A800 hardware if the primary candidate is TN).

Enter the completed v1 semantic, custom ROBDD, and OxiDD measurements as
`blind=false` controls. They cannot win blind baseline selection.

- [x] **Step 9: Validate that the proposer bundle is non-identifying**

Run the checker plus a custodian-side audit that groups public rows by
`(input_bits, output_bits, train_rows, test_policy, observed_fraction)` and
asserts each stratum contains every hidden family equally often. Search public
paths, headers, and JSON/CSV keys for family names, generator names, secret
seeds, `ground_truth`, and `test_outputs`. Any hit invalidates and regenerates
the suite before its commitment is published.

- [x] **Step 10: Commit the public commitment before executing baselines**

```bash
python3 research/check_gate.py --phase protocol
git add reblind/COMMITMENT.txt \
  reblind/manifest.csv \
  reblind/README.md \
  research/BASELINE_MATRIX.csv \
  research/BASELINE_MATRIX.sha256
git commit -m "data(qcs): commit sealed blind benchmark"
```

Do not stage custodian-only generator code, seeds, mappings, complete tables,
or evaluator logs before the algorithm freeze.

---

### Task 10: Enforce the Five-Minute Autoresearch and Sealed-Evaluation Contract

**Status:** STEPS 1–8 COMPLETE in `749bb60`, with independent-review
hardening in `24dbef4` and `735ec28`; final review PASS. Step 9 remains
blocked on the committed Task 13 public importer.

**Files:**
- Create: `scripts/run-experiment.py`
- Create: `scripts/materialize-slurm-failures.py`
- Create: `autoresearch/LOG_TEMPLATE.md`
- Create: `autoresearch/README.md`
- Create: `autoresearch/test_run_experiment.py`
- Create: `autoresearch/test_materialize_slurm_failures.py`
- Modify: `research/check_gate.py`
- Modify: `research/test_check_gate.py`
- Modify: `research/BENCHMARK_PROTOCOL.md`

**Interfaces:**
- Consumes: a frozen native run root, one declared cell ID, its canonical
  in-cell metrics path, optional independently checked container provenance,
  and an argv after `--`.
- Produces: `RUN_ROOT/cells/<cell-id>/manifest.json`, `stdout.log`,
  `stderr.log`, normalized peak memory, validated visible-only candidate
  metrics, and exactly one terminal status. For Slurm tasks killed before the
  runner writes a manifest, the post-fetch materializer converts the frozen
  run spec plus captured harness classification and task log into terminal
  failure evidence; it can never manufacture success.

**Binding pre-implementation amendment (2026-07-27):** this block replaces
conflicting Task 10 examples below. The Task 9 checker was deliberately
hardened before the runner existed; the runner must implement its native
layout rather than create a second evidence dialect.

1. A run is rooted at `RUN_ROOT`, contains the pre-existing exact
   `RUN_ROOT/run_spec.json`, and writes only
   `RUN_ROOT/cells/<cell_id>/{manifest.json,stdout.log,stderr.log,...}`.
   `run-experiment.py` therefore requires `--run-root`, `--cell-id`, and the
   canonical in-cell `--metrics-json`; `--experiment-id`, `--seed`,
   `--hardware`, and an arbitrary results directory are removed. It rejects a
   missing/duplicate cell, a spec outside the run root, a metrics path outside
   the selected cell, an existing cell directory, and an empty command.
2. A tracked JSON file is a provenance-free canonical **design spec** with
   exactly `schema_version` and `cells`; it never attempts to contain the hash
   of the commit that contains itself. The ignored execution
   `RUN_ROOT/run_spec.json` adds a top-level `provenance` object with exactly
   `source_commit`, `runner_commit`, `tree_digest`, `image_sha256`, and
   `compiler_digest` to that frozen design. The checker canonicalizes the
   execution projection `{"schema_version":1,"cells":[...]}` and requires its
   bytes to equal the tracked design spec; it validates execution provenance
   independently. Every cell `params` has exactly:

   ```text
   comparison_id,role,method,method_version,blind,evaluation_scope,hardware,dataset_id,tier,observation_fraction,algorithm_seed,repeat,timeout_seconds
   ```

   `comparison_id=cell_id`; all values are canonical strings;
   `blind=true`; `evaluation_scope=visible_cv_only`; the seed is 64 lowercase
   hex; repeat is a canonical nonnegative integer; and timeout is a canonical
   positive integer or decimal in `(0,300]`. A baseline execution spec adds
   `role=baseline` and these three fixed fields to each frozen matrix row while
   preserving every `BASELINE_MATRIX.csv` field verbatim. `check_gate.py` must
   validate both baseline and candidate JSON specs; baseline-only method
   restrictions remain exclusive to the canonical baseline matrix.
3. Local provenance requires a clean worktree including untracked files,
   `source_commit=runner_commit=git rev-parse HEAD`, `image_sha256=none`, and
   `tree_digest=SHA256(raw bytes from
   git ls-tree -rz --full-tree HEAD)`. The old SHA-256-of-empty-`git diff`
   proposal is invalid because it does not identify the tree. Container runs
   require a canonical `--container-provenance` JSON whose five values exactly
   equal the run spec; Task 14 independently verifies that file against the
   staged image before invoking this runner. The runner records but does not
   pretend to measure a container image from inside itself.
4. A successful child writes an exact-key metrics object:

   ```json
   {
     "train_exact": 1.0,
     "visible_cv_exact": 0.75,
     "visible_cv_bit_accuracy": 0.875,
     "gates": 37,
     "completed_table_sha256": "64 lowercase hex characters",
     "verifier": "pass"
   }
   ```

   The child must also write the fixed regular files `completed-table.csv`,
   `circuit.txt`, and canonical `artifact.json` in the selected cell. The
   artifact index has exactly:

   ```json
   {
     "circuit_path": "circuit.txt",
     "circuit_sha256": "64 lowercase hex characters",
     "completed_table_path": "completed-table.csv",
     "completed_table_sha256": "64 lowercase hex characters",
     "equivalence": "pass",
     "schema_version": 1
   }
   ```

   It is compact sorted-key JSON with one final LF. The runner opens regular
   files without following symlinks, stable-hashes the table and circuit,
   requires both index digests and the metrics table digest to match, then
   hashes the index itself. Accuracy values are finite and in `[0,1]`,
   `train_exact` must be exactly `1.0`, and gates is a nonnegative integer.
   Missing/extra/malformed metrics or index fields, a path race, symlink, hash
   mismatch, or equivalence other than pass is invalid. `bit_accuracy` is not
   an alias for either visible metric.
5. Extend the checked manifest with required
   `completed_table_sha256`, `circuit_sha256`, `schema_version`, `producer`,
   `run_spec_sha256`, `argv`, `started_utc`, `ended_utc`,
   `stdout_sha256`, `stderr_sha256`, `scheduler_job_id`,
   `scheduler_task_index`, `scheduler_state`, `scheduler_exit_code`,
   `scheduler_classification`, `scheduler_elapsed_seconds`, and
   `cleanup_seconds`. Retain `artifact_path`, `scheduler_sha256`,
   and `log_sha256`. Runner manifests use
   `producer=runner`, an argv string array, RFC-3339 UTC timestamps,
   the seven scheduler fields set to the literal `none`, and
   `log_sha256=SHA256(frame(stdout_bytes) || frame(stderr_bytes))`, where each
   frame is an eight-byte unsigned big-endian length followed by the bytes.
   Failed manifests set all candidate quality/digest/artifact fields to the
   literal `none`; valid elapsed, cleanup, and peak-memory observations may
   remain.
   Row fields are emitted as canonical strings so the CSV/evidence join is
   byte-stable.
6. `SUCCESS` means child exit 0, exact valid metrics, verifier pass, and a
   stable artifact hash. Timeout returns 124. A nonzero child is
   `NONZERO_EXIT` and is preserved when it is a valid process exit; a signal
   is normalized to `128+signal`. Zero-exit malformed metrics returns 65,
   verifier fail returns 66, and verifier not-run returns 67, with statuses
   `INVALID_METRICS`, `VERIFIER_FAILED`, and `VERIFIER_NOT_RUN`. The latter
   two retain only the verifier classification, not invalid quality claims.
7. The monotonic deadline includes child startup. Send `SIGTERM` early enough
   to reserve a bounded grace and `SIGKILL` no later than the deadline; always
   reap the process group. For a timeout, `elapsed_seconds` is the declared
   censored cap—not a falsely clipped wall measurement—and
   `cleanup_seconds` records the measured time from the deadline until reap.
   Successful/nonzero cells store measured monotonic elapsed and
   `cleanup_seconds=0.0`. Tests use a clean temporary Git repository and
   include a SIGTERM-ignoring grandchild.
8. Because the stable top-level harness is out of scope and its human-readable
   `classify` table discards duplicate accounting rows, the materializer
   consumes a separately captured raw Slurm parsable file with exact header
   `JobIDRaw|State|ExitCode|MaxRSS|ElapsedRaw`. It accepts one unique root
   allocation row `<job-id>_<one-based-index>` per run-spec cell plus uniquely
   named `.batch`/`.extern` steps, derives peak KiB across those records,
   requires `ExitCode=<code>:<signal>` with each component a canonical
   integer in `[0,255]`, and requires canonical nonnegative integer
   `ElapsedRaw`. The raw capture must use `sacct --units=K`; `MaxRSS` is
   either blank or `<canonical-nonnegative-integer>K`. Blank root RSS is
   filled from the maximum nonblank task/`.batch`/`.extern` value; if every
   value is blank, `peak_memory_kib=none`. No decimal or other unit is
   accepted, so there is no rounding ambiguity. Duplicate IDs or inconsistent
   state/exit pairs are rejected. The actual hpccube capture command remains
   blocked until the Task 14 resource-card ratification chooses an approved
   raw-accounting route; `harness_slurm.sh classify` remains diagnostic only
   and is never scientific input. The materializer hashes the complete raw
   bytes and the exact
   `RUN_ROOT/slurm-<job-id>_<one-based-index>.out`. Existing valid runner
   manifests remain byte-identical. For a missing manifest it emits only
   `TIMEOUT`, `OOM`, `NONZERO_EXIT`, `CANCELLED`, or
   `MISSING_SUCCESS_MANIFEST`, with `producer=scheduler`, empty argv,
   unavailable timestamps as `none`, the scheduler job/task/state/
   classification fields populated, `stdout_sha256` and `log_sha256` equal
   to the task-log hash, `stderr_sha256=none`, and no success metrics or
   artifact. Pending, unknown, duplicate, incomplete, mismatched, or log-less
   scheduler evidence fails validation before any manifest is
   written. The materializer never emits `SUCCESS`.
   Manifest exit codes are normalized as `124` for `TIMEOUT`, `137` for
   `OOM`, `130` for `CANCELLED`, and `70` for
   `MISSING_SUCCESS_MANIFEST`. `NONZERO_EXIT` uses the raw nonzero code, else
   `128+signal`, else `1`; `scheduler_exit_code` retains the exact raw
   `code:signal`. Tests cover blank/root/step RSS, each K-unit maximum, signal
   exit, and every status mapping.
9. Add checker round-trip tests for one successful runner manifest and every
   runner/scheduler terminal failure, including the completed-table digest,
   circuit/index transitive binding, operational metadata, decimal subsecond
   timeout, generic candidate role, design-versus-execution projection, and
   the unchanged 360-row baseline contract. All tests use synthetic data; no
   public benchmark rows are mounted in Task 10.

- [x] **Step 1: Write failing timeout and manifest tests**

Create a clean temporary Git repository, write a one-cell native
`run_spec.json` with matching provenance, and invoke the wished-for amended
CLI. The first RED tests require a `0.05`-second sleeping child to become a
terminal `TIMEOUT` at `cells/cell-001/manifest.json`, and reject a declared
timeout of `300.001` before the cell directory or child is created.

- [x] **Step 2: Run and observe the missing-runner failure**

```bash
source .venv/bin/activate
python -m pytest autoresearch/test_run_experiment.py -q
```

Expected: both tests fail because `run-experiment.py` does not exist.

- [x] **Step 3: Implement process-group termination and atomic manifests**

Implement the binding amendment with a small `RunResult` dataclass. Resolve
the worktree and run root, validate the frozen spec/provenance before creating
the cell, start the child in a new session, reserve termination grace inside
the cap, and atomically `fsync`/replace the terminal manifest. Normalize
`resource.RUSAGE_CHILDREN.ru_maxrss` to KiB by dividing by 1,024 on macOS and
retaining the Linux value.

- [x] **Step 4: Add process-tree, nonzero, and schema tests**

Test that:

- a grandchild is absent after its parent times out;
- stdout and stderr are separated and hashed correctly;
- a child exit `17` produces `NONZERO_EXIT` and runner exit `17`;
- an existing cell ID is never overwritten;
- argv elements containing spaces remain separate JSON strings;
- total child execution stays within the configured cap, including a child that
  ignores `SIGTERM`;
- macOS and Linux `ru_maxrss` fixtures normalize to the same KiB value;
- malformed, missing, NaN, or out-of-range metrics produce `INVALID_METRICS`;
- `verifier="fail"` and `"not_run"` can never produce runner success;
- the manifest contains no environment values or sealed-data contents.

- [x] **Step 5: Materialize scheduler failures without dropping cells**

`materialize-slurm-failures.py RUN_ROOT CLASSIFY_TSV --job-id JOB_ID`
validates the exact harness-classification format from the binding amendment
and requires one terminal row per ordered run-spec cell. It
leaves every existing valid runner manifest byte-for-byte unchanged. For a
missing manifest it atomically writes one provenance-bound terminal record:
Slurm timeout → `TIMEOUT`, out-of-memory → `OOM`, nonzero/failed →
`NONZERO_EXIT`, cancellation → `CANCELLED`, and Slurm `COMPLETED` without a
runner manifest → `MISSING_SUCCESS_MANIFEST`. The record includes run-spec,
source, image, compiler, job, task-index, scheduler-state, exit-code, elapsed,
MaxRSS, task-log, and classification digests; unavailable metrics/artifacts are
the literal `none`. It rejects pending/unknown states, missing/duplicate
indices, provenance disagreement, or an attempt to replace any manifest.

Test every mapping, exact run-spec cardinality, atomic non-overwrite,
deterministic bytes, and the invariant that this script never emits
`SUCCESS`. These manifests are failed scientific observations, not successful
reruns; Task 15 retains and normalizes them.

- [x] **Step 6: Define the worktree and LOG protocol**

`LOG_TEMPLATE.md` contains these exact headings:

```markdown
# Experiment <opaque-id>

## Hypothesis
## Parent commit and diff digest
## Permitted data
## Command, seed, and environment
## Hardware and five-minute cap
## Result: accuracy, gates, runtime, memory, verifier
## Failure signal and interpretation
## Next pivot
```

For every hypothesis, create the worktree from the latest accepted commit:

```bash
git worktree add ../occam-exp-<opaque-id> \
  -b codex/occam-exp-<opaque-id> <accepted-commit>
cp autoresearch/LOG_TEMPLATE.md \
  ../occam-exp-<opaque-id>/LOG.md
```

Do not reuse a worktree for a different hypothesis. A promoted change is
reviewed and cherry-picked into the accepted branch; a failed worktree remains
available until its manifest and `LOG.md` lessons are consolidated.
Root `LOG.md` is tracked on that hypothesis branch: fill its hypothesis,
permitted-data, and parent-commit sections and include it in the
synthetic-test-only algorithm commit before any data attachment. Every later
result update is a separate evidence commit. Thus `git status --porcelain=v1`
can be empty before a Git bundle without discarding the required log.

- [x] **Step 7: Document and test the proposal/evaluator firewall**

`autoresearch/README.md` binds three roles:

1. the **custodian** generates the sealed complete tables, opaque IDs, public
   training rows, and checksums;
2. the **proposer** receives only the reviewed contract, public rows, test
   domain policy, and aggregate lessons, and writes a completed table/circuit;
3. the **evaluator** checks the sealed rows and returns only
   `experiment_id`, train exact accuracy, sealed exact accuracy, bit accuracy,
   reachable gates, elapsed time, peak memory, and terminal status.

Add a test that recursively scans a synthetic proposer bundle and fails if a
path, header, or JSON key contains `family`, `generator`, `ground_truth`,
`test_outputs`, or a sealed digest. The evaluator's per-example mismatches and
family labels remain in an ignored custodian-only results root.

- [x] **Step 8: Run focused/baseline tests and commit**

```bash
source .venv/bin/activate
python -m pytest autoresearch -q
make test
git add autoresearch \
  scripts/run-experiment.py \
  scripts/materialize-slurm-failures.py \
  research/check_gate.py \
  research/test_check_gate.py \
  research/BENCHMARK_PROTOCOL.md
git commit -m "feat(qcs): enforce five-minute autoresearch cells"
```

- [ ] **Step 9: Execute and freeze both predeclared blind baselines**

This step is blocked until the Task 13 importer/CLI commit. Attach
`OCCAM_REBLIND_PUBLIC_ROOT` only after that commit and the Task 9 baseline-code
commit. Execute the exact digest-matched 360-row `BASELINE_MATRIX.csv` with at
most four local workers; every command takes only `PUBLIC_ROOT + OPAQUE_ID`,
and every child is a separate
`run-experiment.py --timeout-seconds 300` process. Compute only the
predeclared visible-row cross-validation, training consistency, completed-table
digest, XAG gates, and runtime; the sealed evaluator is not invoked. Keep even
these visible outcomes inaccessible until the Task 11, Task 12, and Task 14
synthetic-test-only hypothesis commits exist; then populate `BASELINES.csv`
with `evaluation_scope=visible_cv_only` and run:

```bash
python3 research/check_gate.py \
  --phase manifests --run results/occam-baselines-local \
  --expected-spec research/BASELINE_MATRIX.csv
python3 research/check_gate.py --phase baseline
git add research/BASELINES.csv
git commit -m "data(qcs): freeze matched blind baselines"
```

Public execution in Task 11 cannot begin until this command passes. Both
baseline methods remain in the comparator portfolio; no score selects one.
Synthetic-test-only implementation may proceed from the already-frozen plan
without reading these results.

---

### Task 11: Implement the Blind Care-Set ROBDD Learner

**Files:**
- Create: `src/care_bdd.rs`
- Create: `tests/care_bdd.rs`
- Create: `research/DEVELOPMENT_RESULTS.csv`
- Create if TN is not promoted: `research/FROZEN_COMPARISON.json`
- Create if TN is not promoted:
  `research/run-specs/{candidate,baseline-zero,baseline-hamming}-r{0,1}.json`
- Modify: `src/robdd.rs`
- Modify: `src/lib.rs`
- Modify: `src/main.rs`

**Interfaces:**
- Consumes: only `PartialTable`, public selection seed, candidate variable
  order, `EmptyCarePolicy`, and fold count.
- Produces: `complete_care_set`, `cross_validate_care_set`,
  `BlindOrderScorer`, a complete table, a shared-root XAG circuit, and one
  visible-development evidence row. No function accepts a sealed
  `CompleteTable`.

- [ ] **Step 1: Write failing exact-care and completion tests**

```rust
use occam_circuit_hmyuuu::care_bdd::{
    complete_care_set, cross_validate_care_set, EmptyCarePolicy,
};
use occam_circuit_hmyuuu::table::PartialTable;

#[test]
fn reuse_sibling_completes_unseen_branches_and_preserves_every_care_row() {
    let partial = PartialTable::parse(
        "input,output\n00,0\n10,1\n",
        2,
        1,
    ).unwrap();
    let (completed, circuit) =
        complete_care_set(&partial, &[0, 1], EmptyCarePolicy::ReuseSibling)
            .unwrap();
    assert_eq!(
        completed.outputs,
        vec![vec![false], vec![true], vec![false], vec![true]]
    );
    for (input, output) in &partial.rows {
        let got = circuit.evaluate(input).unwrap();
        assert_eq!(&got, output);
    }
}

#[test]
fn cross_validation_is_deterministic_and_never_uses_hidden_rows() {
    let partial = small_public_add_table();
    let a = cross_validate_care_set(
        &partial, &[0, 2, 1, 3], EmptyCarePolicy::ReuseSibling, 5, 17,
    ).unwrap();
    let b = cross_validate_care_set(
        &partial, &[0, 2, 1, 3], EmptyCarePolicy::ReuseSibling, 5, 17,
    ).unwrap();
    assert_eq!(a, b);
    assert_eq!(a.total_validation_rows(), partial.rows.len());
}
```

- [ ] **Step 2: Run and observe the missing learner failure**

```bash
cargo test --manifest-path Cargo.toml \
  --test care_bdd
```

- [ ] **Step 3: Implement fixed-order care-set reduction**

Build every output root in one complemented ROBDD manager. Recursive state is
`Empty` or `Edge(BddEdge)`. For the current public-row subset:

1. return `Empty` when it contains no care row;
2. return a terminal if all labels for this output bit agree;
3. otherwise split rows on `order[level]` and recurse;
4. under `ReuseSibling`, replace one empty child by the nonempty child, removing
   the decision variable;
5. under `Zero`, replace an empty child by false;
6. call a new `pub(crate) SharedRobdd::mk_care_node` boundary only after both
   children are concrete.

An exhausted order with conflicting labels is an error. A root cannot remain
empty because `PartialTable` is nonempty. Share the manager across output bits,
extract through the existing Shannon-to-XAG identity, enumerate all `2^n`
assignments, and reject unless the circuit reproduces every care row.
`mk_care_node` delegates to the existing canonical private `mk`; it does not
expose unrestricted node mutation outside the crate.

- [ ] **Step 4: Implement deterministic visible-row cross-validation**

Canonicalize each input row, hash
`selection_seed || input_bytes` with SHA-256, sort by digest, and assign folds
round-robin. Every row is validation exactly once. For each fold, fit only the
other visible rows and report exact-row and bit correctness on that fold.

`BlindScore` ranks candidates by:

1. greater validation exact-row accuracy;
2. fewer full-visible-refit XAG gates;
3. greater validation bit accuracy as a diagnostic tie-break only;
4. fewer shared BDD nodes;
5. `ReuseSibling` before `Zero`;
6. numeric lexicographic variable order.

Use integer numerators/denominators for ranking so floating-point ties cannot
change order. Refit the winning configuration on all visible rows, require
100% training consistency, and emit one canonical complete table.

- [ ] **Step 5: Search orders without consulting a completed reference table**

Add `BlindOrderScorer` with the same deterministic seed orders, adjacent
neighbors, cache, beam bounds, and progress callback as `OrderScorer`, but
score each candidate by the visible-row cross-validation tuple above. The
scorer owns only `&PartialTable`; tests must fail to compile if a completed
reference is supplied.

Expose:

```text
occam learn-care PUBLIC_ROOT OPAQUE_ID OUTPUT_DIR \
  --folds 5 --seed S --beam 32 --rounds 12 \
  --policy reuse-sibling
```

The command loads only through Task 13 `PublicSuite`, writes
`completed-table.csv`, `circuit.txt`, `metrics.json`, and `search.csv`, and
runs through `run-experiment.py --timeout-seconds 300`. Raw training paths and
width overrides are rejected.

- [ ] **Step 6: Add exhaustive, leakage, and OxiDD checks**

Test:

- every observed row is reproduced for all candidate orders and both policies;
- conflicting duplicate rows and incomplete permutations fail;
- fold membership is deterministic, disjoint, and covers all visible rows;
- empty-branch reuse never invents a node;
- output roots share nodes;
- two runs emit byte-identical tables, circuits, metrics, and search CSV;
- the completed table and extracted XAG agree on every assignment;
- OxiDD agrees on the completed function for the top three finalists;
- changing a synthetic hidden table while holding `PartialTable` fixed cannot
  change learner output.

- [ ] **Step 7: Commit the learner hypothesis before attaching public rows**

```bash
cargo test --locked --release \
  --manifest-path Cargo.toml --test care_bdd
cargo test --locked --release \
  --manifest-path Cargo.toml
git add src/care_bdd.rs \
  src/robdd.rs \
  src/lib.rs \
  src/main.rs \
  tests/care_bdd.rs \
  LOG.md
git commit -m "feat(qcs): freeze blind care-set ROBDD learner"
```

Record the clean commit and hypothesis in its worktree `LOG.md`; only then
attach `OCCAM_REBLIND_PUBLIC_ROOT`.

- [ ] **Step 8: Execute, evaluate, and commit aggregate evidence**

Run one five-minute cell per opaque instance through the frozen command and
record only visible cross-validation, training consistency, gates, and
operational metrics. Do not invoke or query the sealed evaluator. Append
candidate rows—not baseline rows—to
`research/DEVELOPMENT_RESULTS.csv`; no sealed accuracy, per-row hidden error,
or family grouping may appear.

```bash
git add research/DEVELOPMENT_RESULTS.csv LOG.md
git commit -m "data(qcs): record blind care-BDD evidence"
```

If TN is not promoted, use visible cross-validation now to freeze care-BDD's
one global configuration as the primary candidate. Commit
`research/FROZEN_COMPARISON.json` with that candidate, the two-method frozen
baseline portfolio, repeats `{0,1}`, local hardware/compiler digests, dataset
commitment, cap, and six repeat-specific canonical run specs before requesting
any sealed score:

```text
research/run-specs/candidate-r0.json
research/run-specs/candidate-r1.json
research/run-specs/baseline-zero-r0.json
research/run-specs/baseline-zero-r1.json
research/run-specs/baseline-hamming-r0.json
research/run-specs/baseline-hamming-r1.json
```

Each file has exactly 180 rows and fixes one method and one repeat; together
they preserve all 1,080 predeclared execution rows. `FROZEN_COMPARISON.json`
contains each tracked file's SHA-256 and schema/cardinality summary.

```bash
git add research/FROZEN_COMPARISON.json \
  research/run-specs/candidate-r0.json \
  research/run-specs/candidate-r1.json \
  research/run-specs/baseline-zero-r0.json \
  research/run-specs/baseline-zero-r1.json \
  research/run-specs/baseline-hamming-r0.json \
  research/run-specs/baseline-hamming-r1.json \
  LOG.md
git commit -m "data(qcs): freeze care-BDD comparison before sealed evaluation"
```

---

### Task 12: Add Bounded Exact Local XAG Synthesis with RustSAT/CaDiCaL

**Files:**
- Create: `src/sat.rs`
- Create: `tests/sat.rs`
- Modify: `src/lib.rs`
- Modify: `src/main.rs`

**Interfaces:**
- Consumes: a complete truth table with at most six cut inputs and one or more
  outputs, a gate bound, and an absolute deadline inside the cell's 300-second
  outer cap.
- Produces:
  `synthesize_xag_at_most(table, gates, deadline) -> Result<SatResult, String>`
  and checked replacement circuits, where `SatResult` is exactly
  `Sat(Circuit) | Unsat | Timeout | Unknown(String)`.

- [ ] **Step 1: Write failing exact-small-function tests**

```rust
use std::time::{Duration, Instant};

#[test]
fn exact_synthesis_distinguishes_zero_and_one_gate_functions() {
    let xor = CompleteTable::from_fn(2, 1, |m| ((m & 1) ^ ((m >> 1) & 1)) as u64);
    let deadline = Instant::now() + Duration::from_secs(5);
    assert!(matches!(
        synthesize_xag_at_most(&xor, 0, deadline).unwrap(),
        SatResult::Unsat
    ));
    let SatResult::Sat(circuit) =
        synthesize_xag_at_most(&xor, 1, deadline).unwrap() else {
        panic!("XOR must have a one-gate solution");
    };
    assert_eq!(circuit.graph.reachable_gate_count(&circuit.outputs), 1);
    assert_exhaustive_equivalence(&xor, &circuit).unwrap();

    let zero = CompleteTable::from_fn(2, 1, |_| 0);
    let SatResult::Sat(zero_circuit) =
        synthesize_xag_at_most(&zero, 1, deadline).unwrap() else {
        panic!("at-most one gate must admit a zero-gate constant");
    };
    assert_eq!(
        zero_circuit.graph.reachable_gate_count(&zero_circuit.outputs),
        0
    );
}
```

- [ ] **Step 2: Run with the SAT feature and observe the missing implementation**

```bash
cargo test --features sat --manifest-path Cargo.toml --test sat
```

- [ ] **Step 3: Encode a bounded acyclic XAG**

Implement an internal `synthesize_xag_exactly(table, gates, deadline)` encoding.
For each allocated exact-bound gate:

- one Boolean chooses XOR versus AND;
- exactly-one selectors choose each fanin from primary inputs, constants, and
  earlier gates;
- one polarity bit complements each selected fanin;
- row-value variables encode every gate on every truth-table row;
- output exactly-one selectors choose a primary input, constant, or gate with
  polarity.

Add CNF truth clauses for XOR and AND and symmetry breaking:

- fanin A's source index ≤ fanin B's source index;
- identical gates are forbidden;
- every synthesized gate must reach at least one output.

`synthesize_xag_at_most` iterates exact bounds `0..=gates` under the same
absolute deadline and returns the first independently verified SAT circuit.
Because every gate is reachable only in the internal exact-bound encoding, the
public function still means “at most.” If any lower bound returns `Timeout` or
`Unknown`, propagate it instead of skipping to a higher bound.

- [ ] **Step 4: Validate SAT, UNSAT, timeout, and unknown independently**

Every SAT model must decode to `Circuit`, compact, and pass exhaustive
equivalence. An UNSAT result is reported only as “no circuit within this encoded
bound”; preserve the DIMACS bytes and CaDiCaL proof when the binding exposes a
proof trace, then check the trace before using the word “certificate”.

Install a solver termination callback or interrupt flag tied to the supplied
deadline. Deadline termination returns `Timeout`; an interrupted,
resource-limited, or otherwise indeterminate solver response returns
`Unknown(reason)`. Neither state may be converted to `Unsat`, used as a
minimality certificate, or retried with a longer cell. Add a test with an
already-expired deadline that returns `Timeout` without invoking the solver.

- [ ] **Step 5: Integrate safe cut replacement**

Enumerate cuts with at most six leaves. Accept a replacement only when:

- it uses fewer reachable challenge gates;
- its cut table is exhaustively equivalent;
- the reinserted whole circuit is exhaustively equivalent;
- deterministic rerun returns identical serialized bytes.

- [ ] **Step 6: Run focused/full tests and commit**

```bash
cargo test --features sat --release --manifest-path Cargo.toml --test sat -- --nocapture
cargo test --features sat --release --manifest-path Cargo.toml
git add src/sat.rs \
  src/lib.rs \
  src/main.rs \
  tests/sat.rs \
  LOG.md
git commit -m "feat(qcs): add bounded exact XAG resynthesis"
```

Record the hypothesis and synthetic-only evidence in the worktree's tracked
`LOG.md`; do not attach or inspect public benchmark rows before this commit.
Run every synthesis command through `run-experiment.py --timeout-seconds 300`.
If a six-leaf solve returns `Timeout` or `Unknown`, retain the tested smaller
bound and report it precisely; do not broaden a local proof into a global
minimality claim.

Expose a runner-compatible command:

```text
occam resynthesize INPUT_CIRCUIT OUTPUT_DIR \
  --max-cut-inputs 6 --deadline-seconds 285 \
  --metrics-json OUTPUT_DIR/metrics.json
```

It writes SAT status, encoded bound, DIMACS/proof digests when applicable,
whole-circuit gate delta, exhaustive-equivalence result, and verifier status.

---

### Task 13: Import the Frozen Reblinded Benchmark and Enforce the Common Candidate Boundary

**Files:**
- Create: `src/reblind.rs`
- Create: `tests/reblind.rs`
- Modify: `src/baseline.rs`
- Modify: `tests/baseline.rs`
- Modify: `src/main.rs`
- Modify: `src/lib.rs`
- Modify: `reblind/README.md`

**Interfaces:**
- Consumes: only `OCCAM_REBLIND_PUBLIC_ROOT`, the public commitment, opaque
  manifest, and `instances/<opaque-id>/train.csv`.
- Produces: `PublicInstance`, a visible `PartialTable`, an increasing full-
  domain iterator, a deterministic visible-row validation split, and strict
  import of a learner's canonical `completed-table.csv`. It has no generator,
  family enum, secret seed, sealed label, or complete reference-table API.

**Binding pre-implementation amendment (2026-07-27):**

- Frozen IDs match `rb-[0-9a-f]{24}`. For benchmark evidence the positional
  `PUBLIC_ROOT` and `OCCAM_REBLIND_PUBLIC_ROOT` must both be present and
  canonicalize to the same directory.
- The public bundle cannot reproduce the commitment because the commitment
  also binds private state. `PublicSuite::load_frozen` embeds the tracked
  `COMMITMENT.txt` and exact tracked `manifest.csv`, requires the root basename
  to equal that commitment, and requires byte-identical root manifest bytes.
  A separately supplied `BundleTrust` and `load_with_trust` wrapper are
  crate-private under `#[cfg(test)]` for unit fixtures only; they do not exist
  in a production library build and are never accepted by a benchmark CLI.
  Integration tests exercise `load_frozen` rejection and CLI boundary checks;
  trusted synthetic success cases live in `src/reblind.rs` unit tests.
- Parse canonical UTF-8/LF CSV strictly. Reject CRLF, a missing final LF,
  extra columns/files, executable files, every symlink, identical or
  conflicting duplicate inputs, and non-increasing input masks. Numeric
  assignment order means `encode_lsb(mask,ninputs)` for
  `mask=0..2^ninputs-1`, not lexicographic text order.
- `visible_folds` decodes exactly 64 lowercase seed hex characters, orders
  rows by `SHA256(seed_bytes || canonical_input_ascii)` with numeric input as
  the collision tie-break, and assigns `rank mod folds`. Task 11 reuses this
  implementation instead of defining a second fold dialect.
- `frozen-baseline` derives its seed internally as
  `SHA256(COMMITMENT || method || opaque_id)`, computes five-fold visible
  exact-row and bit accuracy without synthesizing each fold, performs one
  final full-visible synthesis, and atomically writes
  `completed-table.csv`, `circuit.txt`, `artifact.json`, and the exact Task 10
  metrics. It exhaustively proves table/circuit equivalence. It accepts no
  raw CSV, width, seed, manifest, or commitment override.
- Add `export-visible PUBLIC_ROOT OPAQUE_ID OUTPUT_DIR --seed <64hex> --folds
  5`. It writes only digest-validated public rows, deterministic fold
  assignments, and a hash manifest. The Python TN lane consumes this export
  and never opens a public-bundle `train.csv` itself.

- [ ] **Step 1: Write failing public-bundle and leakage tests**

Place the trusted-success test below in `src/reblind.rs`'s `#[cfg(test)]`
module, where the crate-private synthetic trust API exists. Keep
`tests/reblind.rs` limited to production `load_frozen` and CLI rejection
paths.

```rust
#[test]
fn public_bundle_import_is_opaque_and_digest_checked() {
    let root = synthetic_public_bundle();
    let suite = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap();
    assert_eq!(suite.instances().len(), 2);
    for instance in suite.instances() {
        assert!(instance.opaque_id.starts_with("rb-"));
        assert_eq!(instance.output_bits, instance.input_bits + 1);
        assert!(instance.train.rows.len() < (1usize << instance.input_bits));
    }
    assert!(scan_public_bundle(root.path()).unwrap().is_empty());
}

#[test]
fn completed_table_must_be_canonical_and_training_consistent() {
    let instance = synthetic_public_instance();
    let completed = instance.import_completed_table(canonical_candidate()).unwrap();
    instance.train.validate_against(&completed).unwrap();
}
```

- [ ] **Step 2: Run and observe the missing importer failure**

```bash
cargo test --manifest-path Cargo.toml \
  --lib reblind::tests
cargo test --manifest-path Cargo.toml \
  --test reblind
```

- [ ] **Step 3: Implement the opaque public manifest**

Parse only this canonical schema:

```text
opaque_id,input_bits,output_bits,train_rows,test_policy,observed_fraction,public_sha256
```

Require sorted unique opaque IDs, input widths `12`, `16`, or `20`, output
width `input_bits+1`, fractions exactly `0.03` or `0.10`,
`test_policy=all-unobserved`, and lowercase 64-hex public digests. Verify each
digest against the Task 9 framing of the six public fields before the digest
plus the exact `train.csv` bytes. Never include `public_sha256` itself, the
manifest header, or row terminator in that preimage. Reject extra files or
columns so metadata cannot become a covert family label.

- [ ] **Step 4: Enforce the proposal-side leakage boundary**

`scan_public_bundle` recursively rejects filenames, headers, and JSON/CSV keys
containing `family`, `generator`, `ground_truth`, `test_outputs`, `secret`,
`seed`, or `sealed`. It also rejects executable source, symlinks escaping the
bundle, widths inconsistent with `2n+1`, and unequal row counts inside one
`(input_bits, observed_fraction)` stratum.

`PublicSuite::load_frozen` accepts only the content-addressed extraction:

```text
results/occam-reblind/public/<COMMITMENT>/
├── manifest.csv
└── instances/<opaque-id>/train.csv
```

The caller supplies that root explicitly through `OCCAM_REBLIND_PUBLIC_ROOT`;
the importer never searches parent directories or the custodian filesystem.

- [ ] **Step 5: Enforce the common completed-table boundary**

Every learner writes:

```text
input,output
000000000000,0000000000000
...
```

in increasing assignment order. The Rust importer requires exactly
`2^input_bits` rows and rejects missing, duplicate, unordered, width-invalid, or
training-inconsistent rows before synthesis. It then uses the same
ROBDD/XAG/canonical-netlist path as every other candidate. For the 20-input
tier, stream-parse candidate rows and keep only the representation required by
the next backend so the importer remains inside the five-minute/memory budget.

- [ ] **Step 6: Add deterministic visible-row selection**

Expose only the SHA-256 round-robin fold split from Task 11. Two loads of the
same public bytes and public selection seed must yield identical folds. No
method returns a family, secret seed, sealed digest, per-example evaluator
error, or full reference output.

- [ ] **Step 7: Wire every existing learner through the public importer**

Add the Task 9 `frozen-baseline PUBLIC_ROOT OPAQUE_ID ...` CLI now. It calls
only `PublicSuite::load_frozen`, selects exactly one opaque instance, and
passes its
validated `PartialTable` to `complete_frozen_baseline`. Reject raw CSV paths,
unknown IDs, commitment/digest mismatch, and any attempt to override
input/output widths. Add an integration test proving a modified `train.csv`
fails before the baseline runs.

All later learner CLIs must reuse this same loader. No command used for
benchmark evidence may accept `TRAIN_CSV`, a separately supplied width, or a
caller-created `PartialTable` path.

- [ ] **Step 8: Run tests and commit**

```bash
cargo test --release --manifest-path Cargo.toml \
  --lib reblind::tests
cargo test --release --manifest-path Cargo.toml \
  --test reblind
git add src/reblind.rs \
  src/baseline.rs \
  src/lib.rs \
  src/main.rs \
  tests/reblind.rs \
  tests/baseline.rs \
  reblind/README.md
git commit -m "feat(qcs): import sealed Occam public bundles"
```

---

### Task 14: Implement the Deterministic JAX MPS Completion Pilot

**Files:**
- Create: `tn/pyproject.toml`
- Create: `tn/src/occam_tn/__init__.py`
- Create: `tn/src/occam_tn/data.py`
- Create: `tn/src/occam_tn/model.py`
- Create: `tn/src/occam_tn/train.py`
- Create: `tn/src/occam_tn/pipeline.py`
- Create: `tn/src/occam_tn/hpc_cell.py`
- Create: `tn/tests/test_model.py`
- Create: `tn/tests/test_train.py`
- Create: `tn/tests/test_hpc_contract.py`
- Create: `tn/hpc/run_spec.template.json`
- Create: `tn/hpc/job_card.json`
- Create: `tn/hpc/occam-tn.def`
- Create: `tn/hpc/.gitignore`
- Create: `tn/hpc/README.md`
- Create: `scripts/run-tn-cell.sh`
- Create: `tests/tn_bridge.rs`
- Create after visible-only selection: `research/FROZEN_COMPARISON.json`
- Create before the pilot:
  `research/run-specs/{tn-smoke,tn-pilot}.json`
- Create after visible-only selection:
  `research/run-specs/{candidate,baseline-zero,baseline-hamming}-r{0,1}.json`
- Modify: `src/main.rs`
- Create through uv: `tn/uv.lock`

**Interfaces:**
- Consumes: one public reblinded partial table, a deterministic visible-only
  validation split, bit order, rank, public selection seed, and a prebuilt
  Rust `occam` binary.
- Produces: one canonical complete table, one verified challenge netlist, and
  one runner-compatible metrics file. The timed cell includes fitting,
  refitting, full-domain enumeration, care-row restoration, Rust synthesis,
  exhaustive table/circuit equivalence, and artifact writing.
- Never consumes a family name, generator, secret seed, sealed label, sealed
  digest, or per-example evaluator result. Rust remains the only
  synthesis/scoring backend; no generic real-MPS-to-BDD conversion is assumed.

- [ ] **Step 1: Create and lock the isolated uv project**

Use:

```toml
[project]
name = "occam-tn"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
  "jax==0.11.0",
  "numpy==2.5.1",
  "optax==0.2.8",
]

[dependency-groups]
dev = ["pytest==9.1.1"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Run:

```bash
uv lock --project tn
uv sync --project tn --group dev
```

Because JAX/Optax are a new heavy domain stack, show the resolved lock and
download estimate and obtain explicit user approval before `uv sync`. The
existing root `.venv` used by `make test` remains separate.

- [ ] **Step 2: Write failing exact-shape and determinism tests**

```python
def test_vector_mps_has_expected_batch_and_output_shape():
    params = init_mps(jax.random.key(7), nbits=6, outputs=4, rank=3)
    x = jnp.array([[0, 1, 0, 1, 1, 0], [1, 0, 1, 0, 0, 1]], dtype=jnp.int32)
    assert mps_logits(params, x).shape == (2, 4)

def test_overlay_restores_every_observed_row():
    completed = threshold_and_overlay(all_logits, all_inputs, observed)
    for key, output in observed.items():
        assert completed[key] == output


def test_pipeline_forwards_the_runner_metrics_path_to_rust(fake_occam, tmp_path):
    metrics = tmp_path / "cell" / "candidate-metrics.json"
    run_pipeline(tiny_public_cell(), fake_occam, metrics)
    assert fake_occam.metrics_path == metrics
    assert metrics.is_file()
```

- [ ] **Step 3: Run and observe missing-package failures**

```bash
uv run --project tn pytest \
  tn/tests -q
```

- [ ] **Step 4: Implement the open-boundary vector-output MPS**

Use exact binary feature selection:

```python
def mps_logits(params, x):
    state = params["left"][x[:, 0]]
    for site, core in enumerate(params["middle"], start=1):
        selected = core[x[:, site]]
        state = jnp.einsum("bi,bij->bj", state, selected)
    right = params["right"][x[:, -1]]
    return jnp.einsum("bi,bio->bo", state, right)
```

Shapes are `left=(2,χ)`, each middle core `(2,χ,χ)`, and
`right=(2,χ,m)`. Initialize from one explicit JAX key and train sigmoid
binary cross-entropy with Optax Adam. Report exact-row accuracy as the primary
metric and per-bit accuracy second.

- [ ] **Step 5: Add the common Rust synthesis boundary and end-to-end pipeline**

Add this command without a second synthesis implementation:

```text
occam synthesize-completed PUBLIC_ROOT OPAQUE_ID COMPLETED_TABLE OUTPUT_DIR \
  --order grouped|interleaved \
  --metrics-json OUTPUT_DIR/candidate-metrics.json
```

It must reject a table unless it has exactly `2^N` unique rows in increasing
assignment order, valid widths, and every training row from the digest-checked
Task 13 public instance unchanged. Raw CSV paths and width overrides are not
accepted. It builds
the table through the existing shared ROBDD/XAG backend, removes unreachable
gates, exhaustively evaluates the circuit over all assignments, and writes
canonical netlist plus the Task 10 metrics schema. Test the command on a tiny
complete table and on missing, duplicate, unordered, width-invalid, and
training-inconsistent tables.

`occam_tn.pipeline` performs one visible-only fold fit, records validation
exact-row accuracy, refits on every public training row, enumerates all
`2^N` inputs in increasing assignment order, thresholds outputs, overlays the
public care rows, and writes canonical LF CSV. It then invokes
`occam synthesize-completed` with the exact `--metrics-json` path supplied by
`run-experiment.py`. The Rust subprocess and all of its synthesis and
verification work stay inside the same outer timeout.

- [ ] **Step 6: Make completion deterministic and fail closed**

Enable JAX x64 and high matmul precision, force an explicitly named CPU or GPU
device, sort every input row, threshold with `logit >= 0`, and seed data order,
initialization, and optimization from the one public selection seed. Write all
files atomically and flush progress approximately 20 times per run.

Two CPU reruns with identical public bytes and parameters must produce
byte-identical completed-table, circuit, and metrics bytes before GPU
promotion. The container sets deterministic CUDA/XLA execution flags; two
A800 reruns must also match byte-for-byte. A device mismatch, nondeterministic
artifact, training exact accuracy below `1.0`, synthesis timeout, or verifier
failure makes the cell ineligible.

- [ ] **Step 7: Write the harness-native HPC contract and failing tests**

`job_card.json` is the reviewed resource contract:

```json
{
  "partition": "qdagnormal",
  "gres": "gpu:A800:1",
  "cpus_per_task": 4,
  "memory": "32G",
  "walltime": "00:05:00",
  "array_base": 1,
  "max_array_size": 200,
  "max_concurrent": 3,
  "runtime_module": "<literal returned by the read-only probe>"
}
```

Before implementing the wrapper, a read-only `hpccube` login-shell probe must
resolve the exact available Apptainer module name. Store that literal in
`job_card.json` and copy the same literal into `run-tn-cell.sh` before the
algorithm commit; the shell does not parse JSON at runtime. Source the site
module initialization and load that exact module in the wrapper. Tests reject
an unresolved placeholder, require the two literals to match, and confirm that
the resulting `apptainer` command is available before the script attempts the
cell. The compute-node smoke records `apptainer --version`.

`run_spec.template.json` uses the native schema:

```json
{
  "cells": [
    {
      "cell_id": "cell-0001",
      "params": {
        "method": "tn",
        "opaque_id": "PUBLIC_OPAQUE_ID",
        "order": "grouped",
        "rank": 4,
        "algorithm_seed": "PUBLIC_SELECTION_SEED",
        "repeat": 0
      }
    }
  ]
}
```

Tests require unique opaque cell IDs and tuples, consecutive 1-based
selection, at most 200 rows, only the six TN parameter keys shown above, and
no family or sealed fields. A matched-baseline row instead has exactly
`method="baseline"`, `opaque_id`, the frozen `baseline` name, and
`algorithm_seed`, and `repeat`; a separate one-row smoke spec uses exactly
`{"method":"smoke","algorithm_seed":"0","repeat":0}` and resolves only an
image-internal synthetic fixture. They also require `run-tn-cell.sh` to:

- read `HARNESS_RUN_SPEC`;
- pass the 1-based `SLURM_ARRAY_TASK_ID` unchanged to the in-image coordinator;
- resolve the site Apptainer module/runtime, then make exactly one
  `apptainer exec --nv` call;
- invoke no host `python3`, `uv`, `cargo`, or network command because none is
  available in the audited non-interactive PATH; and
- contain no rank, seed, instance, retry, or continuation loop.

Tests require `occam_tn.hpc_cell` inside the image to map
`SLURM_ARRAY_TASK_ID=1` to `cells[0]`, derive the run name from
`results/<run>/run_spec.json`, select the opaque `cell_id` and algorithm seed,
validate the staged image manifest, and `exec` the Task 10 runner with
`--timeout-seconds 285`, `--algorithm-source-commit`, and `--image-sha256`.
For `method=tn` the
child is `occam_tn.pipeline`; for `method=baseline` it is the frozen Rust
baseline command using the same public root, image, CPU/GPU allocation, timer,
completion/synthesis backend, and manifest schema. The latter is the explicit
matched-hardware exception to the normal CPU-local baseline policy. The runner
and its child use the container's Python. They write
`results/<run>/cells/<cell_id>/manifest.json`, pass one identical metrics path
to the runner and pipeline, and require the pipeline to see an A800.
The contract test also requires `run-tn-cell.sh` to be executable on disk and
staged with Git mode `100755`.

- [ ] **Step 8: Implement, test, and commit code before attaching public data**

`run-tn-cell.sh` is POSIX shell plus the site module command. It does not parse
JSON. It invokes:

```text
apptainer exec --nv \
  tn/hpc/occam-tn.sif \
  python -m occam_tn.hpc_cell \
  --run-spec <run-spec> --cell-index <one-based>
```

`hpc_cell.py` parses the one tuple and replaces itself with:

```text
# method=tn
python /opt/occam/run-experiment.py ... \
  --timeout-seconds 285 --metrics-json <metrics> -- \
  python -m occam_tn.pipeline \
  --public-root <public-root> --run-spec <run-spec> --cell-index <one-based> \
  --occam-bin /opt/occam/bin/occam --output-dir <cell-dir> \
  --metrics-json <same-metrics>

# method=baseline
python /opt/occam/run-experiment.py ... \
  --timeout-seconds 285 --metrics-json <metrics> -- \
  /opt/occam/bin/occam frozen-baseline \
  <public-root> <opaque-id> <cell-dir> --method <frozen-baseline> \
  --metrics-json <same-metrics>

# method=smoke
python /opt/occam/run-experiment.py ... \
  --timeout-seconds 285 --metrics-json <metrics> -- \
  python -m occam_tn.pipeline \
  --mode smoke --public-root /opt/occam/smoke-public \
  --run-spec <run-spec> --cell-index <one-based> \
  --occam-bin /opt/occam/bin/occam --output-dir <cell-dir> \
  --metrics-json <same-metrics>
```

For normal TN and baseline rows, `hpc_cell.py` reads the lowercase commitment
from tracked `reblind/COMMITMENT.txt`, derives the sole allowed public root as
`results/occam-reblind/public/<COMMITMENT>/`, and verifies that directory,
manifest, and per-instance digest before starting the runner. The run spec
cannot override this path. Smoke uses only the image-internal synthetic bundle
shown above. Tests exercise all three dispatch modes and reject any fourth
method or public-root override.

The image contains the runner, Linux release
`target/release/occam-circuit-hmyuuu` installed as
`/opt/occam/bin/occam`, and the locked Python environment, so the node performs
no compilation or download. Run:

```bash
chmod +x scripts/run-tn-cell.sh
uv run --offline --project tn pytest \
  tn/tests -q
cargo test --locked --release \
  --manifest-path Cargo.toml --test tn_bridge
git add tn/pyproject.toml \
  tn/uv.lock \
  tn/src/occam_tn/__init__.py \
  tn/src/occam_tn/data.py \
  tn/src/occam_tn/model.py \
  tn/src/occam_tn/train.py \
  tn/src/occam_tn/pipeline.py \
  tn/src/occam_tn/hpc_cell.py \
  tn/tests/test_model.py \
  tn/tests/test_train.py \
  tn/tests/test_hpc_contract.py \
  tn/hpc/run_spec.template.json \
  tn/hpc/job_card.json \
  tn/hpc/occam-tn.def \
  tn/hpc/.gitignore \
  tn/hpc/README.md \
  scripts/run-tn-cell.sh \
  src/main.rs \
  tests/tn_bridge.rs \
  LOG.md
git diff --cached --name-only
git commit -m "feat(qcs): add deterministic MPS completion pilot"
```

The staged-name review must contain only those code/protocol paths plus the
tracked root `LOG.md`. It must not contain a `.sif`, public rows, completed
table, result manifest, evaluator log, or any file under
`reblind/revealed-after-freeze/`. Only after this clean algorithm commit exists
may the experiment worktree receive `OCCAM_REBLIND_PUBLIC_ROOT`.

- [ ] **Step 9: Run four independent local five-minute go/no-go cells**

Before reading visible validation metrics, freeze one public `n=6` opaque
development instance, one public selection seed, and the four-cell grid
`grouped/interleaved × rank 4/8`. Put those four cells in the ignored
`results/occam-tn-local/run_spec.json`. Each cell uses:

```bash
python3 scripts/run-experiment.py \
  --experiment-id <opaque-cell-id> \
  --seed <public-selection-seed> \
  --hardware local-cpu \
  --results-root results/occam-tn-local/cells \
  --timeout-seconds 300 \
  --metrics-json results/occam-tn-local/cells/<opaque-cell-id>/candidate-metrics.json \
  -- uv run --offline --project tn \
  python -m occam_tn.pipeline \
  --public-root <content-addressed-public-root> \
  --run-spec results/occam-tn-local/run_spec.json \
  --cell-index <one-based-index> \
  --occam-bin target/release/occam-circuit-hmyuuu \
  --output-dir results/occam-tn-local/cells/<opaque-cell-id> \
  --metrics-json results/occam-tn-local/cells/<opaque-cell-id>/candidate-metrics.json
```

JAX tracing/compilation is inside the timed command. Compare with the
care-BDD candidate on the identical visible folds and common Rust backend.
Promote TN only if its aggregate visible exact-row accuracy is greater than the
care-BDD value, or the exact integer numerator/denominator ties and TN has
fewer challenge-native gates. Gates never compensate for lower accuracy. This
four-cell screen decides only whether to build the image; it does not select
the final configuration. If no cell passes, record the failure and move the
remaining budget to care-BDD/XAG/SAT; do not build or submit the GPU branch.

Complete `LOG.md`, commit the four public-only manifests/digests summarized in
`research/DEVELOPMENT_RESULTS.csv`, and verify a clean status before building or bundling:

```bash
git add research/DEVELOPMENT_RESULTS.csv LOG.md
git commit -m "data(qcs): freeze local MPS promotion decision"
git status --porcelain=v1
```

The evidence commit changes no algorithm source. It is the source HEAD for the
container and remote Git bundle.

- [ ] **Step 10: Build and checksum the offline image only after promotion**

Use the harness `build-apptainer-image` workflow on an internet-capable Linux
builder. `occam-tn.def` builds from the exact clean frozen source/evidence HEAD,
`pyproject.toml`, and `uv.lock`; copies
`target/release/occam-circuit-hmyuuu` to `/opt/occam/bin/occam`; installs
`run-experiment.py` at `/opt/occam/run-experiment.py`; installs the tiny
digest-valid synthetic smoke bundle at `/opt/occam/smoke-public`; and leaves
no package-manager network access at runtime. `tn/hpc/.gitignore` excludes
`*.sif`.

Write the `.sif` SHA-256, source commit, definition-file digest, builder image
digest, Python/JAX/CUDA versions, and expected A800 device test to ignored
`results/occam-tn-runtime/image-manifest.json`. Do not modify the tracked HPC
README between the clean algorithm commit and Git-bundle creation. The image
builder also writes a plain
`results/occam-tn-runtime/occam-tn.sif.sha256`; the shell wrapper validates it
from the repository root with `sha256sum -c` before entering the image, without
Python. Its filename field is the repository-relative staged `.sif` path. The image is
never committed; after jobs finish, copy only the reviewed metadata and actual
job evidence into the README evidence commit in Step 14. Building or installing
this heavy environment requires separate user approval at execution time.

- [ ] **Step 11: Generate run specs and stage exact artifacts with Git provenance**

The public pilot is fixed before execution as 24 independent cells:
`2 orders × 4 ranks × 3 public selection seeds` on the same predeclared
`n=6` opaque development instance, plus the one-row synthetic smoke spec. At
this stage, do not create a full-suite spec or comparison file:
those depend on public pilot evidence and are created in Step 13 before sealed
evaluation. Write the exact one-row and 24-row canonical specs first to
`research/run-specs/tn-smoke.json` and `research/run-specs/tn-pilot.json`,
validate their schema/cardinality, record their SHA-256 values in `LOG.md`, and
commit them before execution:

```bash
git add research/run-specs/tn-smoke.json \
  research/run-specs/tn-pilot.json \
  LOG.md
git commit -m "data(qcs): freeze MPS smoke and pilot matrices"
```

Each ignored execution spec at `results/<run>/run_spec.json` is a byte-for-byte
copy of its tracked canonical file; no script edit is needed, and no spec may
exceed 200 cells.

Require `git status --porcelain=v1` to print nothing. Copy the two canonical
specs to their ignored execution paths and assert byte equality. Create a Git
bundle for the exact HEAD, copy it to `~/scratch/occam71/`, and clone it into
the currently absent `~/BooleanRazor`; for later revisions, fetch the new
bundle and checkout its commit detached. Verify the remote
`git rev-parse HEAD` exactly matches the recorded local commit. This preserves
`.git` for runner provenance and ships only tracked files—never a loose copy of
the worktree.

Separately stage only:

1. `tn/hpc/occam-tn.sif`;
2. `results/occam-tn-runtime/image-manifest.json`;
3. `results/occam-tn-runtime/occam-tn.sif.sha256`;
4. `results/occam-reblind/public/<COMMITMENT>/`;
5. `results/occam-tn-smoke/run_spec.json`;
6. `results/occam-tn-pilot/run_spec.json`.

Representative commands, with `<commit>` and `<COMMITMENT>` replaced by the
recorded literal values, are:

```bash
git status --porcelain=v1
git bundle create /tmp/occam71-<commit>.bundle HEAD
ssh hpccube 'mkdir -p ~/scratch/occam71'
rsync -az /tmp/occam71-<commit>.bundle hpccube:~/scratch/occam71/
ssh hpccube \
  'git clone ~/scratch/occam71/occam71-<commit>.bundle ~/BooleanRazor'
ssh hpccube 'git -C ~/BooleanRazor checkout --detach <commit>'
ssh hpccube 'git -C ~/BooleanRazor rev-parse HEAD'
ssh hpccube \
  'mkdir -p ~/BooleanRazor/tn/hpc \
    ~/BooleanRazor/results/occam-tn-runtime \
    ~/BooleanRazor/results/occam-reblind/public/<COMMITMENT> \
    ~/BooleanRazor/results/occam-tn-smoke \
    ~/BooleanRazor/results/occam-tn-pilot'
rsync -az tn/hpc/occam-tn.sif \
  hpccube:~/BooleanRazor/tn/hpc/
rsync -az results/occam-tn-runtime/image-manifest.json \
  hpccube:~/BooleanRazor/results/occam-tn-runtime/image-manifest.json
rsync -az results/occam-tn-runtime/occam-tn.sif.sha256 \
  hpccube:~/BooleanRazor/results/occam-tn-runtime/occam-tn.sif.sha256
rsync -az results/occam-reblind/public/<COMMITMENT>/ \
  hpccube:~/BooleanRazor/results/occam-reblind/public/<COMMITMENT>/
rsync -az results/occam-tn-smoke/run_spec.json \
  hpccube:~/BooleanRazor/results/occam-tn-smoke/run_spec.json
rsync -az results/occam-tn-pilot/run_spec.json \
  hpccube:~/BooleanRazor/results/occam-tn-pilot/run_spec.json
```

Before cloning, check whether the destination now exists; use the documented
fetch-and-detach refresh path instead of overwriting an existing checkout.
Never stage the custodian root, reveal files, sealed tables, evaluator logs,
`.venv`, `target`, or unrelated dirty changes. Append source/image/public/spec
digests to the hypothesis `LOG.md`.

- [ ] **Step 12: Preflight, probe, ratify, and scheduler-test the exact job**

```bash
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' precheck
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' probe-partitions
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' submit --test-only \
  --array 24%3 \
  --run-spec results/occam-tn-pilot/run_spec.json \
  --entrypoint scripts/run-tn-cell.sh \
  --partition qdagnormal --time 00:05:00 --cpus 4 \
  --extra '--mem=32G --gres=gpu:A800:1 --output=results/occam-tn-pilot/slurm-%A_%a.out'
```

Run the same `submit --test-only` invocation separately—with its literal
`--run-spec`, output path, and array—for every request:

| Run | Array |
|---|---:|
| `occam-tn-smoke` | `1%1` |
| `occam-tn-pilot` | `24%3` |

For example, the smoke request substitutes
`--array 1%1 --run-spec results/occam-tn-smoke/run_spec.json` and
`--output=results/occam-tn-smoke/slurm-%A_%a.out`. Capture both rendered
commands and scheduler responses. Step 13 repeats this entire
stage/probe/test-only/ratify gate for each later 180-cell comparison request;
never treat the pilot result as authorization or feasibility evidence for one
of them.

Show the fresh queue probe, source/image digests, 24-cell spec digest, and exact
job card to the user before the pilot, then show each distinct spec digest and
fresh scheduler estimate before its own ratification. A missing checkout,
nonmatching commit, QOS/GRES
rejection, unavailable A800, unresolved container module, array-limit issue, or
distant start estimate stops here. `--array 24%3` renders exactly one Slurm
directive, `1-24%3`; do not add a second array option through `--extra`. A prior
general approval is not a substitute for ratifying this concrete resource
request.

- [ ] **Step 13: Submit, monitor, fetch, and classify after ratification**

First submit a one-cell end-to-end smoke spec through the same entrypoint. It
checks the image digest, exposes an A800 to JAX, runs a tiny built-in
train/enumerate/Rust-synthesize/verify case, and writes a valid native
manifest. Fetch and classify it. Only a passing smoke permits the 24-cell
pilot; only the Step 9 promotion rule permits the frozen candidate, matched
two-baseline portfolio, and predefined repeat runs. Submit each only after its own
staging digest, test-only response, queue estimate, and resource card have been
ratified.

After fetching the pilot, rank its 24 cells by visible exact-row accuracy,
gates only on an exact tie, diagnostic bit accuracy, then lexicographic
configuration. Freeze the selected order, rank, and algorithm seed. Generate
six tracked 180-row canonical specs under `research/run-specs/`: candidate,
ZeroFill, and HammingOneNearest each at repeats `0` and `1`.
`FROZEN_COMPARISON.json` records every canonical spec digest and cardinality,
candidate/baseline source identities, dataset commitment,
image/compiler/hardware identities, 285-second runner cap, and 300-second
scheduler cap. Commit the full 1,080-row design, comparison, and updated
tracked log before opening any sealed result:

```bash
git add research/FROZEN_COMPARISON.json \
  research/run-specs/candidate-r0.json \
  research/run-specs/candidate-r1.json \
  research/run-specs/baseline-zero-r0.json \
  research/run-specs/baseline-zero-r1.json \
  research/run-specs/baseline-hamming-r0.json \
  research/run-specs/baseline-hamming-r1.json \
  LOG.md
git commit -m "data(qcs): freeze blind comparison before sealed evaluation"
git status --porcelain=v1
```

Create a new bundle for this metadata-only HEAD, refresh the remote checkout
through `git fetch <bundle> HEAD` plus detached `FETCH_HEAD`, and verify the
remote commit. Then create each ignored execution spec as a byte-for-byte copy
of its tracked canonical file and stage exactly:

```text
results/occam-tn-full-r0/run_spec.json
results/occam-tn-full-r1/run_spec.json
results/occam-baseline-zero-r0/run_spec.json
results/occam-baseline-zero-r1/run_spec.json
results/occam-baseline-hamming-r0/run_spec.json
results/occam-baseline-hamming-r1/run_spec.json
```

Create the six corresponding remote result directories and `rsync -az` each
literal local spec to the same repository-relative path; do not rsync the
parent `results/` tree. Verify local-copy equality and all six remote SHA-256
values against the tracked canonical files and `FROZEN_COMPARISON.json`.

For each spec in that order, rerun `precheck`, `probe-partitions`, and the
literal Task 14 Step 12 `submit --test-only` command with `--array 180%3` and
its own output directory. Show and ratify each spec digest, rendered scheduler
request, and queue estimate separately. Only then may its real submission
occur. The baseline route is one baseline cell per opaque ID through the same
container and 285-second runner; it does not train or invoke the TN model.

For each accepted run, repeat the checked command without `--test-only`,
capture its job ID, and use:

```bash
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' status <job-id>
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' fetch <run>
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' classify <run> <job-id> \
  > results/<run>/sacct.tsv
python3 scripts/materialize-slurm-failures.py \
  results/<run> results/<run>/sacct.tsv --job-id <job-id>
scripts/harness_slurm.sh \
  --profile skills/using-slurm/profiles/hpccube.toml \
  --alias hpccube --repo '~/BooleanRazor' pending-cells <run>
python3 research/check_gate.py \
  --phase manifests --run results/<run> \
  --expected-spec research/run-specs/<canonical>.json
```

`<canonical>` is the tracked file mapped to that literal run:
`tn-smoke`, `tn-pilot`, `candidate-r0`, `candidate-r1`,
`baseline-zero-r0`, `baseline-zero-r1`, `baseline-hamming-r0`, or
`baseline-hamming-r1`; no caller-selected untracked expected spec is allowed.

Monitor pending→running, tail the first cell until it emits a valid progress
line, then use the bounded `wait` command and remain engaged through terminal
state. Treat native `classify` as scheduler evidence only. `pending-cells`
without a success field checks completeness, not scientific success;
`materialize-slurm-failures.py` supplies provenance-bound evidence only for
terminal tasks that died before the runner wrote a manifest, and
`check_gate --phase manifests` validates every expected terminal record.
For the smoke gate only, additionally run `pending-cells
occam-tn-smoke --success-field status --success-value SUCCESS` and require no
output. In later pilot and confirmatory runs, failed cells remain in the
matrix and cannot be selected or dropped. A startup image/device failure stops
the remaining branch rather than triggering an unplanned dependency install.
Append Slurm job ID, partition, GRES, CPU, memory, elapsed, `MaxRSS`,
GPU-hours, image digest, source/spec commits, and per-cell classification to
`LOG.md`.

- [ ] **Step 14: Freeze only reviewable evidence**

```bash
uv run --offline --project tn pytest \
  tn/tests -q
cargo test --locked --release \
  --manifest-path Cargo.toml --test tn_bridge
git add research/DEVELOPMENT_RESULTS.csv \
  tn/hpc/README.md \
  LOG.md
git diff --cached --name-only
git commit -m "data(qcs): record MPS pilot evidence"
```

Do not commit `.sif` files, complete candidate tables, public data, raw Slurm
logs, or custodian/evaluator data. Record failed and timed-out cells as well as
successful ones. The custom JAX MPS is the primary pilot because it has a
smaller auditable surface than a broad TN framework. If time remains, tn4ml
may be added only as a separately committed candidate behind the same
five-minute CSV/Rust boundary; it never receives a direct MPS-to-BDD
conversion claim.

---

### Task 15: Differential Verification, Research Decision, and Submission README

**Files:**
- Create: `scripts/verify-julia.sh`
- Create: `research/RESULTS.csv`
- Create: `research/MANIFESTS.ndjson`
- Create: `research/MANIFESTS.sha256`
- Create: `research/analyze.py`
- Create: `research/test_analyze.py`
- Create: `research/FINAL_REPORT.md`
- Read and verify without modification: `research/FROZEN_COMPARISON.json`
- Read and verify without modification:
  `research/run-specs/`
- Create: `research/accuracy-gate-runtime.png`
- Create: `research/scaling.png`
- Create after algorithm freeze: `reblind/revealed-after-freeze/generator.rs`
- Create after algorithm freeze: `reblind/revealed-after-freeze/seeds.json`
- Create after algorithm freeze: `reblind/revealed-after-freeze/mapping.csv`
- Create after algorithm freeze: `reblind/revealed-after-freeze/AUDIT.md`
- Modify: `README.md`
- Modify: `mystery-A.txt`
- Modify: `mystery-B.txt`
- Modify: `mystery-C.txt`
- Modify: `mystery-D.txt`
- Modify: `predictions/mystery-A/test_outputs.csv`
- Modify: `predictions/mystery-B/test_outputs.csv`
- Modify: `predictions/mystery-C/test_outputs.csv`
- Modify: `predictions/mystery-D/test_outputs.csv`

**Interfaces:**
- Consumes: every semantic, care-BDD, complete-table ROBDD, order-search,
  SAT-local, TN, and hybrid candidate; matched baseline manifests; aggregate
  sealed evaluator output; and the post-freeze custodian reveal.
- Produces: exactly one verified v1 circuit/prediction pair per mystery,
  blinded accuracy-first results, paired runtime/scaling statistics, and an
  explicit `100×`, scaling-advantage, or not-demonstrated research decision.

- [ ] **Step 1: Select the v1 exact-control artifacts**

For each public v1 instance:

1. reject training-inconsistent candidates;
2. reject completed-table digest mismatches against the semantic v1 table;
3. reject any exhaustive circuit mismatch;
4. reject circuit/prediction disagreement;
5. choose the fewest reachable gates;
6. break equal-gate ties by lexicographic netlist bytes.

This gate is valid only for the disclosed v1 control. Never apply its known
semantic digest to a blind benchmark candidate.

- [ ] **Step 2: Evaluate only the visible-selected frozen comparison**

Before the evaluator opens a sealed label, validate
`FROZEN_COMPARISON.json` against the committed dataset, candidate, both fixed
baselines, run specs, repeats, hardware/image/compiler, and timeout digests.
The evaluator accepts artifacts only for that frozen candidate and those two
baseline methods, with their exact configurations. It joins them only by
opaque instance ID, secret-seed index, tier, observation fraction, repeat,
hardware, and timeout, and rejects
training exact accuracy below `1.0`, invalid metrics, prediction/circuit
disagreement, or nondeterministic rerun.

Within each matched cell, compare and report:

1. greater sealed exact-row accuracy;
2. fewer challenge-native reachable gates;
3. greater sealed bit accuracy as a diagnostic only;
4. lower elapsed seconds;
5. lexicographic artifact digest.

Report per-instance values, micro exact accuracy, macro exact accuracy,
per-instance gates, and summed gates. Do not call a derived aggregate the
official four-instance score. Sealed outcomes never select a method,
hyperparameter, seed, order, rank, baseline, or rerun cohort. Any nonprimary
ablation scored on this suite is descriptive only and cannot replace the
frozen primary or support the confirmatory claim without a separately
committed confirmation suite.

- [ ] **Step 3: Verify the sealed reveal and rerun independently**

After every algorithm commit is frozen, obtain the custodian reveal. Recompute
the canonical custodian-manifest digest and require an exact match with
`reblind/COMMITMENT.txt`; regenerate all public and sealed tables and compare
their hashes. Commit the generator, revealed seeds, mappings, and audit only
now under `reblind/revealed-after-freeze/`. Never commit complete sealed
tables, per-example mismatches, or raw evaluator logs.

Run the frozen primary candidate and each fixed blind baseline twice from clean
worktrees on identical hardware. Require byte-identical completed tables,
circuits, metrics, and prediction files; compare all three against the
regenerated sealed tables and the common Rust evaluator.

- [ ] **Step 4: Run two clean deterministic v1 builds**

```bash
cargo clean --manifest-path Cargo.toml
OCCAM_V1_ROOT=/tmp/occam71-audit.03qN9w/extracted/occam-circuit \
cargo test --locked --all-features --release \
  --manifest-path Cargo.toml

OCCAM_V1_ROOT=/tmp/occam71-audit.03qN9w/extracted/occam-circuit \
cargo run --locked --release \
  --manifest-path Cargo.toml -- \
  solve-v1 /tmp/occam71-audit.03qN9w/extracted/occam-circuit \
  .
```

Repeat generation into a fresh directory and compare every artifact digest.

- [ ] **Step 5: Differentially run the official Julia verifier**

For each `mystery-X.txt`, run the pinned `verify.jl` on `train.csv` and on the
generated `test_outputs.csv`. Parse and compare:

- official gate lines versus Rust reachable count;
- official exact accuracy equals 1.0;
- official bit accuracy equals 1.0;
- sample count equals the file's non-header row count.

The script exits nonzero on any mismatch and prints one flushed summary line per
instance.

- [ ] **Step 6: Recheck public commitments**

Run `shasum -a 256` on each prediction file and assert all four full digests
match the pinned commitments. Store the digest table in `README.md`.

- [ ] **Step 7: Compute matched statistics and make the research decision**

`RESULTS.csv` uses this sealed-confirmation schema:

```text
comparison_id,role,method,method_version,blind,evaluation_scope,source_commit,runner_commit,tree_digest,image_sha256,compiler_digest,hardware,dataset_id,tier,observation_fraction,benchmark_seed_id,algorithm_seed,repeat,timeout_seconds,status,exit_code,timed_out,train_exact,sealed_exact,bit_accuracy,gates,elapsed_seconds,peak_memory_kib,verifier,artifact_sha256,manifest_sha256,evidence_path
```

`evaluation_scope` is exactly `sealed_confirmation`. Produce
`MANIFESTS.ndjson` by stripping logs, host-private paths, and any sealed
per-example data from each runner manifest, canonicalizing its remaining
provenance/status/metrics object, sorting by `(comparison_id, dataset_id,
repeat)`, and writing one object per LF line. Each results row's
`manifest_sha256` hashes its exact canonical object bytes; `MANIFESTS.sha256`
hashes the complete NDJSON bytes. Commit both files, never the raw logs.

Before any candidate sealed result is opened, `FROZEN_COMPARISON.json` fixes
the two-method baseline portfolio and exact comparison hardware. A TN
comparison reruns each baseline through `method=baseline` inside the same A800
image/allocation and 285-second inner runner; a CPU comparison runs all three
methods on the same local host. Different hardware, time caps, images, compiler
modes, or missing manifest hashes cannot support a speed or scaling claim.

`analyze.py` requires every predeclared opaque ID, secret seed, fraction, and
repeat exactly once for the candidate and for each baseline and verifies each
normalized row against the committed sanitized-manifest hash. It fails closed
on unmatched pairs, unequal
caps/provenance, missing/duplicate cells, training inconsistency,
nondeterministic reruns, verifier non-pass, or malformed metrics. A timeout,
OOM, nonzero exit, or invalid output remains in the analysis with
`elapsed_seconds=timeout_seconds`, `sealed_exact=0`, and worst circuit quality;
no cell may be filtered after its result is known.

Apply the `100×` rule independently to ZeroFill and HammingOneNearest:

1. every candidate cell is valid, deterministic, and training-consistent;
2. on every matched cell, candidate sealed exact-row accuracy is at least the
   baseline value;
3. whenever exact-row accuracy ties, candidate reachable gates are no greater
   than the baseline value;
4. compute `baseline_elapsed/candidate_elapsed` on every matched cell,
   including normalized failures; and
5. enumerate all `5^5 = 3,125` ordered paired cluster-bootstrap resamples of
   the five independent benchmark seeds—keeping all six families, tiers,
   fractions, and repeats in each sampled seed cluster intact—and require the
   95% lower confidence bound of the paired median speedup to be at least
   `100`; and
6. require all five seed-cluster median speedups to exceed `1`, giving an exact
   one-sided paired sign-test value `p=1/32`.

Any quality-gate failure rejects the entire `100×` claim; it does not merely
remove that pair. The publishable rule passes only if both separately
predeclared baseline comparisons pass; report both curves and never form a
post-result composite. Phrase the result as “100× over both reproduced
baselines,” not “100× over SOTA,” unless the survey actually reproduces a
recognized SOTA implementation.

For the scaling rule, a method **solves** a tier only when:

- all 60 logical instances have two valid verified executions (120 rows);
- both execution rows are training-consistent and their completed tables,
  circuits, metrics, and predictions are byte-identical;
- the stratified-bootstrap 95% lower bound for tier macro exact-row accuracy is
  at least `0.99`; and
- the worst of the five benchmark-seed macro accuracies is at least `0.95`.

The candidate must solve both `n=8` and `n=10`, while **each** matched baseline
fails the same definition on both. Using all execution rows with failures
capped at their row-specific `timeout_seconds`, fit
`log2(median elapsed)` against operand width `n ∈ {6,8,10}` separately for
each method. For each candidate-versus-baseline curve, enumerate the same
`5^5` paired seed-cluster bootstrap and require the 95% lower bound of
`baseline_runtime_slope − candidate_runtime_slope` to exceed zero; also
require all five seed-cluster slope differences to be positive
(`p=1/32`, exact one-sided sign test). Report peak-memory slopes as supporting
evidence, assigning an OOM the allocation limit. This solve-and-slope
conjunction must pass against both full baseline curves—not a favorable subset
or composite—to establish the scaling criterion.

If neither rule passes, report “publishable performance criterion not
demonstrated”; do not substitute a qualitative claim. Generate the two named
accuracy–gate–runtime and scaling figures, tier/seed intervals, the complete
failure table, and the machine-readable decision.

- [ ] **Step 8: Write the pitch-style README and research report**

Include:

- explicit disclosure that A/B/C/D were identified from public leakage;
- exact family mapping;
- XAG/free-negation cost model;
- semantic, ROBDD/OxiDD, order-search, SAT, and TN roles;
- final per-instance gate counts;
- four prediction SHA-256 values;
- training, exhaustive, deterministic, OxiDD, and Julia verification status;
- exact fresh-checkout commands;
- sealed benchmark protocol, commitment/reveal audit, and aggregate results
  separated from v1 leaderboard claims;
- the matched baselines, hardware, statistical test, and `100×`/scaling/not-
  demonstrated decision;
- accuracy–gate–runtime Pareto and scaling figures;
- hpccube job IDs and resource usage only if jobs were actually run.

- [ ] **Step 9: Run the repository baseline**

```bash
cargo fmt --manifest-path Cargo.toml -- --check
cargo test --locked --all-features --release --manifest-path Cargo.toml
uv run --project tn pytest tn/tests -q
source .venv/bin/activate
python -m pytest research/test_analyze.py -q
make test
git diff --check
```

Expected: all Rust/TN/research tests pass, harness remains 223 passing tests,
no warnings or whitespace errors.

- [ ] **Step 10: Commit the verified submission with exact paths**

```bash
git add README.md \
  mystery-A.txt \
  mystery-B.txt \
  mystery-C.txt \
  mystery-D.txt \
  predictions/mystery-A/test_outputs.csv \
  predictions/mystery-B/test_outputs.csv \
  predictions/mystery-C/test_outputs.csv \
  predictions/mystery-D/test_outputs.csv \
  research/RESULTS.csv \
  research/analyze.py \
  research/test_analyze.py \
  research/FINAL_REPORT.md \
  research/FROZEN_COMPARISON.json \
  research/MANIFESTS.ndjson \
  research/MANIFESTS.sha256 \
  research/run-specs \
  research/accuracy-gate-runtime.png \
  research/scaling.png \
  reblind/revealed-after-freeze/generator.rs \
  reblind/revealed-after-freeze/seeds.json \
  reblind/revealed-after-freeze/mapping.csv \
  reblind/revealed-after-freeze/AUDIT.md \
  scripts/verify-julia.sh \
  docs/plans/2026-07-23-occam-circuit-rust-bdd-tn.md
git diff --cached --name-only
git commit -m "feat(qcs): solve Occam Circuit challenge 71"
```

- [ ] **Step 11: Finish the branch**

Use `superpowers:verification-before-completion`, request code review, then use
`superpowers:finishing-a-development-branch`. Push and open the leaderboard PR
only after the user chooses that finish option. The PR must link Issue #71 and
state exact gate counts and all four commitment matches without claiming that
the leaked v1 demonstrates blind learning.

---

## Four-to-Five-Day Execution Schedule and Stop Rules

Tasks 1–8 are already complete, so the remaining sprint is:

| Time | Binding work | Exit evidence |
|---|---|---|
| Day 1 morning | Task 9 survey, baseline code/schema, custodian suite and commitment | Protocol gate passes; suite is frozen without proposer row access |
| Day 1 afternoon | Task 10 runner, Task 13 importer, begin synthetic-only candidate worktrees | Hard-cap and digest-boundary tests pass; no row bytes/outcomes exposed |
| Day 2 | Finish Task 11/12/14 hypothesis commits; execute/release exact 360-cell baseline portfolio; public care-BDD/SAT cells | Proposals predate data; both fixed baselines and the checked blind candidate are frozen |
| Day 3 | Task 14 local TN go/no-go; image/stage/test-only/hpccube pilot only if promoted | Four local cells decide TN; native HPC manifests if submitted |
| Day 4 | Six full 180-cell candidate/baseline/repeat runs | Candidate and both baselines have two matched executions; failures are retained and classified |
| Day 5 contingency | Commitment reveal, statistics, plots, Julia differential, report/PR preparation | Explicit `100×`, scaling, or not-demonstrated decision |

Compute feasibility:

- the local care-BDD/order/SAT cells are each capped at five minutes and below
  the harness's 16 GB local threshold;
- one worst-case 180-cell local method pass is 15 CPU-hours and at most
  3.75 hours wall with four workers; the two-method 360-cell frozen baseline
  portfolio is 30 CPU-hours and at most 7.5 hours wall;
- if care-BDD is the frozen candidate, its claim-grade path of two candidate
  passes plus two passes for each fixed baseline is at most 90 CPU-hours, or
  22.5 hours running wall with four workers;
- the initial TN HPC pilot is 24 A800 cells × five minutes = at most two
  A800-GPU-hours, with concurrency three and at most 40 minutes running wall
  time before queue delay;
- one full 180-cell TN pass is at most 15 A800-GPU-hours and five hours
  running wall at concurrency three;
- the claim-grade TN path—two candidate passes and two passes for each fixed
  baseline on matched A800 hardware—costs at most 90 A800-GPU-hours, or 30
  hours running wall at concurrency three, plus the two-GPU-hour pilot and
  queue delay; and
- every run spec remains below the profile's 200-cell limit and runs only after
  the local promotion rule and exact queue/resource card are ratified.

Stop rules:

- If Task 9 is not frozen by the end of Day 1 morning, continue only the
  leakage-disclosed v1 control and make no blind-learning claim.
- Any failure of training consistency, prediction/circuit agreement, exhaustive
  equivalence, deterministic rerun, or official verifier blocks promotion.
- If two successive SAT bounds return `Timeout`/`Unknown`, stop increasing the
  bound and retain the last checked result.
- If no local TN cell meets the promotion rule, do not stage or submit TN HPC
  work.
- If remote staging, image verification, or `sbatch --test-only` is not green
  by Day 3, finish with local evidence; do not spend Day 4 debugging cluster
  setup.
- Freeze algorithm changes 24 hours before the final deadline. The last day is
  for reruns, commitment reveal, statistics, verification, and writing.
- No deadline pressure permits a run beyond 300 seconds, exposure of sealed
  data, an undocumented aggregate, or a claim unsupported by the predeclared
  decision rule.

---

## Self-Review Checklist

- [ ] Every ratified workflow has a task: semantic v1 (Tasks 4–5), complete-
  table ROBDD/OxiDD/order diagnostics (Tasks 6–8), survey and benchmark freeze
  (Task 9), autoresearch/firewall (Task 10), blind care-set ROBDD (Task 11),
  exact/local SAT (Task 12), public reblind import (Task 13), TN/HPC enumeration
  (Task 14), and common evaluation/research decision (Task 15).
- [ ] Every production module first appears behind a failing focused test.
- [ ] `Family`, table, XAG, ROBDD, care-set, order, SAT-result, and circuit
  signatures are consistent between tasks.
- [ ] Accuracy, training consistency, deterministic reruns, exhaustive
  equivalence, prediction/circuit agreement, commitments, and Julia
  differential checks are explicit release gates.
- [ ] The proposer cannot read family names, generator code, secret seeds,
  sealed labels, per-example errors, or custodian storage.
- [ ] Task 13's digest-checked public importer is committed before any baseline,
  care-BDD, or TN cell reads public rows.
- [ ] The exact 360-row baseline matrix, both fixed baselines, and one
  visible-selected candidate/configuration are committed before sealed
  candidate evaluation.
- [ ] Both larger benchmark tiers, five independent benchmark seeds, two observation
  fractions, matched hardware, timeout handling, bootstrap intervals, and the
  `100×`/scaling decision rule are explicit.
- [ ] OxiDD and TN are oracles/candidate producers; neither replaces the
  challenge-native XAG scorer.
- [ ] The hpccube plan stages a clean commit/offline image, uses one A800 per
  independent five-minute cell, scheduler-tests and ratifies every distinct
  smoke/pilot/candidate/baseline/repeat spec, monitors, fetches, and classifies
  before claims.
- [ ] Runner success requires `verifier="pass"`; no failed, skipped, timed-out,
  OOM, or malformed cell can be counted as success or dropped from analysis.
- [ ] No top-level harness integration or unratified HPC submission is included.
- [ ] No global minimality claim is inferred from a local SAT UNSAT result.
- [ ] `Timeout` and `Unknown` can never become SAT `Unsat`.
- [ ] No generic real MPS-to-BDD conversion is assumed.
