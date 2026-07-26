use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use occam_circuit_hmyuuu::bits::encode_lsb;
use occam_circuit_hmyuuu::instances::{Family, MYSTERY_INSTANCES, semantic_output};
use occam_circuit_hmyuuu::netlist::Netlist;
use occam_circuit_hmyuuu::table::{
    CompleteTable, InputTable, PartialTable, prediction_csv_bytes, row_index, sha256_hex,
};

struct TempDir(PathBuf);

impl TempDir {
    fn new(label: &str) -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("occam-{label}-{}-{nonce}", std::process::id()));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn completed_table(spec: &occam_circuit_hmyuuu::instances::InstanceSpec) -> CompleteTable {
    let operand_bits = spec.input_bits / 2;
    let operand_mask = (1usize << operand_bits) - 1;
    CompleteTable::from_fn(spec.input_bits, spec.output_bits, |mask| {
        let x = (mask & operand_mask) as u64;
        let y = (mask >> operand_bits) as u64;
        semantic_output(spec.family, operand_bits, x, y) as usize
    })
}

fn run_solve(data_root: &Path, output_root: &Path) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .args(["solve-v1"])
        .arg(data_root)
        .arg(output_root)
        .output()
        .unwrap()
}

fn artifact_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
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

fn write_artifacts(root: &Path, bytes: &[u8]) {
    for relative in artifact_paths() {
        let path = root.join(relative);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, bytes).unwrap();
    }
}

fn assert_artifacts(root: &Path, bytes: &[u8]) {
    for relative in artifact_paths() {
        assert_eq!(
            fs::read(root.join(&relative)).unwrap(),
            bytes,
            "{} changed unexpectedly",
            relative.display()
        );
    }
}

fn copy_v1_datasets(source_root: &Path, destination_root: &Path) {
    for spec in &MYSTERY_INSTANCES {
        let source = source_root.join("datasets").join(spec.slug);
        let destination = destination_root.join("datasets").join(spec.slug);
        fs::create_dir_all(&destination).unwrap();
        for file in ["train.csv", "test_inputs.csv", "commitment.sha256"] {
            fs::copy(source.join(file), destination.join(file)).unwrap();
        }
    }
}

#[test]
fn v1_contract_is_exact_and_fixed() {
    let dims: Vec<_> = MYSTERY_INSTANCES
        .iter()
        .map(|s| (s.slug, s.input_bits, s.output_bits, s.family))
        .collect();
    assert_eq!(
        dims,
        vec![
            ("mystery-A", 16, 9, Family::Add),
            ("mystery-B", 14, 7, Family::AbsDiff),
            ("mystery-C", 12, 12, Family::Multiply),
            ("mystery-D", 10, 11, Family::SumSquares),
        ]
    );
    let commitments: Vec<_> = MYSTERY_INSTANCES.iter().map(|s| s.commitment).collect();
    assert_eq!(
        commitments,
        vec![
            "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
            "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
            "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
            "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
        ]
    );
    assert_eq!(semantic_output(Family::Add, 8, 255, 255), 510);
    assert_eq!(semantic_output(Family::AbsDiff, 7, 3, 90), 87);
    assert_eq!(semantic_output(Family::Multiply, 6, 63, 63), 3969);
    assert_eq!(semantic_output(Family::SumSquares, 5, 31, 31), 1922);
}

