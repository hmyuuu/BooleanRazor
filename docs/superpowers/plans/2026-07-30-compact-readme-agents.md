# Compact README and Agent Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long project introduction and agent guide with compact, accurate documents that preserve the repository's evidence and safety boundaries.

**Architecture:** `README.md` will serve as the public project summary and navigation page. `AGENTS.md` will remain the operational authority, with concise commands and links to detailed workflows instead of repeated explanations.

**Tech Stack:** Markdown, Make, Git

## Global Constraints

- Keep `README.md` near 50–70 lines and remove command examples.
- Keep `AGENTS.md` near 70–100 lines and retain essential commands and instructions.
- Preserve the current evidence ceiling: blind advantage has not been demonstrated.
- Preserve data-access, verification, promotion, report-generation, and HPC approval rules.
- Do not edit generated reports, generated Markdown views, source code, or evidence records.

---

### Task 1: Compact the public README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `docs/STATUS.md`, `docs/METHODS.md`, `docs/EXPERIMENT_INDEX.md`, and `research/EVIDENCE_LEDGER.md`.
- Produces: a short public overview that links readers to the authoritative detail.

- [ ] **Step 1: Replace repeated detail with six short sections**

Use this order:

1. project purpose;
2. current scientific answer;
3. disclosed-control gate-count table;
4. evidence boundaries;
5. verification summary;
6. navigation links.

State the synthetic frontier as historical branch-only evidence and state that
public baseline, visible-blind, and sealed results are absent or blocked.

- [ ] **Step 2: Remove implementation and command material**

Delete the architecture diagram, verification/status matrices, setup code
block, command matrix, runner invocation, Julia wrapper example, and promotion
command example.

- [ ] **Step 3: Check length and formatting**

Run:

```bash
wc -l README.md
git diff --check -- README.md
```

Expected: about 50–70 lines and no whitespace errors.

### Task 2: Compact the operational agent guide

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: `GOAL.md`, generated status documents, the active plan, the handoff, and vendored workflow skills.
- Produces: the startup, evidence, experiment, promotion, reporting, and HPC rules that agents must follow.

- [ ] **Step 1: Retain the startup command block**

Keep the clean-checkout sequence:

```bash
make setup
make skills
make test
make report-check
```

Require agents to inspect `git status --short`, preserve unrelated work, and
choose an evidence track before accessing data or changing claims.

- [ ] **Step 2: Condense operational rules**

Keep:

- the four evidence tracks and their maximum decisions;
- the disclosed-control claim boundary and challenge gate metric;
- the public/sealed data firewall;
- one-worktree-per-hypothesis and root `LOG.md`;
- the 300-second cell cap and failure preservation;
- the verification ladder;
- evidence-bound promotion;
- explicit approval before heavy installs, nonpublic data, sealed access, or Slurm;
- `reports/data/project.json` as the only hand-edited report source.

Link to detailed skills and protocol documents instead of restating method,
runner-schema, status-code, candidate-route, and repository-map detail.

- [ ] **Step 3: Check length and formatting**

Run:

```bash
wc -l AGENTS.md
git diff --check -- AGENTS.md
```

Expected: about 70–100 lines and no whitespace errors.

### Task 3: Verify the documentation rewrite

**Files:**
- Verify: `README.md`
- Verify: `AGENTS.md`

**Interfaces:**
- Consumes: the rewritten guides.
- Produces: evidence that links, generated artifacts, and project claims remain valid.

- [ ] **Step 1: Check protected claims and links**

Run:

```bash
rg -n "Blind advantage has not been demonstrated|300 seconds|reports/data/project.json|sealed|official-verification.json" README.md AGENTS.md
```

Expected: the scientific ceiling and key operational constraints remain
visible.

- [ ] **Step 2: Run repository validation**

Run:

```bash
make report-check
git diff --check
git status --short
```

Expected: report validation passes, the diff has no whitespace errors, and
only the approved documentation files plus this plan are modified.

- [ ] **Step 3: Review the final diff**

Run:

```bash
git diff -- README.md AGENTS.md
```

Confirm that no command was added to `README.md`, operational commands remain
in `AGENTS.md`, and no rule permits a stronger claim or broader data access.
