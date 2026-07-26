use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use occam_circuit_hmyuuu::arithmetic::synthesize_family;
use occam_circuit_hmyuuu::bits::encode_lsb;
use occam_circuit_hmyuuu::instances::{InstanceSpec, MYSTERY_INSTANCES, semantic_output};
use occam_circuit_hmyuuu::netlist::Netlist;
use occam_circuit_hmyuuu::table::{
    CompleteTable, InputTable, PartialTable, prediction_csv_bytes, row_index, sha256_hex,
};

const USAGE: &str = "usage: occam-circuit-hmyuuu solve-v1 DATA_ROOT OUTPUT_ROOT";

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
    if arguments.len() != 3 || arguments[0] != "solve-v1" {
        return Err(USAGE.into());
    }
    solve_v1(Path::new(&arguments[1]), Path::new(&arguments[2]))
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

fn build_and_validate_candidate(
    data_root: &Path,
    spec: &'static InstanceSpec,
) -> Result<Candidate, String> {
    let dataset = data_root.join("datasets").join(spec.slug);
    let commitment_text = fs::read_to_string(dataset.join("commitment.sha256"))
        .map_err(|error| format!("{} commitment: {error}", spec.slug))?;
    if commitment_text.split_whitespace().next() != Some(spec.commitment) {
        return Err(format!(
            "{} archive commitment does not match the pinned contract",
            spec.slug
        ));
    }

    let operand_bits = spec.input_bits / 2;
    let operand_mask = (1usize << operand_bits) - 1;
    let completed = CompleteTable::from_fn(spec.input_bits, spec.output_bits, |mask| {
        let x = (mask & operand_mask) as u64;
        let y = (mask >> operand_bits) as u64;
        semantic_output(spec.family, operand_bits, x, y) as usize
    });

    let training_text = fs::read_to_string(dataset.join("train.csv"))
        .map_err(|error| format!("{} training data: {error}", spec.slug))?;
    let training = PartialTable::parse(&training_text, spec.input_bits, spec.output_bits)
        .map_err(|error| format!("{} training data: {error}", spec.slug))?;
    training
        .validate_against(&completed)
        .map_err(|error| format!("{} training consistency: {error}", spec.slug))?;

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

    let circuit = synthesize_family(spec.family, operand_bits, spec.output_bits)
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
        training_rows: training.rows.len(),
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

fn commit_staged_tree(stage: &Path, output_root: &Path) -> Result<(), String> {
    if !output_root.exists() {
        fs::rename(stage, output_root).map_err(|error| {
            format!(
                "atomically install output tree {}: {error}",
                output_root.display()
            )
        })?;
        return Ok(());
    }
    if !output_root.is_dir() {
        return Err(format!(
            "output root {} is not a directory",
            output_root.display()
        ));
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
        return Err(format!(
            "{error}; rollback also failed for {}",
            rollback_errors.join(", ")
        ));
    }

    fs::remove_dir_all(&backup)
        .map_err(|error| format!("remove completed backup {}: {error}", backup.display()))?;
    backup_cleanup.disarm();
    fs::remove_dir_all(stage)
        .map_err(|error| format!("remove completed stage {}: {error}", stage.display()))?;
    Ok(())
}
