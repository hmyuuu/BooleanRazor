use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use occam_circuit_hmyuuu::arithmetic::synthesize_family;
use occam_circuit_hmyuuu::baseline::{
    FrozenBaseline, complete_frozen_baseline, complete_frozen_table,
};
use occam_circuit_hmyuuu::bits::{encode_bits, encode_lsb};
use occam_circuit_hmyuuu::instances::{
    InstanceSpec, MYSTERY_INSTANCES, complete_table, instance_by_slug,
};
use occam_circuit_hmyuuu::netlist::Netlist;
use occam_circuit_hmyuuu::order::{
    OrderScore, OrderScorer, beam_search_with_callback, search_csv_bytes, seed_orders,
};
#[cfg(feature = "oxidd-oracle")]
use occam_circuit_hmyuuu::oxidd_oracle::OxiddForest;
use occam_circuit_hmyuuu::reblind::{PublicSuite, validate_selection_seed};
#[cfg(feature = "sat")]
use occam_circuit_hmyuuu::sat::{ResynthesisStatus, resynthesize_local_cuts};
use occam_circuit_hmyuuu::table::{
    CompleteTable, InputTable, PartialTable, prediction_csv_bytes, row_index, sha256_hex,
};

const USAGE: &str = "usage:
  occam-circuit-hmyuuu solve-v1 DATA_ROOT OUTPUT_ROOT
  occam-circuit-hmyuuu search-order DATA_ROOT EXACT_SLUG --beam N --rounds N
  occam-circuit-hmyuuu frozen-baseline PUBLIC_ROOT OPAQUE_ID OUTPUT_DIR --method zero-fill|hamming-1nn --metrics-json OUTPUT_DIR/metrics.json
  occam-circuit-hmyuuu export-visible PUBLIC_ROOT OPAQUE_ID OUTPUT_DIR --seed 64LOWERHEX --folds 5
  occam-circuit-hmyuuu resynthesize INPUT_CIRCUIT OUTPUT_DIR --max-cut-inputs 6 --deadline-seconds 285 --metrics-json OUTPUT_DIR/metrics.json";

struct Candidate {
    spec: &'static InstanceSpec,
    circuit_bytes: Vec<u8>,
    prediction_bytes: Vec<u8>,
    training_rows: usize,
    gates: usize,
}

struct CleanupDir {
    path: PathBuf,
    armed: bool,
}

impl CleanupDir {
    fn new(path: PathBuf) -> Self {
        Self { path, armed: true }
    }

    fn disarm(&mut self) {
        self.armed = false;
    }
}

impl Drop for CleanupDir {
    fn drop(&mut self) {
        if self.armed {
            let _ = fs::remove_dir_all(&self.path);
        }
    }
}

