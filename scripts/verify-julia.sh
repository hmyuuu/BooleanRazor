#!/bin/sh
set -eu
LC_ALL=C
export LC_ALL

fail() {
  printf 'error: %s\n' "$1" >&2
  exit 65
}

if [ "$#" -ne 6 ]; then
  printf '%s\n' \
    "usage: verify-julia.sh JULIA_BIN VERIFY_JL CIRCUIT DATASET EXPECTED_GATES INSTANCE" >&2
  exit 64
fi

julia_bin=$1
verifier=$2
circuit=$3
dataset=$4
expected_gates=$5
instance=$6

case "$expected_gates" in
  ""|*[!0-9]*)
    fail "EXPECTED_GATES must be a canonical non-negative integer"
    ;;
esac
case "$expected_gates" in
  0|[1-9]*)
    ;;
  *)
    fail "EXPECTED_GATES must not contain leading zeroes"
    ;;
esac

case "$instance" in
  ""|*[!A-Za-z0-9._-]*)
    fail "INSTANCE contains unsafe characters"
    ;;
esac
case "$instance" in
  [A-Za-z0-9]*)
    ;;
  *)
    fail "INSTANCE must start with an alphanumeric character"
    ;;
esac

[ -x "$julia_bin" ] || fail "JULIA_BIN is not executable"
for input in "$verifier" "$circuit" "$dataset"; do
  [ -f "$input" ] || fail "required input is not a regular file: $input"
  [ ! -L "$input" ] || fail "symlinked evidence input is not allowed: $input"
done

if grep -q "$(printf '\r')" "$dataset"; then
  fail "DATASET must use canonical LF line endings"
fi

header=$(sed -n '1p' "$dataset")
[ "$header" = "input,output" ] || fail "DATASET header must be input,output"

expected_samples=$(
  awk -F, '
    NR == 1 { next }
    NF != 2 || $1 !~ /^[01]+$/ || $2 !~ /^[01]+$/ { exit 2 }
    { n++ }
    END {
      if (n == 0) exit 3
      print n
    }
  ' "$dataset"
) || fail "DATASET must contain at least one canonical binary input,output row"

scratch=$(mktemp -d "${TMPDIR:-/tmp}/occam-julia-verify.XXXXXX")
trap 'rm -rf "$scratch"' EXIT HUP INT TERM

"$julia_bin" --startup-file=no --history-file=no \
  "$verifier" "$circuit" "$dataset" >"$scratch/stdout"

line_count=$(wc -l <"$scratch/stdout" | tr -d '[:space:]')
[ "$line_count" = "4" ]

gates=$(sed -n 's/^gates:[[:space:]]*\([0-9][0-9]*\)[[:space:]]*(inverters free)$/\1/p' "$scratch/stdout")
samples=$(sed -n 's/^samples:[[:space:]]*\([0-9][0-9]*\)$/\1/p' "$scratch/stdout")
exact=$(sed -n 's/^exact-match acc:[[:space:]]*\([0-9][0-9.]*\)$/\1/p' "$scratch/stdout")
bit=$(sed -n 's/^bit accuracy:[[:space:]]*\([0-9][0-9.]*\)$/\1/p' "$scratch/stdout")

[ "$gates" = "$expected_gates" ]
[ "$samples" = "$expected_samples" ]
[ "$exact" = "1.0" ]
[ "$bit" = "1.0" ]

printf 'instance=%s gates=%s samples=%s exact=1.0 bit=1.0 verifier=pass\n' \
  "$instance" "$gates" "$samples"
