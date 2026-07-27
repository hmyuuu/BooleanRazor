---
name: setup-cluster
user-invocable: false
description: >-
  Use when a usable cluster profile is needed and none exists — a fresh account,
  no `skills/using-slurm/profiles/active.toml`, "set up my cluster", "configure
  HPC", or when `/cluster-jobs` / `/onboard` / `/using-slurm` find no profile.
  Builds the unified TOML profile (ssh + scheduler + partitions), probes live
  resources, and seeds the student safety `[limits]`.
---

# setup-cluster

Make a cluster *usable*: one unified TOML profile per cluster under
`skills/using-slurm/profiles/<name>.toml`, plus the `active.toml` symlink. This
is the single source of truth for cluster readiness — `/onboard` delegates its
cluster stage here, and `/cluster-jobs` / `/using-slurm` route here when no
profile is found. Mirrors `/setup-julia` (dispatched on demand, not a slash
command).

Three things, in order: **build the profile → probe live resources → seed
`[limits]`**. The schema is `skills/using-slurm/references/cluster-profiles.md`
— read it before writing; do not invent fields.

## Idempotency

Skip if `skills/using-slurm/profiles/active.toml` already exists *and* carries a
`[limits]` section. If the profile exists but predates limits, jump straight to
**3. Seed limits** and append them — do not rebuild the profile.

## 1. Build the profile

Ask the warm gate (one `AskUserQuestion`): paste the cluster's docs URL, or walk
through 4 quick questions. Either fills the schema.

**From a docs URL** — dispatch an Agent subagent (`subagent_type:
"general-purpose"`, max-effort framing) to crawl comprehensively, because one
fetch misses the sidebar sub-pages:

<brief name="cluster-docs-crawl">
- Input: the docs root URL.
- Enumerate + fetch every sub-page for: login/connection, scheduler/submission,
  partitions/queues/limits, environment/modules, filesystem, network reach.
- Extract verbatim (sbatch examples, partition tables, module loads, hostnames).
- Synthesize into the TOML schema in `cluster-profiles.md`.
- Flag harness-side gotchas not explicit in docs (non-interactive ssh not
  sourcing `/etc/profile`; two `sbatch` binaries; login-shell-only quirks).
- Output: the `[[documentation]]` URL index, the proposed `<name>.toml`, a
  `[[gotchas]]` list, and any field it could not extract (→ fall to questions
  for those fields only).
- **Coverage, not filtering** — report every partition row and gotcha, even
  uncertain ones. Silently dropping one is the failure mode.
</brief>

Display the proposed `<name>.toml` inline as a fenced block; `AskUserQuestion`:
Accept and save / Edit then save / Discard and use the walk-through. Write only
after Accept or an edit.

**Walk-through fallback (≤4 warm questions):**
1. *"Paste the ssh command you use to reach the login node (e.g. `ssh -i ~/.ssh/id_rsa user@host`), or a `~/.ssh/config` stanza."* → parse `host`/`user`/`identity_file`/`port` into `[connection.ssh]`; default `alias` to the cluster short-name.
2. `AskUserQuestion` workload manager: `Slurm` / `PBS / Torque` / `LSF` / `Plain ssh` / `Not sure — I'll probe`.
3. *"Default queue/partition? Overridable per job."*
4. `AskUserQuestion` region: `Mainland China` / `Outside mainland China` / `Air-gapped` / `Not sure`.

Per the harness UX rule, every question frames the why → states the consequence
→ offers the escape hatch.

## 2. Probe live resources (read-only)

Before seeding limits, see what the cluster actually offers — this both informs
the student and supplies real caps for `[limits]`:

```bash
scripts/harness_slurm.sh --profile <name>.toml probe-partitions   # parsed sinfo: idle/mix/alloc, cores/mem/gpu
```

If the profile carries `[commands].quota_command`, run it read-only over ssh for
the student's own allocation usage (best-effort; skip with a note if absent).
Present a compact **"what's available / your budget"** summary. Purely read-only
— no confirm gate.

## 3. Seed `[limits]`

Propose `[limits]` seeded from the probed `[[partitions]]` caps — real numbers,
not invented:

- `[limits.hard].max_walltime` ← the largest partition `max_wall` (or the
  default partition's, if the student should be fenced tighter).
- `[limits.hard].max_nodes` / `max_cpus` ← partition node/core counts.
- `[limits.hard].max_array_size` ← a conservative default (e.g. 200) unless the
  cluster documents a per-user array cap.
- `[limits.soft]` ← thresholds below the hard caps (warn before the ceiling).
- `[limits.paths].allowed_roots` ← `[filesystem].scratch` + the results dir.

Show the proposed `[limits]` block and get an explicit confirm-or-edit (the
harness "propose for ratification" rule). Students draw on individual
allocations, so these protect each student from their own mistakes.

## 4. Write + activate

Write `skills/using-slurm/profiles/<name>.toml`, symlink `active.toml → <name>.toml`.
Validate shape:

```bash
python3 scripts/cluster_profile.py --field connection.ssh.alias --profile skills/using-slurm/profiles/<name>.toml
```

Confirm one line: *"Cluster profile saved at `…/<name>.toml` with safety limits.
Future jobs use it automatically."* If the profile holds secrets (a real
identity file path is fine; an inline key is not), remind the student to
`.gitignore` it.

Do **not** bootstrap Julia/Python here — that's `/setup-julia` etc., dispatched
on demand by the submitting skill.

## Output

- `skills/using-slurm/profiles/<name>.toml` (unified: connection + scheduler +
  partitions + network + region + `[limits]`) and the `active.toml` symlink.
- A one-line "what's available / your budget" summary from the probe.
- The ratified `[limits]` block.

## Composition

- `/onboard` delegates its cluster-setup stage to this skill.
- `/cluster-jobs` and `/using-slurm` route here when no profile exists.
- `/setup-julia` runs afterward, on demand, for language setup.
