#![cfg(feature = "sat")]

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};

use occam_circuit_hmyuuu::netlist::Netlist;
use occam_circuit_hmyuuu::sat::{SatResult, synthesize_xag_at_most};
use occam_circuit_hmyuuu::table::CompleteTable;

static NEXT_TEMP: AtomicU64 = AtomicU64::new(0);

struct TempDir(PathBuf);

impl TempDir {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "occam-sat-test-{}-{}",
            std::process::id(),
            NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn run_resynthesize(input: &Path, output: &Path, max_inputs: &str, seconds: &str) -> Output {
    Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .args([
            "resynthesize",
            input.to_str().unwrap(),
            output.to_str().unwrap(),
            "--max-cut-inputs",
            max_inputs,
            "--deadline-seconds",
            seconds,
            "--metrics-json",
        ])
        .arg(output.join("metrics.json"))
        .output()
        .unwrap()
}

#[test]
fn exact_synthesis_distinguishes_zero_and_one_gate_functions() {
    let xor = CompleteTable::from_fn(2, 1, |mask| (mask & 1) ^ ((mask >> 1) & 1));
    let deadline = Instant::now() + Duration::from_secs(5);
    assert!(matches!(
        synthesize_xag_at_most(&xor, 0, deadline).unwrap(),
        SatResult::Unsat
    ));
    let SatResult::Sat(circuit) = synthesize_xag_at_most(&xor, 1, deadline).unwrap() else {
        panic!("XOR must have a one-gate solution");
    };
    assert_eq!(circuit.reachable_gate_count().unwrap(), 1);
    assert_eq!(circuit.evaluate_all().unwrap(), xor.outputs);

    let zero = CompleteTable::from_fn(2, 1, |_| 0);
    let SatResult::Sat(zero_circuit) = synthesize_xag_at_most(&zero, 1, deadline).unwrap() else {
        panic!("at-most one gate must admit a zero-gate constant");
    };
    assert_eq!(zero_circuit.reachable_gate_count().unwrap(), 0);
}

#[test]
fn expired_deadline_returns_timeout_before_solver_work() {
    let xor = CompleteTable::from_fn(2, 1, |mask| (mask & 1) ^ ((mask >> 1) & 1));

    assert!(matches!(
        synthesize_xag_at_most(&xor, 8, Instant::now() - Duration::from_secs(1)).unwrap(),
        SatResult::Timeout
    ));
}

#[test]
fn multi_output_solution_shares_a_reachable_gate_and_uses_the_exact_lower_bound() {
    let table = CompleteTable::from_fn(3, 2, |mask| {
        let product = (mask & 1) & ((mask >> 1) & 1);
        product | ((product ^ ((mask >> 2) & 1)) << 1)
    });
    let deadline = Instant::now() + Duration::from_secs(5);

    assert!(matches!(
        synthesize_xag_at_most(&table, 1, deadline).unwrap(),
        SatResult::Unsat
    ));
    let SatResult::Sat(circuit) = synthesize_xag_at_most(&table, 2, deadline).unwrap() else {
        panic!("the shared two-output function must have an exact two-gate solution");
    };
    assert_eq!(circuit.reachable_gate_count().unwrap(), 2);
    assert_eq!(circuit.evaluate_all().unwrap(), table.outputs);
}

#[test]
fn synthesis_rejects_tables_beyond_the_frozen_six_input_cut_limit() {
    let table = CompleteTable::from_fn(7, 1, |mask| mask & 1);

    assert_eq!(
        synthesize_xag_at_most(&table, 0, Instant::now() + Duration::from_secs(5)).unwrap_err(),
        "SAT synthesis supports at most 6 inputs"
    );
}

#[test]
fn resynthesize_command_rewrites_a_synthetic_window_and_is_byte_deterministic() {
    let temporary = TempDir::new();
    let input = temporary.0.join("redundant-xor.txt");
    fs::write(
        &input,
        "INPUTS 2\nw1 = OR x1 x2\nw2 = AND x1 x2\nw3 = XOR w1 w2\nOUTPUTS w3\n",
    )
    .unwrap();
    let first = temporary.0.join("first");
    let second = temporary.0.join("second");

    let first_run = run_resynthesize(&input, &first, "6", "285");
    assert!(
        first_run.status.success(),
        "{}",
        String::from_utf8_lossy(&first_run.stderr)
    );
    let second_run = run_resynthesize(&input, &second, "6", "285");
    assert!(
        second_run.status.success(),
        "{}",
        String::from_utf8_lossy(&second_run.stderr)
    );

    for artifact in [
        "artifact.json",
        "circuit.txt",
        "completed-table.csv",
        "metrics.json",
        "sat-report.json",
    ] {
        assert_eq!(
            fs::read(first.join(artifact)).unwrap(),
            fs::read(second.join(artifact)).unwrap(),
            "{artifact} was not deterministic"
        );
    }
    let circuit_text = fs::read_to_string(first.join("circuit.txt")).unwrap();
    let circuit = Netlist::parse(&circuit_text).unwrap();
    assert_eq!(circuit.gate_count(), 1);
    assert_eq!(
        circuit.evaluate_all().unwrap(),
        Netlist::parse(&fs::read_to_string(input).unwrap())
            .unwrap()
            .evaluate_all()
            .unwrap()
    );
    let report = fs::read_to_string(first.join("sat-report.json")).unwrap();
    assert!(report.contains("\"cut_budget\":128"));
    assert!(report.contains("\"max_cut_inputs\":6"));
    assert!(report.contains("\"solver_call_budget\":64"));
    assert!(report.contains("\"sat_status\":\"sat\""));
    assert!(report.contains("\"whole_circuit_gate_delta\":-2"));
    assert!(report.contains("\"exhaustive_equivalence\":\"pass\""));
}

#[test]
fn resynthesize_command_rejects_every_resource_budget_override() {
    let temporary = TempDir::new();
    let input = temporary.0.join("xor.txt");
    fs::write(&input, "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n").unwrap();

    for (max_inputs, seconds, expected) in [
        ("5", "285", "--max-cut-inputs must equal the frozen value 6"),
        (
            "6",
            "284",
            "--deadline-seconds must equal the frozen value 285",
        ),
    ] {
        let output = temporary.0.join(format!("rejected-{max_inputs}-{seconds}"));
        let result = run_resynthesize(&input, &output, max_inputs, seconds);
        assert!(!result.status.success());
        assert!(
            String::from_utf8_lossy(&result.stderr).contains(expected),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert!(!output.exists());
    }
}

#[test]
fn resynthesize_command_finds_a_six_leaf_cut_inside_a_wider_circuit() {
    let temporary = TempDir::new();
    let input = temporary.0.join("wide-local-window.txt");
    fs::write(
        &input,
        "INPUTS 7\nw1 = OR x1 x2\nw2 = AND x1 x2\nw3 = XOR w1 w2\nw4 = XOR w3 x7\nOUTPUTS w4 x3 x4 x5 x6\n",
    )
    .unwrap();
    let output = temporary.0.join("output");

    let run = run_resynthesize(&input, &output, "6", "285");
    assert!(
        run.status.success(),
        "{}",
        String::from_utf8_lossy(&run.stderr)
    );
    let original = Netlist::parse(&fs::read_to_string(input).unwrap()).unwrap();
    let rewritten =
        Netlist::parse(&fs::read_to_string(output.join("circuit.txt")).unwrap()).unwrap();
    assert_eq!(
        rewritten.evaluate_all().unwrap(),
        original.evaluate_all().unwrap()
    );
    assert_eq!(rewritten.gate_count(), 2);
    let report = fs::read_to_string(output.join("sat-report.json")).unwrap();
    assert!(report.contains("\"whole_circuit_gate_delta\":-2"));
    assert!(report.contains("\"rewrites_accepted\":1"));
}

#[test]
fn resynthesize_command_preserves_an_unchecked_trace_for_unsat_encoding() {
    let temporary = TempDir::new();
    let input = temporary.0.join("minimal-xor.txt");
    fs::write(&input, "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n").unwrap();
    let output = temporary.0.join("output");

    let run = run_resynthesize(&input, &output, "6", "285");
    assert!(
        run.status.success(),
        "{}",
        String::from_utf8_lossy(&run.stderr)
    );
    let dimacs = fs::read(output.join("sat-instance.cnf")).unwrap();
    assert!(dimacs.starts_with(b"p cnf "));
    let proof = fs::read(output.join("sat-proof.drat")).unwrap();
    assert!(!proof.is_empty());
    let report = fs::read_to_string(output.join("sat-report.json")).unwrap();
    assert!(report.contains("\"proof_checked\":false"));
    assert!(!report.contains("\"proof_sha256\":null"));
    assert!(!report.contains("certificate"));
}

#[test]
fn resynthesize_command_compacts_dead_gates_before_metrics_and_output() {
    let temporary = TempDir::new();
    let input = temporary.0.join("dead-gate.txt");
    fs::write(
        &input,
        "INPUTS 2\nw1 = XOR x1 x2\nw2 = AND x1 x2\nOUTPUTS w1\n",
    )
    .unwrap();
    let output = temporary.0.join("output");

    let run = run_resynthesize(&input, &output, "6", "285");
    assert!(
        run.status.success(),
        "{}",
        String::from_utf8_lossy(&run.stderr)
    );
    let selected =
        Netlist::parse(&fs::read_to_string(output.join("circuit.txt")).unwrap()).unwrap();
    assert_eq!(selected.gate_count(), 1);
    let metrics = fs::read_to_string(output.join("metrics.json")).unwrap();
    assert!(metrics.contains("\"gates\":1"));
    assert!(metrics.contains("\"verifier\":\"not_run\""));
    assert!(!metrics.contains("\"verifier\":\"pass\""));
    let report = fs::read_to_string(output.join("sat-report.json")).unwrap();
    assert!(report.contains("\"whole_circuit_gate_delta\":0"));
}
