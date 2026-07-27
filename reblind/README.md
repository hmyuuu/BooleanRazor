# Reblinded benchmark boundary

This directory is the public, committed boundary between an independent
custodian and proposal worktrees. The commitment and nonidentifying 180-row
manifest are now frozen; no public training bundle is mounted in this
worktree, and no private benchmark or evaluator material is stored here.

## Publication record

- Commitment: `f2af9d3df949c6d07cfb80d209bc18040068fc1b2b5b3b36ec9743d7cfedc315`
- Public manifest: 180 instances, 22,438 bytes,
  SHA-256 `405ebeb9b83b92065d268360f763ecfefb8d0ea114556019b85ace958e6f9836`
- Canonical public archive: 23,570,730 bytes,
  SHA-256 `23e58e1f263052a290ad1321d7fccf45996224fc528a51a1b169cd97bf877d40`
- Frozen baseline matrix: 360 rows, 72,240 bytes,
  SHA-256 `cf3749189d84bb6aebf038e20c4af8397dcd9d8157cf201e21676004ab4ed569`

The custodian retained the canonical extracted public bundle and
`occam-reblind-public-f2af9d3df949c6d07cfb80d209bc18040068fc1b2b5b3b36ec9743d7cfedc315.tar.zst`
outside proposer worktrees. Byte-identical regeneration and archive-layout
audits passed before this publication.

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
