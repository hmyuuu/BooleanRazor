# BooleanRazor vendored-skill provenance

Audit date: 2026-07-27 (Asia/Shanghai)

This inventory defines the skill directories selected for the standalone
BooleanRazor workspace. Copy each directory recursively, including scripts,
references, templates, and other companion files; copying only `SKILL.md` is
not equivalent.

## External packages

### obra/superpowers

- Upstream: `https://github.com/obra/superpowers.git`
- Audited source root:
  `/Users/hmyuuu/Library/Application Support/ion/repos/f8a3f25821e2a56d`
- Audited commit: `d884ae04edebef577e82ff7c4e143debd0bbec99`
- Source worktree status at audit: clean
- License: MIT, copyright 2025 Jesse Vincent
- License payload to copy:
  - source: `/Users/hmyuuu/Library/Application Support/ion/repos/f8a3f25821e2a56d/LICENSE`
  - destination: `skills/_licenses/obra-superpowers-LICENSE.txt`
  - SHA-256: `a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400`

Copy these complete directories:

- `using-superpowers`
- `using-git-worktrees`
- `brainstorming`
- `writing-plans`
- `executing-plans`
- `subagent-driven-development`
- `test-driven-development`
- `systematic-debugging`
- `requesting-code-review`
- `receiving-code-review`
- `verification-before-completion`
- `finishing-a-development-branch`
- `dispatching-parallel-agents`

### QuantumBFS/sci-brain

- Upstream: `https://github.com/QuantumBFS/sci-brain.git`
- Audited source root:
  `/Users/hmyuuu/Library/Application Support/ion/repos/f69251a4fb3b55f1`
- Audited commit: `e89fc0b088e47a19e386d1cd6aae16009e51f052`
- Source worktree status at audit: clean
- License: MIT, copyright line contains only the year 2025
- License payload to copy:
  - source: `/Users/hmyuuu/Library/Application Support/ion/repos/f69251a4fb3b55f1/LICENSE`
  - destination: `skills/_licenses/QuantumBFS-sci-brain-LICENSE.txt`
  - SHA-256: `06dcddbb6908a0c6dd4a9e8ec822eea41d5a460a53089fecccc8a68049e99241`

Copy the complete `survey` and `download-ref` directories. They remain from
the same audited package commit so survey's `resolve_kb.py` and indexing
helpers are present.

## Local sources with no declared license

### session-handoff

- Audited source:
  `/Users/hmyuuu/.agents/skills/session-handoff`
- The source is not in a Git repository and no enclosing `LICENSE`,
  `COPYING`, or `NOTICE` was found under `/Users/hmyuuu/.agents`.
- `SKILL.md` SHA-256:
  `8c781272f8422ed1f16812a323eb6d4dde770ee24def2055d4c9d07bbf8b856d`
- License status: `NOASSERTION`; do not infer a license.

Copy the complete `session-handoff` directory.

### quantum.harness local skills

- Upstream source repository:
  `https://github.com/QuantumBFS/quantum.harness.git`
- Audited worktree:
  `/Users/hmyuuu/.codex/worktrees/583b/quantum.harness`
- Audited worktree commit:
  `749bb60b464558f85880502a27eed7b421151ba0`
- The selected paths were clean at audit.
- No root `LICENSE`, `LICENCE`, `COPYING`, or `NOTICE` was present in the
  audited commit or the locally available `upstream/main`; no license
  declaration was found inside the selected skill directories.
- License status: `NOASSERTION`; do not infer that publication or
  redistribution is licensed.

Copy these complete directories:

| Directory | Last local commit touching the directory |
|---|---|
| `take-challenge` | `052351dac531babadac62091f84d0a9abd63f5c4` |
| `using-slurm` | `26f0f5737f25ba5d58f09a5446c2e0ebbdfd4b11` |
| `cluster-jobs` | `c071a30a0889be301a27c4afea2c2f08a3b4158f` |
| `setup-cluster` | `c071a30a0889be301a27c4afea2c2f08a3b4158f` |
| `build-apptainer-image` | `b85f9ce411d997a32635ba414479d9a7234003a2` |
| `using-jax` | `e68f5b191fe81b12cf7942ee7400f8b6d459fbf7` |
| `method-qcs` | `5364899af57fa60c1ad4558cd051e1d27a4a47f0` |

Add `skills/_licenses/UNLICENSED-SOURCES.md` in BooleanRazor to record the
`NOASSERTION` status for `session-handoff` and the quantum.harness-local
skills. That file is a provenance notice, not a license grant.

## Ion lock mismatch

The live Ion cache does not match the source harness's `Ion.lock` pins:

| Package | `Ion.lock` commit | Audited live source commit |
|---|---|---|
| `obra/superpowers` | `3dcbd5c4b48e02263fbf4a3c01e3fe4f81d584d9` | `d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `QuantumBFS/sci-brain` | `df5a3842b03ad8088c37fc94c1e366f767d16a2c` | `e89fc0b088e47a19e386d1cd6aae16009e51f052` |

The copied bytes must therefore be described as snapshots of the audited live
commits above, not as material reproduced from the old `Ion.lock`. In the
standalone repository, declare the vendored directories as local skills and
either generate a matching new lockfile or omit a misleading inherited lock.

## Cluster-data boundary

The audited Git-tracked `using-slurm` tree contains:

- public `qdeshell.toml` and `scnet.toml` capability profiles,
- the public `localhost.toml` test fixture,
- public HKUST-GZ batch templates,
- no `profiles/active.toml`,
- no inline password, token, private key, or key material.

The source `.gitignore` explicitly treats per-user profiles and
`profiles/active.toml` as local-only. Copy only the audited Git-tracked
`using-slurm` files. Do not copy ignored/untracked profiles, an active-profile
symlink, `~/.ssh`, SSH configuration, `.env` files, credential stores, or
private custodian/evaluation data. The `qdeshell` alias is only a public handle;
it still requires separately configured user access and explicit compute
ratification.

At the standalone boundary, BooleanRazor adds a newly authored,
credentials-free `profiles/hpccube.toml` and an `active.toml` symlink to it.
They contain only the user-provided SSH alias plus the already audited public
QDES capability limits, point the remote project to `~/BooleanRazor`, and do
not authorize a submission.

## Functional dependency risks

1. `survey` invokes the vendored
   `skills/download-ref/helpers/{resolve_kb.py,append_bibtex.py,index.py}`.
   PDF rendering still requires separately approved external tools; the raw
   downloads and extracted figures remain excluded.
2. `using-slurm`, `cluster-jobs`, and `setup-cluster` invoke repository-level
   helpers including `scripts/harness_slurm.sh`,
   `scripts/harness_array_sbatch.sh`, `scripts/cluster_profile.py`, and
   `scripts/cluster_guardrail.py`. Copying the skills alone does not provide
   the HPC mechanism.
3. `using-jax` refers to harness documentation and `make install jax`; the
   standalone Makefile and environment must provide an equivalent target or
   the card must be adapted.
4. `method-qcs` routes to `using-tensorcircuit-ng` and cites harness docs and
   literature paths that are outside this copy map. It remains useful as
   methodology context, but its full route is not self-contained.
5. `take-challenge` is tied to upstream quantum.harness registration paths and
   pull-request conventions. In BooleanRazor it is historical/workflow context,
   not the implementation driver.
6. Vendoring remote package skills as Ion-local directories can remove the
   displayed `superpowers:` / `sci-brain:` namespace. Keep each frontmatter
   `name` unchanged and make the standalone `Ion.toml` names unambiguous.
7. The missing license declarations for local sources are a distribution
   blocker to resolve before publishing them from a new public repository.
