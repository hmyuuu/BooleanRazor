# BooleanRazor Deliverability and Verifier Infrastructure Design

**Date:** 2026-07-30
**Status:** approved design; implementation planning follows user review
**Repository:** `/Users/hmyuuu/workspace/BooleanRazor`

## 1. Purpose

BooleanRazor already contains a strong exact Boolean-circuit core, a frozen
blind-study protocol, bounded experiment infrastructure, and several carefully
recorded hypothesis branches. It is not yet a coherent deliverable:

- current conclusions are scattered across a 3,551-line plan, handoff files,
  branch-local logs, and static documentation;
- the public-facing README does not expose the implemented command and
  verification paths;
- internal Rust equivalence and the official Julia verifier are not represented
  consistently;
- `frozen-baseline` currently writes `verifier:"pass"` after only internal
  Rust equivalence, while other candidates correctly write `not_run`;
- the runner discards otherwise valid candidate evidence when Julia has not
  run, so a later verifier cannot bind a trustworthy post-run decision;
- there is no executable state machine from a result to
  advance/freeze/promote/reject;
- the useful methods and negative results are not packaged as reusable
  repository skills.

This design turns the repository into an evidence-first research deliverable
without importing unpromoted algorithms or overstating the blind result.

## 2. Current scientific boundary

The deliverable must state the following without weakening or inflating it:

1. The disclosed v1 controls A=`x+y`, B=`abs(x-y)`, C=`x*y`, and
   D=`x²+y²` have exact constructive circuits with 37, 49, 168, and 127
   reachable challenge gates.
2. Those controls are not blind-learning evidence and are not minimality
   proofs.
3. Shared complemented ROBDD construction, challenge-native XAG extraction,
   OxiDD differential checks, deterministic order search, bounded local SAT
   resynthesis, the opaque public importer, and the five-minute evidence runner
   are implemented on `main`.
4. Care-BDD and SAT results on `main` are synthetic/internal correctness
   evidence, not blind benchmark performance.
5. The public reblind row bundle is absent. `research/BASELINES.csv` has no
   executed baseline rows. No sealed confirmation, matched `100×` result, or
   scaling result exists.
6. Therefore blind advantage has not been demonstrated because claim-grade
   blind evaluation has not occurred. This is not a statistically supported
   negative performance result.
7. Branch-only outcomes are historical evidence, not mainline implementation:
   the fair scheduler was deterministic but tied the control and was rejected;
   GreedyExactConflict improved the synthetic gate tie-break while exact-row CV
   remained zero and advanced only to a public-candidate decision; the TN
   branch proved a deterministic synthetic pipeline only; the Julia branch
   contains reviewed wrapper code and a disclosed-v1 official-verifier run.

## 3. Goals

The implementation will:

- create an original, readable, offline static web report;
- derive the web report and concise Markdown navigation from one canonical
  evidence source;
- expose supported conclusions, missing proof, branch-only lessons, methods,
  commands, and the verifier path;
- integrate the reviewed official-Julia wrapper and its adversarial tests;
- represent internal equivalence separately from official verification;
- preserve valid candidate artifacts for later official verification;
- write a digest-bound official verification record without mutating original
  runner evidence;
- provide a fail-closed promotion checker with evidence-track-specific maximum
  decisions;
- add repository skills for exact-circuit optimization and evidence promotion;
- rewrite `AGENTS.md` as a practical decision tree;
- correct stale standalone paths and command navigation;
- keep all report generation and validation deterministic and dependency-free;
- preserve the user's existing uncommitted `docs/LEADERBOARD.md` change.

## 4. Non-goals

This deliverability pass will not:

- merge care-BDD, GreedyExactConflict, projected-support, or TN hypothesis code
  from their experiment branches;
- claim a blind result, global circuit minimality, or an official aggregate not
  defined by the challenge;
- mount public or sealed benchmark data;
- install Julia, JAX, a full static-site framework, or other heavy tools;
- submit remote or Slurm work;
- deploy or publish the web report;
- modify the evaluator contract to turn an ineligible candidate into a pass;
- manufacture fresh external-verifier evidence when the official runtime or
  dataset is unavailable.