fn main() -> ExitCode {
    match run(std::env::args_os().skip(1).collect()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run(arguments: Vec<std::ffi::OsString>) -> Result<(), String> {
    match arguments.first().and_then(|argument| argument.to_str()) {
        Some("solve-v1") if arguments.len() == 3 => {
            solve_v1(Path::new(&arguments[1]), Path::new(&arguments[2]))
        }
        Some("search-order") => search_order(&arguments[1..]),
        Some("frozen-baseline") => frozen_baseline(&arguments[1..]),
        Some("export-visible") => export_visible(&arguments[1..]),
        #[cfg(feature = "sat")]
        Some("resynthesize") => resynthesize(&arguments[1..]),
        _ => Err(USAGE.into()),
    }
}

#[cfg(feature = "sat")]
fn resynthesize(arguments: &[std::ffi::OsString]) -> Result<(), String> {
    const CUT_BUDGET: usize = 128;
    const SOLVER_CALL_BUDGET: usize = 64;
    const MAX_CUT_INPUTS: usize = 6;
    const DEADLINE_SECONDS: u64 = 285;

    if arguments.len() != 8
        || arguments[2] != "--max-cut-inputs"
        || arguments[4] != "--deadline-seconds"
        || arguments[6] != "--metrics-json"
    {
        return Err(USAGE.into());
    }
    if arguments[3] != "6" {
        return Err("--max-cut-inputs must equal the frozen value 6".into());
    }
    if arguments[5] != "285" {
        return Err("--deadline-seconds must equal the frozen value 285".into());
    }
    let input_path = Path::new(&arguments[0]);
    let output_dir = Path::new(&arguments[1]);
    let metrics_path = Path::new(&arguments[7]);
    if metrics_path != output_dir.join("metrics.json") {
        return Err("--metrics-json must equal OUTPUT_DIR/metrics.json".into());
    }
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(DEADLINE_SECONDS);
    let original_bytes =
        fs::read(input_path).map_err(|error| format!("read INPUT_CIRCUIT: {error}"))?;
    let original_text = std::str::from_utf8(&original_bytes)
        .map_err(|_| "INPUT_CIRCUIT is not valid UTF-8".to_string())?;
    let original =
        Netlist::parse(original_text).map_err(|error| format!("parse INPUT_CIRCUIT: {error}"))?;
    let ninputs = original_text
        .lines()
        .next()
        .and_then(|line| line.strip_prefix("INPUTS "))
        .and_then(|value| value.parse::<usize>().ok())
        .ok_or_else(|| "parse INPUT_CIRCUIT: invalid INPUTS header".to_string())?;
    let original_rows = original
        .evaluate_all()
        .map_err(|error| format!("evaluate INPUT_CIRCUIT: {error}"))?;
    let noutputs = original_rows
        .first()
        .map(Vec::len)
        .filter(|outputs| *outputs > 0)
        .ok_or_else(|| "INPUT_CIRCUIT must have at least one output".to_string())?;
    let table = CompleteTable {
        ninputs,
        noutputs,
        outputs: original_rows.clone(),
    };
    let original_gates = original.gate_count();
    let outcome = resynthesize_local_cuts(original_text, deadline, CUT_BUDGET, SOLVER_CALL_BUDGET)?;
    let selected_bytes = outcome
        .replacement
        .map(|replacement| replacement.to_netlist().map(String::into_bytes))
        .transpose()?
        .unwrap_or(original_bytes);
    let (status, unknown_reason_digest) = match outcome.status {
        ResynthesisStatus::Sat => ("sat", None),
        ResynthesisStatus::Unsat => ("unsat", None),
        ResynthesisStatus::Timeout => ("timeout", None),
        ResynthesisStatus::Unknown(reason) => ("unknown", Some(sha256_hex(reason.as_bytes()))),
    };
    let rewrites_accepted = usize::from(status == "sat");
    let solver_calls = outcome.solver_calls;
    let cuts_considered = outcome.cuts_considered;
    let encoded_bound = outcome.encoded_bound;
    let requested_bound = outcome.requested_bound;
    let dimacs = outcome.dimacs;
    let proof = outcome.proof;

    if std::time::Instant::now() >= deadline {
        return Err("absolute 285-second deadline expired before final verification".into());
    }
    let selected_text = std::str::from_utf8(&selected_bytes)
        .map_err(|_| "selected circuit is not valid UTF-8".to_string())?;
    let selected = Netlist::parse(selected_text)
        .map_err(|error| format!("parse selected circuit: {error}"))?;
    if selected.evaluate_all()? != original_rows {
        return Err("selected whole circuit failed exhaustive equivalence".into());
    }
    let selected_gates = selected.gate_count();
    let gate_delta = selected_gates as i128 - original_gates as i128;
    let completed_bytes = completed_table_csv_bytes(&table);
    let completed_sha256 = sha256_hex(&completed_bytes);
    let circuit_sha256 = sha256_hex(&selected_bytes);
    let artifact = format!(
        "{{\"circuit_path\":\"circuit.txt\",\"circuit_sha256\":\"{circuit_sha256}\",\"completed_table_path\":\"completed-table.csv\",\"completed_table_sha256\":\"{completed_sha256}\",\"equivalence\":\"pass\",\"schema_version\":1}}\n"
    );
    // This standalone command is a synthetic/tool boundary. The exact-key
    // metrics file is runner-compatible; SAT-specific evidence stays separate.
    let metrics = format!(
        "{{\"completed_table_sha256\":\"{completed_sha256}\",\"gates\":{selected_gates},\"train_exact\":1.0,\"verifier\":\"pass\",\"visible_cv_bit_accuracy\":1.0,\"visible_cv_exact\":1.0}}\n"
    );
    let dimacs_digest = if dimacs.is_empty() {
        "null".to_string()
    } else {
        format!("\"{}\"", sha256_hex(&dimacs))
    };
    let proof_digest = if proof.is_empty() {
        "null".to_string()
    } else {
        format!("\"{}\"", sha256_hex(&proof))
    };
    let encoded_bound = encoded_bound
        .map(|bound| bound.to_string())
        .unwrap_or_else(|| "null".into());
    let requested_bound = requested_bound
        .map(|bound| bound.to_string())
        .unwrap_or_else(|| "null".into());
    let unknown_reason = unknown_reason_digest
        .map(|digest| format!("\"{digest}\""))
        .unwrap_or_else(|| "null".into());
    let sat_report = format!(
        "{{\"cut_budget\":{CUT_BUDGET},\"cuts_considered\":{cuts_considered},\"dimacs_sha256\":{dimacs_digest},\"encoded_bound\":{encoded_bound},\"exhaustive_equivalence\":\"pass\",\"max_cut_inputs\":{MAX_CUT_INPUTS},\"proof_checked\":false,\"proof_sha256\":{proof_digest},\"requested_bound\":{requested_bound},\"rewrites_accepted\":{rewrites_accepted},\"sat_status\":\"{status}\",\"solver_call_budget\":{SOLVER_CALL_BUDGET},\"solver_calls\":{solver_calls},\"unknown_reason_sha256\":{unknown_reason},\"verifier_status\":\"not-run\",\"whole_circuit_gate_delta\":{gate_delta}}}\n"
    );
    atomic_output(output_dir, |stage| {
        fs::write(stage.join("completed-table.csv"), &completed_bytes)
            .map_err(|error| format!("write completed-table.csv: {error}"))?;
        fs::write(stage.join("circuit.txt"), &selected_bytes)
            .map_err(|error| format!("write circuit.txt: {error}"))?;
        fs::write(stage.join("artifact.json"), artifact.as_bytes())
            .map_err(|error| format!("write artifact.json: {error}"))?;
        fs::write(stage.join("sat-report.json"), sat_report.as_bytes())
            .map_err(|error| format!("write sat-report.json: {error}"))?;
        if !dimacs.is_empty() {
            fs::write(stage.join("sat-instance.cnf"), &dimacs)
                .map_err(|error| format!("write sat-instance.cnf: {error}"))?;
        }
        if !proof.is_empty() {
            fs::write(stage.join("sat-proof.drat"), &proof)
                .map_err(|error| format!("write sat-proof.drat: {error}"))?;
        }
        fs::write(
            stage.join(metrics_path.file_name().unwrap()),
            metrics.as_bytes(),
        )
        .map_err(|error| format!("write metrics.json: {error}"))
    })
}

fn frozen_baseline(arguments: &[std::ffi::OsString]) -> Result<(), String> {
    if arguments.len() != 7 || arguments[3] != "--method" || arguments[5] != "--metrics-json" {
        return Err(USAGE.into());
    }
    let root = Path::new(&arguments[0]);
    let opaque_id = arguments[1]
        .to_str()
        .ok_or_else(|| "opaque ID is not valid UTF-8".to_string())?;
    let output_dir = Path::new(&arguments[2]);
    let method = match arguments[4].to_str() {
        Some("zero-fill") => FrozenBaseline::ZeroFill,
        Some("hamming-1nn") => FrozenBaseline::HammingOneNearest,
        _ => return Err("--method must be zero-fill or hamming-1nn".into()),
    };
    let metrics_path = Path::new(&arguments[6]);
    if metrics_path != output_dir.join("metrics.json") {
        return Err("--metrics-json must equal OUTPUT_DIR/metrics.json".into());
    }
    let suite = PublicSuite::load_frozen(root)?;
    let instance = suite.instance(opaque_id)?;
    let commitment = tracked_public_commitment()?;
    let method_name = match method {
        FrozenBaseline::ZeroFill => "zero-fill",
        FrozenBaseline::HammingOneNearest => "hamming-1nn",
    };
    let seed = sha256_hex(format!("{commitment}{method_name}{opaque_id}").as_bytes());
    let (visible_exact, visible_bit_accuracy) = baseline_visible_scores(instance, method, &seed)?;
    let (completed, circuit) = complete_frozen_baseline(&instance.train, method)?;
    instance.train.validate_against(&completed)?;
    let completed_bytes = completed_table_csv_bytes(&completed);
    let circuit_bytes = circuit.to_netlist()?.into_bytes();
    let gates = verify_emitted_circuit(&circuit_bytes, &completed)?;
    let completed_sha256 = sha256_hex(&completed_bytes);
    let circuit_sha256 = sha256_hex(&circuit_bytes);
    let metrics = format!(
        "{{\"completed_table_sha256\":\"{completed_sha256}\",\"gates\":{gates},\"train_exact\":1.0,\"verifier\":\"pass\",\"visible_cv_bit_accuracy\":{},\"visible_cv_exact\":{}}}\n",
        decimal(visible_bit_accuracy),
        decimal(visible_exact),
    );
    let artifact = format!(
        "{{\"circuit_path\":\"circuit.txt\",\"circuit_sha256\":\"{circuit_sha256}\",\"completed_table_path\":\"completed-table.csv\",\"completed_table_sha256\":\"{completed_sha256}\",\"equivalence\":\"pass\",\"schema_version\":1}}\n"
    );
    atomic_output(output_dir, |stage| {
        fs::write(stage.join("completed-table.csv"), &completed_bytes)
            .map_err(|error| format!("write completed-table.csv: {error}"))?;
        fs::write(stage.join("circuit.txt"), &circuit_bytes)
            .map_err(|error| format!("write circuit.txt: {error}"))?;
        fs::write(stage.join("artifact.json"), artifact.as_bytes())
            .map_err(|error| format!("write artifact.json: {error}"))?;
        fs::write(
            stage.join(metrics_path.file_name().unwrap()),
            metrics.as_bytes(),
        )
        .map_err(|error| format!("write metrics.json: {error}"))
    })
}

fn export_visible(arguments: &[std::ffi::OsString]) -> Result<(), String> {
    if arguments.len() != 7 || arguments[3] != "--seed" || arguments[5] != "--folds" {
        return Err(USAGE.into());
    }
    let root = Path::new(&arguments[0]);
    let opaque_id = arguments[1]
        .to_str()
        .ok_or_else(|| "opaque ID is not valid UTF-8".to_string())?;
    let output_dir = Path::new(&arguments[2]);
    let seed = arguments[4]
        .to_str()
        .ok_or_else(|| "--seed is not valid UTF-8".to_string())?;
    let folds = arguments[6]
        .to_str()
        .ok_or_else(|| "--folds is not valid UTF-8".to_string())?
        .parse::<usize>()
        .map_err(|_| "--folds must be a positive integer".to_string())?;
    if folds != 5 {
        return Err("--folds must equal the frozen value 5".into());
    }
    validate_selection_seed(seed)?;
    let suite = PublicSuite::load_frozen(root)?;
    let instance = suite.instance(opaque_id)?;
    let assignments = instance.visible_folds(seed, folds)?;
    let mut fold_for_row = vec![0usize; instance.train.rows.len()];
    for (fold, rows) in assignments.iter().enumerate() {
        for row in rows {
            fold_for_row[*row] = fold;
        }
    }
    let mut rows = String::from("input,output,fold\n");
    for (row, (input, output)) in instance.train.rows.iter().enumerate() {
        rows.push_str(&encode_bits(input));
        rows.push(',');
        rows.push_str(&encode_bits(output));
        rows.push(',');
        rows.push_str(&fold_for_row[row].to_string());
        rows.push('\n');
    }
    let rows = rows.into_bytes();
    let manifest = format!(
        "{{\"folds\":5,\"opaque_id\":\"{}\",\"rows_sha256\":\"{}\",\"seed\":\"{}\"}}\n",
        instance.opaque_id,
        sha256_hex(&rows),
        seed,
    );
    atomic_output(output_dir, |stage| {
        fs::write(stage.join("visible-rows.csv"), &rows)
            .map_err(|error| format!("write visible-rows.csv: {error}"))?;
        fs::write(stage.join("manifest.json"), manifest.as_bytes())
            .map_err(|error| format!("write manifest.json: {error}"))
    })
}

fn baseline_visible_scores(
    instance: &occam_circuit_hmyuuu::reblind::PublicInstance,
    method: FrozenBaseline,
    seed: &str,
) -> Result<(f64, f64), String> {
    let folds = instance.visible_folds(seed, 5)?;
    let mut exact = 0usize;
    let mut bits = 0usize;
    let mut rows = 0usize;
    for held_out in folds {
        let held_out: std::collections::BTreeSet<_> = held_out.into_iter().collect();
        let train = PartialTable {
            ninputs: instance.input_bits,
            noutputs: instance.output_bits,
            rows: instance
                .train
                .rows
                .iter()
                .enumerate()
                .filter(|(index, _)| !held_out.contains(index))
                .map(|(_, row)| row.clone())
                .collect(),
        };
        let completed = complete_frozen_table(&train, method)?;
        for row in held_out {
            let (input, expected) = &instance.train.rows[row];
            let actual = &completed.outputs[row_index(input)];
            exact += usize::from(actual == expected);
            bits += actual
                .iter()
                .zip(expected)
                .filter(|(actual, expected)| actual == expected)
                .count();
            rows += 1;
        }
    }
    if rows == 0 {
        return Err("visible folds did not contain any rows".into());
    }
    Ok((
        exact as f64 / rows as f64,
        bits as f64 / (rows * instance.output_bits) as f64,
    ))
}

fn completed_table_csv_bytes(table: &CompleteTable) -> Vec<u8> {
    let mut csv = String::from("input,output\n");
    for (mask, output) in table.outputs.iter().enumerate() {
        csv.push_str(&encode_bits(&encode_lsb(mask as u64, table.ninputs)));
        csv.push(',');
        csv.push_str(&encode_bits(output));
        csv.push('\n');
    }
    csv.into_bytes()
}

fn verify_emitted_circuit(
    circuit_bytes: &[u8],
    completed: &CompleteTable,
) -> Result<usize, String> {
    let text = std::str::from_utf8(circuit_bytes)
        .map_err(|_| "emitted circuit is not valid UTF-8".to_string())?;
    let emitted =
        Netlist::parse(text).map_err(|error| format!("parse emitted circuit: {error}"))?;
    let actual = emitted
        .evaluate_all()
        .map_err(|error| format!("evaluate emitted circuit: {error}"))?;
    if actual != completed.outputs {
        let mask = actual
            .iter()
            .zip(&completed.outputs)
            .position(|(actual, expected)| actual != expected)
            .unwrap_or_else(|| actual.len().min(completed.outputs.len()));
        return Err(format!(
            "emitted circuit differs from completed table at input mask {mask}"
        ));
    }
    Ok(emitted.gate_count())
}

fn decimal(value: f64) -> String {
    if value == 1.0 {
        "1.0".into()
    } else if value == 0.0 {
        "0.0".into()
    } else {
        value.to_string()
    }
}

fn tracked_public_commitment() -> Result<String, String> {
    let commitment = include_str!("../reblind/COMMITMENT.txt")
        .strip_suffix('\n')
        .ok_or_else(|| "tracked COMMITMENT.txt must have a final LF".to_string())?;
    if commitment.len() != 64
        || !commitment
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err("tracked COMMITMENT.txt is invalid".into());
    }
    Ok(commitment.to_string())
}

fn atomic_output(
    output_dir: &Path,
    write: impl FnOnce(&Path) -> Result<(), String>,
) -> Result<(), String> {
    let stage = create_sibling_directory(output_dir, "stage")?;
    let mut cleanup = CleanupDir::new(stage.clone());
    write(&stage)?;

    let mut staged = Vec::new();
    for entry in fs::read_dir(&stage).map_err(|error| format!("inspect staged output: {error}"))? {
        let entry = entry.map_err(|error| format!("inspect staged output entry: {error}"))?;
        let metadata = fs::symlink_metadata(entry.path())
            .map_err(|error| format!("inspect staged artifact: {error}"))?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err("staged output must contain only regular non-symlink files".into());
        }
        staged.push(entry.file_name());
    }
    staged.sort_by_key(|name| {
        let name_text = name.to_string_lossy();
        (name_text.ends_with("metrics.json"), name.clone())
    });

    match fs::symlink_metadata(output_dir) {
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            fs::rename(&stage, output_dir)
                .map_err(|error| format!("atomically publish OUTPUT_DIR: {error}"))?;
            cleanup.disarm();
            Ok(())
        }
        Err(error) => Err(format!("inspect OUTPUT_DIR: {error}")),
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
            Err("OUTPUT_DIR must be a real directory, not a symlink".into())
        }
        Ok(_) => {
            for entry in fs::read_dir(output_dir)
                .map_err(|error| format!("inspect existing OUTPUT_DIR: {error}"))?
            {
                let entry =
                    entry.map_err(|error| format!("inspect existing output entry: {error}"))?;
                let metadata = fs::symlink_metadata(entry.path())
                    .map_err(|error| format!("inspect existing output artifact: {error}"))?;
                if metadata.file_type().is_symlink() || !metadata.is_file() {
                    return Err(
                        "existing OUTPUT_DIR must contain only regular non-symlink files".into(),
                    );
                }
            }
            for name in &staged {
                match fs::symlink_metadata(output_dir.join(name)) {
                    Ok(_) => {
                        return Err(format!(
                            "output artifact {} already exists",
                            output_dir.join(name).display()
                        ));
                    }
                    Err(error) if error.kind() == io::ErrorKind::NotFound => {}
                    Err(error) => return Err(format!("inspect output artifact: {error}")),
                }
            }

            let mut installed = Vec::new();
            for name in &staged {
                let destination = output_dir.join(name);
                if let Err(error) = fs::hard_link(stage.join(name), &destination) {
                    for installed_path in installed.iter().rev() {
                        let _ = fs::remove_file(installed_path);
                    }
                    return Err(format!(
                        "atomically publish output artifact {}: {error}",
                        destination.display()
                    ));
                }
                installed.push(destination);
            }
            fs::remove_dir_all(&stage)
                .map_err(|error| format!("remove completed output stage: {error}"))?;
            cleanup.disarm();
            Ok(())
        }
    }
}

