# Migration record

BooleanRazor was exported from the `tracks/qcs/solutions/hmyuuu` subtree of
the quantum.harness worktree. The export preserves the solution's relevant
commit ancestry while removing unrelated harness history.

| Field | Value |
| --- | --- |
| Source HEAD | `c345fa5a2b0a964ee4018bca13cf10fc3b098349` |
| Subtree split commit | `336f4782a1cab3b7586136405e32aaf3aa6ec2cc` |
| Standalone export base | `336f4782a1cab3b7586136405e32aaf3aa6ec2cc` |
| Standalone metadata commit | the commit containing this file |
| Export prefix | `tracks/qcs/solutions/hmyuuu` |
| Standalone branch | `main` |
| Source-to-standalone commit map | `docs/COMMIT_MAP.md` |

## Added at the standalone boundary

- Repository instructions, goal, quick-start, path map, and session handoff.
- The ratified plan and tracked Boolean-synthesis and MPS literature.
- Vendored copies of the workflow skills actually used, with their provenance
  and licenses recorded under `skills/`.
- Reusable local Slurm adapters and their offline tests.
- A uv-managed Python 3.11 test environment.

## Deliberately excluded

- The rest of the stable quantum-many-body harness.
- `.venv`, `target`, transient run results, and ignored raw literature files.
- Public training archives not already tracked in the exported subtree.
- Sealed evaluator rows, mappings, private checksums, and custodian state.
- Credentials, cluster secrets, and implicit authorization to use `hpccube`.

The source-harness remote is provenance only and should not be named `origin`
in the standalone repository. Add a BooleanRazor destination remote only after
the human selects one.