## 5. Chosen approach

Use a small evidence-driven static-site generator implemented with the Python
standard library.

This is preferred over hand-maintained HTML because it prevents claim drift,
and over MkDocs/Astro because it adds no package stack or second project
environment. The design adapts only the useful information architecture from
the requested reference commit:

<https://github.com/LiuZY613/quantum.harness/commit/3ed4239e4ce1b6605e20ed5e7702996bac94697a>

The reference's targeted diff is `report/report.json`, which separates
structured report content from a rendered static page. BooleanRazor will use
its own schema, prose, renderer, navigation, and visual design. No source,
style, data, circuit result, or claim is copied.

## 6. Architecture

```text
reports/data/project.json
          |
          +--> scripts/build-report.py
          |      +--> reports/site/index.html
          |      +--> reports/site/methods.html
          |      +--> reports/site/verification.html
          |      +--> reports/site/experiments.html
          |      +--> docs/STATUS.md
          |      +--> docs/METHODS.md
          |      +--> docs/EXPERIMENT_INDEX.md
          |      `--> research/EVIDENCE_LEDGER.md
          |
          `--> scripts/check-deliverable.py

candidate artifacts + runner manifest
          |
          +--> scripts/verify-julia.sh
          `--> scripts/record-verification.py
                   `--> official-verification.json

promotion-request.json
 + runner/control evidence
 + deterministic rerun bindings
 + official verification records
 + optional frozen/sealed comparison evidence
          |
          `--> scripts/check-promotion.py
                   `--> deterministic promotion-decision.json
```

## 7. Canonical evidence model

`reports/data/project.json` is the only hand-edited report source. It uses
canonical UTF-8 JSON with sorted keys and one final LF. It contains:

- `schema_version`;
- project title, concise purpose, and current conclusion;
- disclosed-control rows;
- method records;
- experiment records;
- claim records;
- verification-layer definitions;
- command/navigation records;
- external references.

Each claim has:

```text
claim_id
track
status
summary
evidence
limitations
missing_proof
```

Allowed `track` values are:

- `disclosed_control`;
- `synthetic`;
- `blind_visible`;
- `sealed_confirmation`.

Allowed `status` values are:

- `verified_main`;
- `verified_branch_only`;
- `rejected`;
- `proposed`;
- `blocked`;
- `absent`.

Evidence references are typed:

- a tracked repository path;
- a commit SHA plus historical path;
- a command;
- a test name;
- an external URL.

The checker validates:

- exact keys and enum values;
- unique IDs;
- canonical JSON bytes;
- tracked-path existence;
- lowercase full commit SHA syntax;
- safe URLs;
- nonempty limitations for every non-main or incomplete claim;
- absence of a blind-success claim without sealed-confirmation evidence;
- absence of `official_verifier=pass` without a bound official verification
  record;
- exact disclosed-control gate counts and explicit control-only labeling;
- no family/generator/sealed fields inside proposer-facing records.

Branch-only commit references need not be reachable in a future shallow clone,
but their full SHA, branch role, outcome, limitation, and summarized evidence
remain in the tracked canonical ledger.

## 8. Static report

### 8.1 Pages

`reports/site/index.html`

- one-sentence current conclusion;
- disclosed control versus blind-study separation;
- current control gate table;
- evidence-level summary;
- implemented/blocked/absent status;
- next ratified gate;
- links to exact commands and tracked evidence.

`reports/site/methods.html`

- exact table/XAG/ROBDD core;
- arithmetic controls;
- order search and care completion;
- bounded SAT resynthesis;
- OxiDD's oracle-only role;
- sealed-study runner/importer infrastructure;
- branch-only lessons and negative results;
- supported later optimization directions and stop rules.

`reports/site/verification.html`

- verification ladder;
- internal-equivalence versus official-verifier semantics;
- v1 archive-backed command;
- official Julia wrapper command;
- runner and post-run verification records;
- promotion request and decision examples;
- checks that are currently unavailable or not run.