#[test]
fn official_v1_rows_commitments_and_circuits_are_exact() {
    let Some(data_root) = std::env::var_os("OCCAM_V1_ROOT").map(PathBuf::from) else {
        println!(
            "skipped official_v1_rows_commitments_and_circuits_are_exact: OCCAM_V1_ROOT unset"
        );
        return;
    };
    let output_root = TempDir::new("official-v1-output");
    let command = run_solve(&data_root, &output_root.0);
    assert!(
        command.status.success(),
        "solve-v1 failed:\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&command.stdout),
        String::from_utf8_lossy(&command.stderr)
    );

    for spec in &MYSTERY_INSTANCES {
        let dataset = data_root.join("datasets").join(spec.slug);
        let completed = completed_table(spec);
        let train_csv = fs::read_to_string(dataset.join("train.csv")).unwrap();
        let training = PartialTable::parse(&train_csv, spec.input_bits, spec.output_bits).unwrap();
        training.validate_against(&completed).unwrap();

        let test_csv = fs::read_to_string(dataset.join("test_inputs.csv")).unwrap();
        let test_inputs = InputTable::parse(&test_csv, spec.input_bits).unwrap();
        let prediction_bytes = prediction_csv_bytes(&test_inputs, &completed).unwrap();
        assert_eq!(
            sha256_hex(&prediction_bytes),
            spec.commitment,
            "{}",
            spec.slug
        );
        let emitted_predictions = fs::read(
            output_root
                .0
                .join("predictions")
                .join(spec.slug)
                .join("test_outputs.csv"),
        )
        .unwrap();
        assert_eq!(emitted_predictions, prediction_bytes, "{}", spec.slug);

        let circuit_text =
            fs::read_to_string(output_root.0.join(format!("{}.txt", spec.slug))).unwrap();
        let circuit = Netlist::parse(&circuit_text).unwrap();
        for (mask, semantic_bits) in completed.outputs.iter().enumerate() {
            let input = encode_lsb(mask as u64, spec.input_bits);
            assert_eq!(
                circuit.evaluate(&input).unwrap(),
                *semantic_bits,
                "{}",
                spec.slug
            );
        }
        for input in &test_inputs.rows {
            assert_eq!(
                circuit.evaluate(input).unwrap(),
                completed.outputs[row_index(input)],
                "{}",
                spec.slug
            );
        }
    }

    let corrupt_root = TempDir::new("invalid-v1-data");
    copy_v1_datasets(&data_root, &corrupt_root.0);
    let bad_train_path = corrupt_root
        .0
        .join("datasets")
        .join("mystery-D")
        .join("train.csv");
    let mut bad_train = fs::read_to_string(&bad_train_path).unwrap();
    let first_row = bad_train.find('\n').unwrap() + 1;
    let output_start = first_row + bad_train[first_row..].find(',').unwrap() + 1;
    let replacement = if bad_train.as_bytes()[output_start] == b'0' {
        "1"
    } else {
        "0"
    };
    bad_train.replace_range(output_start..output_start + 1, replacement);
    fs::write(bad_train_path, bad_train).unwrap();

    let output_root = TempDir::new("existing-v1-output");
    write_artifacts(&output_root.0, b"existing artifact\n");

    let command = run_solve(&corrupt_root.0, &output_root.0);
    assert!(
        !command.status.success(),
        "corrupt training data was accepted"
    );
    assert!(
        String::from_utf8_lossy(&command.stderr).contains("mystery-D training consistency"),
        "late corruption did not reach mystery-D validation:\n{}",
        String::from_utf8_lossy(&command.stderr)
    );
    for relative in artifact_paths() {
        assert_eq!(
            fs::read(output_root.0.join(&relative)).unwrap(),
            b"existing artifact\n",
            "{} changed despite a validation failure",
            relative.display()
        );
    }

    let directory_output = TempDir::new("directory-v1-output");
    write_artifacts(&directory_output.0, b"existing artifact\n");
    let directory_target = directory_output.0.join("mystery-A.txt");
    fs::remove_file(&directory_target).unwrap();
    fs::create_dir(&directory_target).unwrap();
    fs::write(directory_target.join("keep.txt"), b"do not delete\n").unwrap();

    let command = run_solve(&data_root, &directory_output.0);
    assert!(
        !command.status.success(),
        "an artifact destination directory was accepted"
    );
    assert_eq!(
        fs::read(directory_target.join("keep.txt")).unwrap(),
        b"do not delete\n"
    );
    for relative in artifact_paths()
        .into_iter()
        .filter(|path| path != Path::new("mystery-A.txt"))
    {
        assert_eq!(
            fs::read(directory_output.0.join(&relative)).unwrap(),
            b"existing artifact\n",
            "{} changed despite an invalid destination type",
            relative.display()
        );
    }

    let predictions_file_output = TempDir::new("predictions-file-output");
    for spec in &MYSTERY_INSTANCES {
        fs::write(
            predictions_file_output.0.join(format!("{}.txt", spec.slug)),
            b"existing circuit\n",
        )
        .unwrap();
    }
    fs::write(
        predictions_file_output.0.join("predictions"),
        b"not a directory\n",
    )
    .unwrap();
    let command = run_solve(&data_root, &predictions_file_output.0);
    assert!(
        !command.status.success(),
        "a regular-file predictions parent was accepted"
    );
    assert_eq!(
        fs::read(predictions_file_output.0.join("predictions")).unwrap(),
        b"not a directory\n"
    );
    for spec in &MYSTERY_INSTANCES {
        assert_eq!(
            fs::read(predictions_file_output.0.join(format!("{}.txt", spec.slug))).unwrap(),
            b"existing circuit\n"
        );
    }

    let instance_file_output = TempDir::new("instance-file-output");
    fs::create_dir(instance_file_output.0.join("predictions")).unwrap();
    fs::write(
        instance_file_output.0.join("predictions").join("mystery-B"),
        b"not an instance directory\n",
    )
    .unwrap();
    let command = run_solve(&data_root, &instance_file_output.0);
    assert!(
        !command.status.success(),
        "a regular-file instance parent was accepted"
    );
    assert_eq!(
        fs::read(instance_file_output.0.join("predictions").join("mystery-B")).unwrap(),
        b"not an instance directory\n"
    );
}

