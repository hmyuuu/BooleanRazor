# Claim language

Use the narrowest phrase supported by the evidence. Copy the following phrases
verbatim when the corresponding state applies:

```text
disclosed control: verified constructive upper bound; not blind; not minimality
synthetic: internal/synthetic evidence; may advance to public candidate
blind visible: visible-only frozen candidate; no sealed-performance claim
sealed confirmation: promoted blind result only after positive sealed decision
blocked: required evidence is absent or unavailable
not demonstrated: claim-grade evaluation has not occurred
```

## Verification distinctions

Use these statements without collapsing their layers:

- `Internal exhaustive Rust equivalence passed for the emitted completed table
  and XAG; official Julia verification is separate.`
- `Official Julia verification was not run.` for `verifier=not_run`.
- `Official Julia verification failed.` for `verifier=fail`.
- `The historical official-Julia evidence applies only to the disclosed v1
  controls and its recorded branch revision.`
- `The public baseline rows are absent.` when `research/BASELINES.csv` has no
  executed rows.
- `Blind advantage has not been demonstrated.` until claim-grade public and
  sealed evaluation has occurred.

Do not call internal equivalence an official pass. Do not call
`VERIFIER_NOT_RUN` a successful runner result. Do not describe a wrapper test
as a candidate verification.

## Decision wording

| Decision | Permitted wording |
| --- | --- |
| `blocked` | Required proof is absent; the claim remains unestablished |
| `reject` | The supplied evidence violated the named eligibility or binding gate |
| `no_change` | The candidate was valid but did not strictly improve exact-row accuracy, then reachable XAG gates |
| `promote_control` | The disclosed control is a verified constructive upper bound |
| `advance_public_candidate` | The synthetic method may advance to separate public-candidate consideration |
| `freeze_candidate` | The visible-only candidate is frozen for separate sealed confirmation |
| `promote_blind_result` | The blind result is promoted under the positive sealed decision |

`blocked` is not a failed experiment, and `not demonstrated` is not evidence
of no effect. Preserve that distinction.

## Forbidden upgrades

Do not claim:

- minimality from a constructive gate count;
- blind recovery from A–D;
- generalization from a fully observed synthetic fixture;
- public or sealed performance from branch-only synthetic evidence;
- SOTA, `100x`, or scaling advantage without the matching positive sealed
  decision and frozen comparison;
- a family identity, generator, or per-example sealed failure;
- current-revision verification from historical branch evidence.

If a requested sentence exceeds the evidence level, replace it with the
permitted phrase and name the missing gate.