`reports/site/experiments.html`

- a status table for main, branch-only, rejected, proposed, blocked, and absent
  work;
- exact commit/source references;
- outcomes and decision boundaries;
- no dynamic public leaderboard snapshot.

### 8.2 Rendering properties

- original CSS and JavaScript;
- semantic HTML, keyboard-visible navigation, accessible color contrast, and
  descriptive table/figure text;
- responsive layout and print/PDF stylesheet;
- no external fonts, trackers, CDNs, or runtime network access;
- local relative links only;
- HTML escaping for all evidence content;
- deterministic page bytes;
- generator/source digest embedded in each generated page;
- English-first content; the schema permits a future translation without
  requiring it now.

### 8.3 Markdown outputs

The same renderer produces:

- `docs/STATUS.md`: current supported conclusion, evidence tiers, blockers, and
  next gate;
- `docs/METHODS.md`: concise method map, supported insights, and optimization
  directions;
- `docs/EXPERIMENT_INDEX.md`: experiment/ref/commit/outcome/evidence table;
- `research/EVIDENCE_LEDGER.md`: claim-by-claim scientific proof and missing
  proof.

Each begins with a generated-file marker and the SHA-256 of
`reports/data/project.json`. Manual edits are rejected by
`make report-check`.

## 9. Official Julia verification

### 9.1 Wrapper

Port the reviewed `scripts/verify-julia.sh` from the Task 15 branch rather than
the whole branch. Preserve its fail-closed behavior:

- exactly six positional arguments;
- executable Julia binary;
- regular, non-symlink verifier/circuit/dataset inputs;
- safe instance label and canonical expected gate count;
- canonical LF `input,output` dataset;
- exact four-line official output;
- expected sample count, gate count, exact accuracy `1.0`, and bit accuracy
  `1.0`;
- nonzero exit on any mismatch, extra line, malformed metric, or Julia error;
- `--startup-file=no --history-file=no`;
- a single canonical summary line only after every check passes.

Port and adapt the branch's fixture/adversarial tests into the main test suite.
The integration records the historical disclosed-v1 Julia run as historical
evidence bound to its original source commit. It does not call it a fresh
current-HEAD rerun.

### 9.2 Bound verification record

Add `scripts/record-verification.py`:

```text
python scripts/record-verification.py \
  --manifest RUN/cells/CELL/manifest.json \
  --julia-bin /absolute/path/to/julia \
  --verify-jl /absolute/path/to/verify.jl \
  --dataset /absolute/path/to/dataset.csv \
  --output RUN/cells/CELL/official-verification.json
```

It:

1. rejects noncanonical or symlinked paths;
2. validates the runner manifest and artifact index;
3. hashes the manifest, circuit, dataset, verifier, and Julia version output;
4. invokes `verify-julia.sh`;
5. parses the wrapper's single canonical summary;
6. rechecks all bound files after execution to detect replacement races;
7. writes canonical sorted-key JSON atomically without overwriting an existing
   record.

The record contains:

```text
schema_version
manifest_sha256
run_spec_sha256
comparison_id
circuit_sha256
dataset_sha256
verify_jl_sha256
julia_version
gates
samples
exact_accuracy
bit_accuracy
status
```

`status` is exactly `pass`. A failed invocation writes no pass record; failure
remains in command logs or a separately requested diagnostic, never in a
promotion credential.

## 10. Runner and metrics semantics

### 10.1 Internal versus external result

`artifact.json` remains the authority for internal exhaustive equivalence:

```json
{"equivalence":"pass"}
```

The exact metrics field `verifier` describes only the official external
verifier:

- `pass`;
- `fail`;
- `not_run`.

`frozen-baseline` changes from `pass` to `not_run`. Care-BDD and SAT retain
their truthful `not_run` value. No producer may set `pass` merely because Rust
evaluation succeeded.

### 10.2 Terminal evidence retention

The runner keeps valid candidate evidence for:

- `SUCCESS` with `verifier=pass`;
- `VERIFIER_NOT_RUN` with `verifier=not_run`;
- `VERIFIER_FAILED` with `verifier=fail`.

