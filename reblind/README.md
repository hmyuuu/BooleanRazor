# Reblinded benchmark boundary

This directory is the public, committed boundary between an independent
custodian and proposal worktrees. At the proposer-safe source freeze it
intentionally contains only this README:

- `COMMITMENT.txt` does not exist yet;
- `manifest.csv` does not exist yet;
- no public training bundle is mounted;
- no generator, family inventory, secret seed, mapping, complete table, sealed
  digest, or evaluator result is stored here.

`research/check_gate.py --phase protocol` must fail on the missing commitment,
manifest, baseline matrix, and matrix digest until the custodian completes the
separate benchmark build. That failure is expected and prevents accidental
proposal access before the algorithm freeze.

## Custodian publication contract

The custodian operates outside every proposer worktree. It publishes only:

```text
COMMITMENT.txt
manifest.csv
```

The manifest header is exactly:

```text
opaque_id,input_bits,output_bits,train_rows,test_policy,observed_fraction,public_sha256
```

`test_policy` is `all-unobserved`. `public_sha256` is SHA-256 over a canonical
length-framed sequence of the six preceding public fields followed by exact
`train.csv` bytes; every component is an unsigned eight-byte big-endian length
and then that many bytes. The digest excludes its own field, the manifest
header, and line terminator.

The content-addressed public archive is named
`occam-reblind-public-<COMMITMENT>.tar.zst` and contains only:

```text
manifest.csv
instances/<opaque-id>/train.csv
```

The archive and extraction live under the ignored
`results/occam-reblind/public/<COMMITMENT>/` directory. A proposer receives
that exact extraction only through `OCCAM_REBLIND_PUBLIC_ROOT`, and only after
its hypothesis and synthetic-test-only implementation commit is recorded. HPC
staging copies this public directory, never a custodian root.

The committed manifest must contain 180 opaque rows and no family, generator,
secret seed, label, complete-table, sealed-table, or evaluator-derived field.
The accompanying baseline matrix contains exactly two frozen methods × those
180 IDs and is committed atomically with this manifest and commitment.

## Reveal boundary

Generator source, seed material, hidden mappings, complete tables, and sealed
digests remain in custodian-only storage until every algorithm commit is
frozen. A later reproducibility reveal belongs under
`reblind/revealed-after-freeze/`; it is never backfilled into a proposer’s
pre-freeze evidence.
