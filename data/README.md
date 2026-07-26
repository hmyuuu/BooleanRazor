# Occam's Circuit v1 data provenance

Download the audited release archive exactly from:

```text
https://github.com/QuantumBFS/quantum.harness/releases/download/occam-circuit-data-v1/occam-circuit.zip
```

The required SHA-256 digest is:

```text
c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b
```

To fetch, verify, and extract it outside this repository's tracked inputs:

```sh
curl -fL https://github.com/QuantumBFS/quantum.harness/releases/download/occam-circuit-data-v1/occam-circuit.zip -o /tmp/occam-circuit.zip
echo 'c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b  /tmp/occam-circuit.zip' | shasum -a 256 -c -
unzip -q /tmp/occam-circuit.zip -d /tmp/occam-circuit
```

Hidden labels are never committed as benchmark training input. Keep any revealed
or reconstructed hidden-test labels outside version-controlled training data.