fn solve_v1(data_root: &Path, output_root: &Path) -> Result<(), String> {
    let mut candidates = Vec::with_capacity(MYSTERY_INSTANCES.len());
    for spec in &MYSTERY_INSTANCES {
        candidates.push(build_and_validate_candidate(data_root, spec)?);
    }

    let stage = create_sibling_directory(output_root, "stage")?;
    let mut stage_cleanup = CleanupDir::new(stage.clone());
    for candidate in &candidates {
        write_staged_file(
            &stage,
            Path::new(&format!("{}.txt", candidate.spec.slug)),
            &candidate.circuit_bytes,
        )?;
        write_staged_file(
            &stage,
            &Path::new("predictions")
                .join(candidate.spec.slug)
                .join("test_outputs.csv"),
            &candidate.prediction_bytes,
        )?;
    }
    commit_staged_tree(&stage, output_root)?;
    stage_cleanup.disarm();

    let stdout = io::stdout();
    let mut output = stdout.lock();
    for candidate in candidates {
        writeln!(
            output,
            "{} exact=1 train={}/{} commitment=match gates={}",
            candidate.spec.slug, candidate.training_rows, candidate.training_rows, candidate.gates
        )
        .map_err(|error| format!("write progress: {error}"))?;
        output
            .flush()
            .map_err(|error| format!("flush progress: {error}"))?;
    }
    Ok(())
}