For all three, the child must have:

- exited zero;
- emitted exact valid metrics;
- produced the fixed canonical table, circuit, and artifact index;
- passed internal equivalence;
- matched every required digest;
- reported `train_exact=1.0`.

The manifest retains quality metrics, completed-table/circuit/artifact hashes,
and paths for those three statuses. Only `SUCCESS` is a successful runner
result.

Timeout, OOM, nonzero exit, invalid metrics, cancellation, missing success
manifest, and scheduler-only failures retain no candidate quality or artifact
claim. Existing censored timing and failure evidence rules remain unchanged.

Update `research/check_gate.py`, runner tests, materializer tests, and protocol
wording to enforce the new distinction. The materializer still never creates
candidate evidence or success.

## 11. Promotion checker

Add `scripts/check-promotion.py` with:

```text
python scripts/check-promotion.py \
  --request promotion-request.json \
  --output promotion-decision.json
```

### 11.1 Request

The canonical request contains:

```text
schema_version
track
candidate_evidence
deterministic_pairs
official_verifications
frozen_comparison
sealed_results
```

Inapplicable values are the literal `none`, not missing or blank. Paths are
resolved relative to the request file, cannot escape its evidence root, and
cannot be symlinks.

### 11.2 Common gates

Every positive decision requires:

- canonical evidence;
- one clean source commit/tree identity;
- the declared dataset boundary;
- valid training consistency;
- internal exhaustive equivalence;
- artifact/transitive digest agreement;
- byte-identical deterministic pairs;
- an official verification pass bound to every promoted circuit;
- no missing predeclared cells or filtered terminal failures;
- a decision compatible with the evidence track.

### 11.3 Maximum decisions

| Track | Maximum positive decision |
| --- | --- |
| `disclosed_control` | `promote_control` |
| `synthetic` | `advance_public_candidate` |
| `blind_visible` | `freeze_candidate` |
| `sealed_confirmation` | `promote_blind_result` |

The checker may also emit:

- `reject` when present evidence violates an eligibility or decision rule;
- `blocked` when required evidence has not been produced;
- `no_change` when evidence is valid but fails a strict-improvement rule.

The decision contains sorted reason codes, the input-file digests, and the
highest legal next step. It contains no wall-clock timestamp so identical
inputs produce byte-identical output.

### 11.4 Track-specific rules

`disclosed_control`

- verifies circuits/predictions, commitments, deterministic reruns, and Julia
  records;
- never emits a blind-learning claim.

`synthetic`

- may advance a precommitted hypothesis only under its declared
  accuracy-first comparison;
- cannot promote a result regardless of gate improvement.

`blind_visible`

- requires the frozen public design and complete visible-only manifests;
- may freeze exactly one configuration;
- cannot read or infer sealed outcomes.

`sealed_confirmation`

- requires `FROZEN_COMPARISON.json`, every predeclared candidate and baseline
  row, normalized failed cells, deterministic repeats, bound verifier records,
  matched hardware/caps/provenance, and the predeclared analysis decision;
- can promote only when the existing `100×` or scaling rule passes against
  both baseline curves;
- otherwise emits `no_change`, `reject`, or `blocked` with exact reasons.

The absent public bundle and sealed results mean the current repository should
produce `blocked`, not a blind promotion.

## 12. Reusable repository skills

Use the local skill-creation workflow to author and validate two skills.

### 12.1 `exact-circuit-optimization`

Purpose: guide a later optimization hypothesis without changing the evidence
contract.

It covers:

- identifying the evidence track and cost model;
- fresh-worktree/precommit hypothesis discipline;
- accuracy-first eligibility;
- challenge-native reachable XAG scoring with free negation;
- arithmetic-control separation;
- order/search scheduling and diversity;
- bounded exact SAT results and `Timeout`/`Unknown` handling;
- retaining informative failed/equal/worse topologies without promoting them;
- exhaustive equivalence and deterministic artifact requirements;
- stopping, recording, and choosing the next hypothesis.

