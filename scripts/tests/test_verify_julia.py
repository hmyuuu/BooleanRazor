"""Fail-closed differential wrapper for the official Occam Julia verifier."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "verify-julia.sh"


def _write(path: Path, data: str, *, executable: bool = False) -> Path:
    path.write_text(data, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)
    return path


def _fixture(tmp_path: Path) -> list[str]:
    julia = _write(
        tmp_path / "julia",
        "#!/bin/sh\nprintf '%s' \"$FAKE_JULIA_OUTPUT\"\n",
        executable=True,
    )
    verifier = _write(tmp_path / "verify.jl", "# official fixture\n")
    circuit = _write(
        tmp_path / "mystery-A.txt",
        "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n",
    )
    dataset = _write(
        tmp_path / "completed-table.csv",
        "input,output\n00,0\n10,1\n",
    )
    return [
        str(SCRIPT),
        str(julia),
        str(verifier),
        str(circuit),
        str(dataset),
        "1",
        "mystery-A",
    ]


def _run_arguments(
    arguments: list[str], output: str, *, exit_code: int = 0
) -> subprocess.CompletedProcess[str]:
    julia = Path(arguments[1])
    julia.write_text(
        "#!/bin/sh\nprintf '%s' \"$FAKE_JULIA_OUTPUT\"\nexit \"$FAKE_JULIA_EXIT\"\n",
        encoding="utf-8",
        newline="\n",
    )
    julia.chmod(0o755)
    env = os.environ | {
        "FAKE_JULIA_OUTPUT": output,
        "FAKE_JULIA_EXIT": str(exit_code),
    }
    return subprocess.run(
        arguments,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _run(tmp_path: Path, output: str, *, exit_code: int = 0) -> subprocess.CompletedProcess[str]:
    return _run_arguments(_fixture(tmp_path), output, exit_code=exit_code)


def test_exact_official_output_emits_one_canonical_summary(tmp_path: Path) -> None:
    output = (
        "gates:            1  (inverters free)\n"
        "samples:          2\n"
        "exact-match acc:  1.0\n"
        "bit accuracy:     1.0\n"
    )
    assert SCRIPT.is_file(), "scripts/verify-julia.sh is missing"
    result = _run(tmp_path, output)

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "instance=mystery-A gates=1 samples=2 "
        "exact=1.0 bit=1.0 verifier=pass\n"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gates", "2"),
        ("samples", "3"),
        ("exact-match acc", "0.5"),
        ("bit accuracy", "0.5"),
    ],
)
def test_any_official_metric_mismatch_fails_without_summary(
    tmp_path: Path, field: str, value: str
) -> None:
    values = {
        "gates": "1  (inverters free)",
        "samples": "2",
        "exact-match acc": "1.0",
        "bit accuracy": "1.0",
    }
    values[field] = value
    output = (
        f"gates:            {values['gates']}\n"
        f"samples:          {values['samples']}\n"
        f"exact-match acc:  {values['exact-match acc']}\n"
        f"bit accuracy:     {values['bit accuracy']}\n"
    )

    result = _run(tmp_path, output)

    assert result.returncode != 0
    assert result.stdout == ""


def test_extra_or_duplicate_output_line_is_rejected(tmp_path: Path) -> None:
    output = (
        "gates:            1  (inverters free)\n"
        "samples:          2\n"
        "exact-match acc:  1.0\n"
        "bit accuracy:     1.0\n"
        "unexpected:       pass\n"
    )

    result = _run(tmp_path, output)

    assert result.returncode != 0
    assert result.stdout == ""


def test_nonzero_julia_exit_is_rejected_without_summary(tmp_path: Path) -> None:
    output = (
        "gates:            1  (inverters free)\n"
        "samples:          2\n"
        "exact-match acc:  1.0\n"
        "bit accuracy:     1.0\n"
    )

    result = _run(tmp_path, output, exit_code=7)

    assert result.returncode != 0
    assert result.stdout == ""


def test_unsafe_instance_label_is_rejected(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    arguments[-1] = "mystery-A\nverifier=pass"
    output = (
        "gates:            1  (inverters free)\n"
        "samples:          2\n"
        "exact-match acc:  1.0\n"
        "bit accuracy:     1.0\n"
    )

    result = _run_arguments(arguments, output)

    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize("path_index", [2, 3, 4])
def test_missing_or_symlinked_input_is_rejected_before_julia(
    tmp_path: Path, path_index: int
) -> None:
    arguments = _fixture(tmp_path)
    original = Path(arguments[path_index])
    original.unlink()
    target = _write(tmp_path / f"target-{path_index}", "fixture\n")
    original.symlink_to(target)
    marker = tmp_path / "julia-invoked"
    julia = Path(arguments[1])
    julia.write_text(
        "#!/bin/sh\n: > \"$FAKE_JULIA_MARKER\"\nexit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    julia.chmod(0o755)
    env = os.environ | {"FAKE_JULIA_MARKER": str(marker)}

    result = subprocess.run(
        arguments,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert not marker.exists()


@pytest.mark.parametrize(
    "dataset",
    [
        "wrong,header\n00,0\n",
        "input,output\n",
        "input,output\r\n00,0\r\n",
    ],
)
def test_noncanonical_or_empty_dataset_is_rejected_before_julia(
    tmp_path: Path, dataset: str
) -> None:
    arguments = _fixture(tmp_path)
    Path(arguments[4]).write_bytes(dataset.encode())
    marker = tmp_path / "julia-invoked"
    julia = Path(arguments[1])
    julia.write_text(
        "#!/bin/sh\n: > \"$FAKE_JULIA_MARKER\"\nexit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    julia.chmod(0o755)
    env = os.environ | {"FAKE_JULIA_MARKER": str(marker)}

    result = subprocess.run(
        arguments,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert not marker.exists()