#[cfg(unix)]
#[test]
fn solve_v1_rejects_symlinks_inside_the_existing_output_tree() {
    use std::os::unix::fs::symlink;

    let Some(data_root) = std::env::var_os("OCCAM_V1_ROOT").map(PathBuf::from) else {
        println!(
            "skipped solve_v1_rejects_symlinks_inside_the_existing_output_tree: OCCAM_V1_ROOT unset"
        );
        return;
    };

    let root_case = TempDir::new("symlink-root");
    let outside_root = root_case.0.join("outside");
    fs::create_dir(&outside_root).unwrap();
    write_artifacts(&outside_root, b"outside root\n");
    let output_link = root_case.0.join("output-link");
    symlink(&outside_root, &output_link).unwrap();
    let command = run_solve(&data_root, &output_link);
    assert!(
        !command.status.success(),
        "a symlinked output root was accepted"
    );
    assert_artifacts(&outside_root, b"outside root\n");

    let predictions_case = TempDir::new("symlink-predictions");
    write_artifacts(&predictions_case.0, b"inside predictions\n");
    fs::remove_dir_all(predictions_case.0.join("predictions")).unwrap();
    let outside_predictions = TempDir::new("outside-predictions");
    for spec in &MYSTERY_INSTANCES {
        let path = outside_predictions
            .0
            .join(spec.slug)
            .join("test_outputs.csv");
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, b"outside predictions\n").unwrap();
    }
    symlink(
        &outside_predictions.0,
        predictions_case.0.join("predictions"),
    )
    .unwrap();
    let command = run_solve(&data_root, &predictions_case.0);
    assert!(
        !command.status.success(),
        "a symlinked predictions directory was accepted"
    );
    for spec in &MYSTERY_INSTANCES {
        assert_eq!(
            fs::read(
                outside_predictions
                    .0
                    .join(spec.slug)
                    .join("test_outputs.csv")
            )
            .unwrap(),
            b"outside predictions\n"
        );
    }

    let instance_case = TempDir::new("symlink-instance");
    write_artifacts(&instance_case.0, b"inside instance\n");
    fs::remove_dir_all(instance_case.0.join("predictions").join("mystery-C")).unwrap();
    let outside_instance = TempDir::new("outside-instance");
    fs::write(
        outside_instance.0.join("test_outputs.csv"),
        b"outside instance\n",
    )
    .unwrap();
    symlink(
        &outside_instance.0,
        instance_case.0.join("predictions").join("mystery-C"),
    )
    .unwrap();
    let command = run_solve(&data_root, &instance_case.0);
    assert!(
        !command.status.success(),
        "a symlinked instance directory was accepted"
    );
    assert_eq!(
        fs::read(outside_instance.0.join("test_outputs.csv")).unwrap(),
        b"outside instance\n"
    );

    let final_case = TempDir::new("symlink-final");
    write_artifacts(&final_case.0, b"inside final\n");
    let final_link = final_case.0.join("mystery-B.txt");
    fs::remove_file(&final_link).unwrap();
    let outside_final_root = TempDir::new("outside-final");
    let outside_final = outside_final_root.0.join("outside-final.txt");
    fs::write(&outside_final, b"outside final\n").unwrap();
    symlink(&outside_final, &final_link).unwrap();
    let command = run_solve(&data_root, &final_case.0);
    assert!(
        !command.status.success(),
        "a symlinked final artifact was accepted"
    );
    assert_eq!(fs::read(&outside_final).unwrap(), b"outside final\n");

    let dangling_case = TempDir::new("symlink-dangling");
    write_artifacts(&dangling_case.0, b"inside dangling\n");
    let dangling_link = dangling_case.0.join("mystery-D.txt");
    fs::remove_file(&dangling_link).unwrap();
    let dangling_target_root = TempDir::new("outside-dangling");
    let missing_target = dangling_target_root.0.join("missing-target.txt");
    symlink(&missing_target, &dangling_link).unwrap();
    let command = run_solve(&data_root, &dangling_case.0);
    assert!(
        !command.status.success(),
        "a dangling final symlink was accepted"
    );
    assert!(
        fs::symlink_metadata(&dangling_link)
            .unwrap()
            .file_type()
            .is_symlink()
    );
    assert!(!missing_target.exists());
}