It cites BooleanRazor's mainline and summarized branch evidence, while marking
branch-only insights as non-promoted.

### 12.2 `circuit-evidence-promotion`

Purpose: move an existing result through internal verification, Julia
verification, freeze, and promotion decisions.

It covers:

- evidence-track selection;
- runner and artifact validation;
- creating an official verification record;
- deterministic-pair checks;
- building a canonical promotion request;
- interpreting `blocked`, `reject`, `no_change`, and positive decisions;
- updating reports and leaderboards only after the corresponding gate;
- wording control, synthetic, visible, and sealed claims accurately.

Both skills are registered in `Ion.toml` and pass `make skills`.

## 13. `AGENTS.md` redesign

`AGENTS.md` becomes the primary operational router rather than a policy-only
summary.

Sections:

1. **Current answer** — what is verified, branch-only, and blocked.
2. **First actions** — context, branch/HEAD/status, setup, skills, tests, and
   baseline failure recording.
3. **Choose the activity** — audit, code change, synthetic experiment, public
   experiment, sealed evaluation, or HPC.
4. **Choose the evidence track** — disclosed, synthetic, blind-visible, or
   sealed.
5. **Data-access gate** — exact allowed and prohibited inputs.
6. **Candidate routes** — v1, baseline, care-BDD, SAT, OxiDD, TN branch, with
   exact feature/command boundaries.
7. **Verification ladder** — training, internal equivalence, deterministic
   rerun, official Julia, sealed evaluator.
8. **Runner rules** — absolute commands/paths because the child runs in its
   cell directory, terminal status meanings, and evidence retention.
9. **Promotion state machine** — exact maximum decision by track.
10. **HPC gate** — unchanged explicit resource-card approval.
11. **Documentation/report update** — `make report` and
    `make report-check`.
12. **Repository map** — code, protocols, evidence, reports, skills, and
    handoff authority.

It links to the generated status, method, experiment, and evidence pages
instead of duplicating long histories.

## 14. Documentation corrections

Update:

- `README.md` with architecture, command matrix, verification levels, web
  report entry, current evidence boundary, and missing proof;
- `autoresearch/README.md` to copy `autoresearch/LOG_TEMPLATE.md` from the
  standalone root and to use absolute runner child paths;
- `reblind/README.md` to document `learn-care`, official-verification follow-up,
  and visible versus sealed decisions;
- `docs/handoff/SESSION_HANDOFF.md` to distinguish current main, branch-only
  outcomes, and the absent public bundle;
- the active plan only where commands or status text are materially stale and
  needed for safe navigation.

Do not restore the removed dynamic public-field section in
`docs/LEADERBOARD.md`. Any future public ranking snapshot must be dated,
sourced, and separate from scientific blind evidence.

## 15. Build and check commands

Add:

```text
make report
make report-check
make test-verifier
make test-promotion
```

`make report` regenerates all report HTML and Markdown deterministically.

`make report-check` renders into a temporary directory, compares exact bytes
with committed outputs, validates links/schema/claims, and fails on drift.

`make test-verifier` runs the wrapper and verification-record tests without
requiring a real Julia installation.

`make test-promotion` runs all state-machine and forbidden-transition tests.

`make test` includes report, verifier, and promotion checks so the deliverable
cannot silently drift.

## 16. Error handling and safety

All new tools fail closed:

- reject symlinks and path escapes;
- reject noncanonical JSON, duplicate keys, NaN/infinity, Boolean-as-integer,
  unknown fields, unknown enum values, and missing final LF;
- use bounded regular-file reads;
- use atomic non-overwriting output;
- re-hash inputs after external execution;
- never rewrite a runner manifest or official verification record;
- never turn missing verification into pass;
- never let report prose exceed the evidence track's maximum claim;
- never allow a branch-only experiment to appear as mainline implementation;
- never let sealed paths or fields enter proposer/report data;
- preserve failed and timed-out cells.

## 17. Testing strategy

Use TDD for each production behavior.

### Report tests