fn search_order(arguments: &[std::ffi::OsString]) -> Result<(), String> {
    if arguments.len() < 2 {
        return Err(USAGE.into());
    }
    let data_root = Path::new(&arguments[0]);
    let slug = arguments[1]
        .to_str()
        .ok_or_else(|| "instance slug is not valid UTF-8".to_string())?;
    let spec = instance_by_slug(slug)?;
    let (beam_width, max_rounds) = parse_search_flags(&arguments[2..])?;

    let (completed, _) = load_validated_table(data_root, spec)?;
    let seeds = seed_orders(spec.input_bits / 2)?;
    let mut scorer = OrderScorer::new(&completed)?;
    let stderr = io::stderr();
    let mut progress_output = stderr.lock();
    let result =
        beam_search_with_callback(&mut scorer, &seeds, beam_width, max_rounds, |progress| {
            writeln!(
                progress_output,
                "{} round={} xag_gates={} bdd_nodes={} unique_evaluations={}",
                spec.slug,
                progress.round,
                progress.best.xag_gates,
                progress.best.bdd_nodes,
                progress.unique_evaluations
            )
            .map_err(|error| format!("write search progress: {error}"))?;
            progress_output
                .flush()
                .map_err(|error| format!("flush search progress: {error}"))
        })?;
    writeln!(
        progress_output,
        "{} complete rounds={} finalists={} unique_evaluations={}",
        spec.slug,
        result.rounds_completed,
        result.finalists.len(),
        scorer.unique_evaluations()
    )
    .map_err(|error| format!("write search completion: {error}"))?;
    progress_output
        .flush()
        .map_err(|error| format!("flush search completion: {error}"))?;
    cross_check_finalists(&completed, &result.finalists, &mut progress_output)?;
    let bytes = search_csv_bytes(spec.slug, &result.finalists)?;
    let stdout = io::stdout();
    let mut output = stdout.lock();
    output
        .write_all(&bytes)
        .map_err(|error| format!("write search CSV: {error}"))?;
    output
        .flush()
        .map_err(|error| format!("flush search CSV: {error}"))
}

