#!/usr/bin/env bash
set -euo pipefail

readonly archive_url="https://github.com/QuantumBFS/quantum.harness/releases/download/occam-circuit-data-v1/occam-circuit.zip"
readonly expected_sha256="c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b"
readonly script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly destination="${1:-${script_dir}/../data/occam-circuit}"
readonly destination_parent="$(dirname "${destination}")"
readonly digest_record="${destination}/.archive.sha256"

if [[ -e "${destination}" ]]; then
    if [[ -f "${digest_record}" ]] &&
        [[ "$(tr -d '[:space:]' <"${digest_record}")" == "${expected_sha256}" ]]; then
        printf 'occam-circuit v1 already verified at %s\n' "${destination}"
        exit 0
    fi
    printf 'error: refusing to overwrite unverified extraction at %s\n' "${destination}" >&2
    exit 1
fi

mkdir -p "${destination_parent}"
work_dir="$(mktemp -d "${destination_parent}/.occam-v1-fetch.XXXXXX")"
trap 'rm -rf "${work_dir}"' EXIT
archive_path="${work_dir}/occam-circuit.zip"

if [[ -n "${OCCAM_V1_ARCHIVE:-}" ]]; then
    cp "${OCCAM_V1_ARCHIVE}" "${archive_path}"
else
    curl --fail --location --silent --show-error \
        --output "${archive_path}" "${archive_url}"
fi

if command -v sha256sum >/dev/null 2>&1; then
    actual_sha256="$(sha256sum "${archive_path}" | awk '{print $1}')"
else
    actual_sha256="$(shasum -a 256 "${archive_path}" | awk '{print $1}')"
fi
if [[ "${actual_sha256}" != "${expected_sha256}" ]]; then
    printf 'error: archive SHA-256 mismatch: expected %s, got %s\n' \
        "${expected_sha256}" "${actual_sha256}" >&2
    exit 1
fi

mkdir "${work_dir}/unpacked"
unzip -q "${archive_path}" -d "${work_dir}/unpacked"
extracted="${work_dir}/unpacked/occam-circuit"
if [[ ! -d "${extracted}" ]]; then
    printf 'error: verified archive does not contain occam-circuit/\n' >&2
    exit 1
fi
printf '%s\n' "${expected_sha256}" >"${extracted}/.archive.sha256"
mv "${extracted}" "${destination}"
printf 'occam-circuit v1 fetched and verified at %s\n' "${destination}"