- missing generator/data failures;
- canonical schema and duplicate-ID rejection;
- HTML escaping and safe links;
- deterministic pages and Markdown;
- committed-output freshness;
- forbidden blind-success claim;
- branch-only status rendering;
- broken tracked evidence path;
- responsive/print markup smoke checks.

### Verifier tests

- exact successful fixture;
- wrong gate/sample/exact/bit values;
- extra/duplicate/missing output lines;
- nonzero Julia exit;
- unsafe instance, malformed dataset, CRLF, symlinks;
- manifest/artifact/dataset/verifier replacement races;
- digest mismatch;
- existing output non-overwrite;
- deterministic record bytes.

### Runner/checker tests

- baseline emits `not_run`;
- `VERIFIER_NOT_RUN` and `VERIFIER_FAILED` retain only validated candidate
  evidence;
- those statuses never count as runner success;
- malformed artifacts still discard quality claims;
- scheduler materialization still cannot create candidate evidence;
- research checker accepts the revised truthful schema and rejects false pass.

### Promotion tests

- every positive transition;
- every track ceiling;
- synthetic-to-blind promotion rejection;
- visible-only-to-sealed promotion rejection;
- missing/foreign/stale Julia record;
- nondeterministic pair;
- mixed source/tree/hardware/cap;
- missing or filtered baseline cell;
- failure normalization;
- absent public/sealed evidence produces deterministic `blocked`;
- equal/worse strict comparison produces `no_change`;
- deterministic decision bytes.

### Final verification

- focused new tests;
- `make skills`;
- `make report-check`;
- `make test`;
- `git diff --check`;
- visual inspection of all report pages at desktop and mobile widths;
- final diff review proving the pre-existing leaderboard edit was not
  overwritten.

## 18. File layout

```text
reports/
├── README.md
├── data/
│   └── project.json
└── site/
    ├── index.html
    ├── methods.html
    ├── verification.html
    ├── experiments.html
    └── assets/
        ├── report.css
        └── report.js

scripts/
├── build-report.py
├── check-deliverable.py
├── verify-julia.sh
├── record-verification.py
└── check-promotion.py

docs/
├── STATUS.md
├── METHODS.md
├── EXPERIMENT_INDEX.md
└── superpowers/specs/
    └── 2026-07-30-booleanrazor-deliverability-verifier-design.md

research/
└── EVIDENCE_LEDGER.md

skills/
├── exact-circuit-optimization/
│   ├── SKILL.md
│   └── references/
└── circuit-evidence-promotion/
    ├── SKILL.md
    └── references/

tests or focused Python test directories/
├── report generation and deliverability tests
├── Julia wrapper/record tests
└── promotion state-machine tests
```

Exact test paths will follow the nearest existing convention selected during
implementation planning.

## 19. Acceptance criteria

The deliverability pass is complete only when:

1. one canonical evidence source deterministically produces all committed web
   and Markdown reports;
2. the reports clearly separate disclosed controls, synthetic evidence,
   visible blind work, sealed confirmation, and missing proof;
3. the report is readable offline, responsive, printable, and free of external
   runtime assets;
4. current supported methods, branch-only lessons, negative results, and later
   optimization directions are navigable;
5. the reviewed Julia wrapper and adversarial tests are on `main`;
6. internal equivalence cannot be reported as official verifier pass;
7. baseline/care/SAT candidate metrics use truthful verifier states;
8. valid unverified/failed-verifier candidate artifacts remain digest-bound and
   auditable without becoming successful;
9. official verification records are immutable, transitive, race-checked, and
   bound to candidate evidence;
10. the promotion checker enforces every evidence-track ceiling and produces
    deterministic decisions;
11. the absent blind data currently results in a truthful blocked decision;
12. both repository-specific skills are registered and validated;
13. `AGENTS.md`, README, autoresearch, reblind, handoff, and command navigation
    agree;
14. focused tests, `make skills`, `make report-check`, the complete
    `make test`, and `git diff --check` pass;
15. no user-owned leaderboard edit, hidden data, run result, heavy dependency,
    remote job, or experimental branch implementation is included.