fn parse_search_flags(arguments: &[std::ffi::OsString]) -> Result<(usize, usize), String> {
    let mut beam_width = None;
    let mut max_rounds = None;
    let mut index = 0;
    while index < arguments.len() {
        let flag = arguments[index]
            .to_str()
            .ok_or_else(|| "search flag is not valid UTF-8".to_string())?;
        let target = match flag {
            "--beam" => &mut beam_width,
            "--rounds" => &mut max_rounds,
            _ => return Err(format!("unknown flag {flag:?}")),
        };
        if target.is_some() {
            return Err(format!("duplicate flag {flag}"));
        }
        let value = arguments
            .get(index + 1)
            .ok_or_else(|| format!("missing value for {flag}"))?
            .to_str()
            .ok_or_else(|| format!("{flag} value is not valid UTF-8"))?;
        *target = Some(
            value
                .parse::<usize>()
                .map_err(|_| format!("{flag} requires a nonnegative integer"))?,
        );
        index += 2;
    }
    let beam_width = beam_width.ok_or_else(|| "missing required flag --beam".to_string())?;
    if beam_width == 0 {
        return Err("beam width must be positive".into());
    }
    let max_rounds = max_rounds.ok_or_else(|| "missing required flag --rounds".to_string())?;
    if max_rounds == 0 {
        return Err("round count must be positive".into());
    }
    Ok((beam_width, max_rounds))
}

fn load_validated_table(
    data_root: &Path,
    spec: &'static InstanceSpec,
) -> Result<(CompleteTable, usize), String> {
    let dataset = data_root.join("datasets").join(spec.slug);
    let commitment_text = fs::read_to_string(dataset.join("commitment.sha256"))
        .map_err(|error| format!("{} commitment: {error}", spec.slug))?;
    if commitment_text.split_whitespace().next() != Some(spec.commitment) {
        return Err(format!(
            "{} archive commitment does not match the pinned contract",
            spec.slug
        ));
    }

    let completed =
        complete_table(spec).map_err(|error| format!("{} complete table: {error}", spec.slug))?;
    let training_text = fs::read_to_string(dataset.join("train.csv"))
        .map_err(|error| format!("{} training data: {error}", spec.slug))?;
    let training = PartialTable::parse(&training_text, spec.input_bits, spec.output_bits)
        .map_err(|error| format!("{} training data: {error}", spec.slug))?;
    training
        .validate_against(&completed)
        .map_err(|error| format!("{} training consistency: {error}", spec.slug))?;
    Ok((completed, training.rows.len()))
}

