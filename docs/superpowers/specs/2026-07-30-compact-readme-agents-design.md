# Compact README and Agent Guide

## Goal

Make `README.md` and `AGENTS.md` shorter, easier to scan, and free of repeated
explanation without weakening the repository's evidence boundaries.

## README

Target about 50–70 lines. Keep:

- the project purpose and current scientific answer;
- the disclosed-control gate counts and their claim boundary;
- a short evidence and verification summary;
- links to status, methods, experiments, evidence, and agent instructions.

Remove command examples, architecture diagrams, detailed method descriptions,
runner internals, and status tables duplicated by generated documents.

## AGENTS

Target about 70–100 lines. Keep concise operational instructions and commands:

- required startup checks;
- activity and evidence-track routing;
- data-access and claim boundaries;
- the 300-second runner limit and deterministic verification ladder;
- promotion, HPC approval, and generated-report rules;
- links to the detailed workflow documents and skills.

Remove repeated scientific narrative, implementation background, candidate
method explanations, and detailed schemas already documented elsewhere.

## Validation

Check links and formatting, run `make report-check`, and review the diff for
lost safety or evidence constraints. No generated report file or source code
will change.
