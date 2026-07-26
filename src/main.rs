use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use occam_circuit_hmyuuu::arithmetic::synthesize_family;
use occam_circuit_hmyuuu::bits::encode_lsb;
use occam_circuit_hmyuuu::instances::{
    InstanceSpec, MYSTERY_INSTANCES, complete_table, instance_by_slug,
};
use occam_circuit_hmyuuu::netlist::Netlist;
use occam_circuit_hmyuuu::order::{
    OrderScore, OrderScorer, beam_search_with_callback, search_csv_bytes, seed_orders,
};
#[cfg(feature = "oxidd-oracle")]
use occam_circuit_hmyuuu::oxidd_oracle::OxiddForest;
use occam_circuit_hmyuuu::table::{
    CompleteTable, InputTable, PartialTable, prediction_csv_bytes, row_index, sha256_hex,
};

const USAGE: &str = "usage:
  occam-circuit-hmyuuu solve-v1 DATA_ROOT OUTPUT_ROOT
  occam-circuit-hmyuuu search-order DATA_ROOT EXACT_SLUG --beam N --rounds N";

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
        _ => Err(USAGE.into()),
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
}