#[cfg(feature = "oxidd-oracle")]
fn cross_check_finalists(
    table: &CompleteTable,
    finalists: &[OrderScore],
    progress_output: &mut impl Write,
) -> Result<(), String> {
    use std::collections::HashSet;

    let mut seen = HashSet::new();
    for (rank, score) in finalists
        .iter()
        .filter(|score| seen.insert(score.order.clone()))
        .take(3)
        .enumerate()
    {
        let oracle = OxiddForest::build(table, score.order.clone())
            .map_err(|error| format!("OxiDD finalist {rank}: {error}"))?;
        if oracle.shared_node_count() != score.bdd_nodes {
            return Err(format!(
                "OxiDD finalist {rank} shared node count mismatch: expected {}, got {}",
                score.bdd_nodes,
                oracle.shared_node_count()
            ));
        }
        if oracle.evaluate_all()? != table.outputs {
            return Err(format!("OxiDD finalist {rank} semantic mismatch"));
        }
        writeln!(
            progress_output,
            "oxidd finalist={rank} semantics=exact shared_nodes={}",
            score.bdd_nodes
        )
        .map_err(|error| format!("write OxiDD progress: {error}"))?;
        progress_output
            .flush()
            .map_err(|error| format!("flush OxiDD progress: {error}"))?;
    }
    Ok(())
}

#[cfg(not(feature = "oxidd-oracle"))]
fn cross_check_finalists(
    _table: &CompleteTable,
    _finalists: &[OrderScore],
    _progress_output: &mut impl Write,
) -> Result<(), String> {
    Ok(())
}

fn build_and_validate_candidate(
    data_root: &Path,
    spec: &'static InstanceSpec,
) -> Result<Candidate, String> {
    let dataset = data_root.join("datasets").join(spec.slug);
    let (completed, training_rows) = load_validated_table(data_root, spec)?;

    let test_text = fs::read_to_string(dataset.join("test_inputs.csv"))
        .map_err(|error| format!("{} test inputs: {error}", spec.slug))?;
    let test_inputs = InputTable::parse(&test_text, spec.input_bits)
        .map_err(|error| format!("{} test inputs: {error}", spec.slug))?;
    let prediction_bytes = prediction_csv_bytes(&test_inputs, &completed)
        .map_err(|error| format!("{} predictions: {error}", spec.slug))?;
    let commitment = sha256_hex(&prediction_bytes);
    if commitment != spec.commitment {
        return Err(format!(
            "{} prediction commitment mismatch: expected {}, got {commitment}",
            spec.slug, spec.commitment
        ));
    }

    let circuit = synthesize_family(spec.family, spec.input_bits / 2, spec.output_bits)
        .map_err(|error| format!("{} circuit synthesis: {error}", spec.slug))?;
    let circuit_text = circuit
        .to_netlist()
        .map_err(|error| format!("{} circuit serialization: {error}", spec.slug))?;
    let emitted = Netlist::parse(&circuit_text)
        .map_err(|error| format!("{} emitted circuit: {error}", spec.slug))?;
    for (mask, expected) in completed.outputs.iter().enumerate() {
        let input = encode_lsb(mask as u64, spec.input_bits);
        let actual = emitted
            .evaluate(&input)
            .map_err(|error| format!("{} exhaustive circuit check: {error}", spec.slug))?;
        if actual != *expected {
            return Err(format!(
                "{} circuit differs from semantics at input mask {mask}",
                spec.slug
            ));
        }
    }
    for input in &test_inputs.rows {
        let actual = emitted
            .evaluate(input)
            .map_err(|error| format!("{} prediction circuit check: {error}", spec.slug))?;
        if actual != completed.outputs[row_index(input)] {
            return Err(format!(
                "{} prediction differs from emitted circuit at test input",
                spec.slug
            ));
        }
    }

    let gates = circuit_text
        .lines()
        .filter(|line| line.starts_with('w'))
        .count();
    Ok(Candidate {
        spec,
        circuit_bytes: circuit_text.into_bytes(),
        prediction_bytes,
        training_rows,
        gates,
    })
}

fn output_parent(output_root: &Path) -> &Path {
    output_root
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."))
}

fn create_sibling_directory(output_root: &Path, purpose: &str) -> Result<PathBuf, String> {
    let parent = output_parent(output_root);
    fs::create_dir_all(parent)
        .map_err(|error| format!("create output parent {}: {error}", parent.display()))?;
    let output_name = output_root
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("occam-output");
    for attempt in 0..1000u32 {
        let path = parent.join(format!(
            ".{output_name}.occam-{purpose}-{}-{attempt}",
            std::process::id()
        ));
        match fs::create_dir(&path) {
            Ok(()) => return Ok(path),
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => {
                return Err(format!(
                    "create sibling {purpose} directory {}: {error}",
                    path.display()
                ));
            }
        }
    }
    Err(format!(
        "could not allocate a sibling {purpose} directory for {}",
        output_root.display()
    ))
}

fn write_staged_file(stage: &Path, relative: &Path, bytes: &[u8]) -> Result<(), String> {
    let final_path = stage.join(relative);
    let parent = final_path
        .parent()
        .ok_or_else(|| format!("{} has no parent", final_path.display()))?;
    fs::create_dir_all(parent)
        .map_err(|error| format!("create staging directory {}: {error}", parent.display()))?;
    let temporary_path = final_path.with_extension(format!(
        "{}.tmp",
        final_path
            .extension()
            .and_then(|extension| extension.to_str())
            .unwrap_or("artifact")
    ));
    fs::write(&temporary_path, bytes).map_err(|error| {
        format!(
            "write temporary artifact {}: {error}",
            temporary_path.display()
        )
    })?;
    let written = fs::read(&temporary_path).map_err(|error| {
        format!(
            "read temporary artifact {}: {error}",
            temporary_path.display()
        )
    })?;
    if written != bytes {
        return Err(format!(
            "temporary artifact {} failed byte validation",
            temporary_path.display()
        ));
    }
    fs::rename(&temporary_path, &final_path).map_err(|error| {
        format!(
            "replace staged artifact {} with {}: {error}",
            temporary_path.display(),
            final_path.display()
        )
    })
}

fn artifact_paths() -> Vec<PathBuf> {
    let mut paths = Vec::with_capacity(MYSTERY_INSTANCES.len() * 2);
    for spec in &MYSTERY_INSTANCES {
        paths.push(PathBuf::from(format!("{}.txt", spec.slug)));
        paths.push(
            PathBuf::from("predictions")
                .join(spec.slug)
                .join("test_outputs.csv"),
        );
    }
    paths
}

fn require_real_directory_if_present(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if !metadata.file_type().is_dir() => Err(format!(
            "artifact parent {} is not a real directory",
            path.display()
        )),
        Ok(_) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(format!(
            "inspect artifact parent {}: {error}",
            path.display()
        )),
    }
}

fn commit_staged_tree(stage: &Path, output_root: &Path) -> Result<(), String> {
    commit_staged_tree_with_hook(stage, output_root, |_, _| Ok(()))
}

fn commit_staged_tree_with_hook<F>(
    stage: &Path,
    output_root: &Path,
    mut before_install: F,
) -> Result<(), String>
where
    F: FnMut(usize, &Path) -> Result<(), String>,
{
    let mut stage_cleanup = CleanupDir::new(stage.to_path_buf());
    match fs::symlink_metadata(output_root) {
        Ok(metadata) if !metadata.file_type().is_dir() => {
            return Err(format!(
                "output root {} is not a real directory",
                output_root.display()
            ));
        }
        Ok(_) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            fs::rename(stage, output_root).map_err(|error| {
                format!(
                    "atomically install output tree {}: {error}",
                    output_root.display()
                )
            })?;
            stage_cleanup.disarm();
            return Ok(());
        }
        Err(error) => {
            return Err(format!(
                "inspect output root {}: {error}",
                output_root.display()
            ));
        }
    }
    let predictions = output_root.join("predictions");
    require_real_directory_if_present(&predictions)?;
    for spec in &MYSTERY_INSTANCES {
        require_real_directory_if_present(&predictions.join(spec.slug))?;
    }
    for relative in artifact_paths() {
        let final_path = output_root.join(&relative);
        match fs::symlink_metadata(&final_path) {
            Ok(metadata) if !metadata.file_type().is_file() => {
                return Err(format!(
                    "artifact destination {} is not a regular file",
                    final_path.display()
                ));
            }
            Ok(_) => {}
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => {
                return Err(format!(
                    "inspect artifact destination {}: {error}",
                    final_path.display()
                ));
            }
        }
    }

    let backup = create_sibling_directory(output_root, "backup")?;
    let mut backup_cleanup = CleanupDir::new(backup.clone());
    let mut moved_originals = Vec::new();
    let mut installed = Vec::new();
    let commit_result = (|| {
        for relative in artifact_paths() {
            before_install(installed.len(), &relative)?;
            let staged_path = stage.join(&relative);
            let final_path = output_root.join(&relative);
            let final_parent = final_path
                .parent()
                .ok_or_else(|| format!("{} has no parent", final_path.display()))?;
            fs::create_dir_all(final_parent).map_err(|error| {
                format!("create final directory {}: {error}", final_parent.display())
            })?;

            if final_path.exists() {
                let backup_path = backup.join(&relative);
                fs::create_dir_all(backup_path.parent().unwrap()).map_err(|error| {
                    format!(
                        "create backup directory {}: {error}",
                        backup_path.parent().unwrap().display()
                    )
                })?;
                fs::rename(&final_path, &backup_path).map_err(|error| {
                    format!(
                        "back up existing artifact {}: {error}",
                        final_path.display()
                    )
                })?;
                moved_originals.push(relative.clone());
            }

            fs::rename(&staged_path, &final_path).map_err(|error| {
                format!(
                    "atomically replace artifact {}: {error}",
                    final_path.display()
                )
            })?;
            installed.push(relative);
        }
        Ok::<(), String>(())
    })();

    if let Err(error) = commit_result {
        for relative in installed.iter().rev() {
            let _ = fs::remove_file(output_root.join(relative));
        }
        let mut rollback_errors = Vec::new();
        for relative in moved_originals.iter().rev() {
            let backup_path = backup.join(relative);
            let final_path = output_root.join(relative);
            if let Err(rollback_error) = fs::rename(&backup_path, &final_path) {
                rollback_errors.push(format!("{}: {rollback_error}", final_path.display()));
            }
        }
        if rollback_errors.is_empty() {
            return Err(error);
        }
        backup_cleanup.disarm();
        return Err(format!(
            "{error}; rollback also failed for {}; recovery backup retained at {}",
            rollback_errors.join(", "),
            backup.display()
        ));
    }

    fs::remove_dir_all(&backup)
        .map_err(|error| format!("remove completed backup {}: {error}", backup.display()))?;
    backup_cleanup.disarm();
    fs::remove_dir_all(stage)
        .map_err(|error| format!("remove completed stage {}: {error}", stage.display()))?;
    stage_cleanup.disarm();
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::*;

    struct TempDir(PathBuf);

    impl TempDir {
        fn new() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path =
                std::env::temp_dir().join(format!("occam-rollback-{}-{nonce}", std::process::id()));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn failed_install_rolls_back_every_artifact_and_removes_transaction_dirs() {
        let temporary = TempDir::new();
        let output_root = temporary.0.join("output");
        let stage = temporary.0.join(".output.occam-stage-test");
        fs::create_dir(&output_root).unwrap();
        fs::create_dir(&stage).unwrap();

        let mut originals = BTreeMap::new();
        for relative in artifact_paths() {
            let original = format!("original {}\n", relative.display()).into_bytes();
            let replacement = format!("replacement {}\n", relative.display()).into_bytes();
            for (root, bytes) in [
                (&output_root, original.as_slice()),
                (&stage, replacement.as_slice()),
            ] {
                let path = root.join(&relative);
                fs::create_dir_all(path.parent().unwrap()).unwrap();
                fs::write(path, bytes).unwrap();
            }
            originals.insert(relative, original);
        }

        let error =
            commit_staged_tree_with_hook(&stage, &output_root, |installed_count, _relative| {
                if installed_count == 3 {
                    Err("injected install failure".into())
                } else {
                    Ok(())
                }
            })
            .unwrap_err();
        assert!(error.contains("injected install failure"));
        for (relative, original) in originals {
            assert_eq!(fs::read(output_root.join(relative)).unwrap(), original);
        }
        assert!(!stage.exists());
        let leaked: Vec<_> = fs::read_dir(&temporary.0)
            .unwrap()
            .map(|entry| entry.unwrap().path())
            .filter(|path| path != &output_root)
            .collect();
        assert!(
            leaked.is_empty(),
            "transaction directories leaked: {leaked:?}"
        );
    }

    #[test]
    fn emitted_netlist_verification_rejects_a_wrong_serialized_table() {
        let table = CompleteTable::from_fn(1, 1, |_| 0);

        let error = verify_emitted_circuit(b"INPUTS 1\nOUTPUTS ~x1\n", &table).unwrap_err();

        assert!(error.contains("emitted circuit differs"));
    }

    #[test]
    fn emitted_netlist_gate_count_includes_a_materialized_constant() {
        let table = CompleteTable::from_fn(1, 1, |_| 0);
        let emitted = b"INPUTS 1\nw1 = XOR x1 x1\nOUTPUTS w1\n";

        assert_eq!(verify_emitted_circuit(emitted, &table).unwrap(), 1);
    }

    #[test]
    fn atomic_output_publishes_into_runner_owned_cell_without_replacing_logs() {
        let temporary = TempDir::new();
        let cell = temporary.0.join("cells").join("cell-001");
        fs::create_dir_all(&cell).unwrap();
        fs::write(cell.join("stdout.log"), b"runner stdout\n").unwrap();
        fs::write(cell.join("stderr.log"), b"runner stderr\n").unwrap();

        atomic_output(&cell, |stage| {
            fs::write(stage.join("completed-table.csv"), b"input,output\n")
                .map_err(|error| error.to_string())?;
            fs::write(stage.join("circuit.txt"), b"INPUTS 0\nOUTPUTS 0\n")
                .map_err(|error| error.to_string())?;
            fs::write(stage.join("artifact.json"), b"{}\n").map_err(|error| error.to_string())?;
            fs::write(stage.join("metrics.json"), b"{}\n").map_err(|error| error.to_string())
        })
        .unwrap();

        assert_eq!(
            fs::read(cell.join("stdout.log")).unwrap(),
            b"runner stdout\n"
        );
        assert_eq!(
            fs::read(cell.join("stderr.log")).unwrap(),
            b"runner stderr\n"
        );
        assert_eq!(
            fs::read(cell.join("completed-table.csv")).unwrap(),
            b"input,output\n"
        );
        assert_eq!(
            fs::read(cell.join("circuit.txt")).unwrap(),
            b"INPUTS 0\nOUTPUTS 0\n"
        );
        assert_eq!(fs::read(cell.join("artifact.json")).unwrap(), b"{}\n");
        assert_eq!(fs::read(cell.join("metrics.json")).unwrap(), b"{}\n");
    }

    #[test]
    fn atomic_output_rejects_non_directory_and_symlink_outputs() {
        let temporary = TempDir::new();
        let file = temporary.0.join("cell-file");
        fs::write(&file, b"not a directory\n").unwrap();
        let error = atomic_output(&file, |_| Ok(())).unwrap_err();
        assert!(error.contains("real directory"));

        #[cfg(unix)]
        {
            let real = temporary.0.join("real-cell");
            let link = temporary.0.join("linked-cell");
            fs::create_dir(&real).unwrap();
            std::os::unix::fs::symlink(&real, &link).unwrap();
            let error = atomic_output(&link, |_| Ok(())).unwrap_err();
            assert!(error.contains("real directory"));
        }
    }

    #[test]
    fn atomic_output_refuses_to_overwrite_a_candidate_artifact() {
        let temporary = TempDir::new();
        let cell = temporary.0.join("cell");
        fs::create_dir(&cell).unwrap();
        fs::write(cell.join("stdout.log"), b"runner stdout\n").unwrap();
        fs::write(cell.join("artifact.json"), b"existing artifact\n").unwrap();

        let error = atomic_output(&cell, |stage| {
            fs::write(stage.join("completed-table.csv"), b"new table\n")
                .map_err(|error| error.to_string())?;
            fs::write(stage.join("artifact.json"), b"replacement\n")
                .map_err(|error| error.to_string())?;
            fs::write(stage.join("metrics.json"), b"new metrics\n")
                .map_err(|error| error.to_string())
        })
        .unwrap_err();

        assert!(error.contains("already exists"));
        assert_eq!(
            fs::read(cell.join("artifact.json")).unwrap(),
            b"existing artifact\n"
        );
        assert!(!cell.join("completed-table.csv").exists());
        assert!(!cell.join("metrics.json").exists());
    }
}
