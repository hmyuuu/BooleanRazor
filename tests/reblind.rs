use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

use occam_circuit_hmyuuu::reblind::PublicSuite;
use occam_circuit_hmyuuu::table::sha256_hex;

const CARE_METHOD: &str = "care-bdd-reuse-sibling";

struct TempRoot(PathBuf);

impl Drop for TempRoot {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn modified_frozen_bundle() -> (TempRoot, PathBuf) {
    static NEXT: AtomicUsize = AtomicUsize::new(0);
    let parent = std::env::temp_dir().join(format!(
        "occam-reblind-cli-test-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    let commitment = include_str!("../reblind/COMMITMENT.txt").trim();
    let root = parent.join(commitment);
    fs::create_dir_all(&root).unwrap();
    fs::write(
        root.join("manifest.csv"),
        include_bytes!("../reblind/manifest.csv"),
    )
    .unwrap();
    for line in include_str!("../reblind/manifest.csv").lines().skip(1) {
        let opaque_id = line.split(',').next().unwrap();
        let instance = root.join("instances").join(opaque_id);
        fs::create_dir_all(&instance).unwrap();
        fs::write(instance.join("train.csv"), b"input,output\nchanged\n").unwrap();
    }
    (TempRoot(parent), root)
}

fn frozen_care_seed(opaque_id: &str) -> String {
    let commitment = include_str!("../reblind/COMMITMENT.txt").trim();
    sha256_hex(format!("{commitment}{CARE_METHOD}{opaque_id}").as_bytes())
}

#[test]
fn frozen_loader_rejects_an_untrusted_root_before_reading_any_bundle() {
    let missing = Path::new("/definitely-not-an-occam-public-bundle");
    let error = PublicSuite::load_frozen(missing).unwrap_err();
    assert!(error.contains("OCCAM_REBLIND_PUBLIC_ROOT"));
}

#[test]
fn frozen_baseline_rejects_a_raw_training_csv_argument() {
    let output = Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .args([
            "frozen-baseline",
            "train.csv",
            "rb-000000000000000000000000",
            "out",
            "--method",
            "zero-fill",
            "--metrics-json",
            "out/metrics.json",
        ])
        .output()
        .unwrap();

    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("OCCAM_REBLIND_PUBLIC_ROOT"));
}

#[test]
fn learn_care_rejects_raw_paths_and_nonfrozen_flags_before_output() {
    let temporary = TempRoot(std::env::temp_dir().join(format!(
        "occam-learn-care-rejections-{}",
        std::process::id()
    )));
    let output_dir = temporary.0.join("output");
    let binary = env!("CARGO_BIN_EXE_occam-circuit-hmyuuu");
    let opaque_id = "rb-000000000000000000000000";
    let seed = frozen_care_seed(opaque_id);
    let base = [
        "learn-care",
        "train.csv",
        opaque_id,
        output_dir.to_str().unwrap(),
        "--folds",
        "5",
        "--seed",
        &seed,
        "--policy",
        "reuse-sibling",
        "--max-order-evals",
        "32",
    ];
    let raw = Command::new(binary).args(base).output().unwrap();
    assert!(!raw.status.success());
    assert!(String::from_utf8_lossy(&raw.stderr).contains("OCCAM_REBLIND_PUBLIC_ROOT"));
    assert!(!output_dir.exists());

    for (tail, expected) in [
        (vec!["--folds", "4"], "--folds must equal"),
        (vec!["--seed", "bad"], "64 lowercase hex"),
        (
            vec!["--seed", &"00".repeat(32)],
            "--seed must equal the frozen algorithm seed",
        ),
        (vec!["--policy", "guess"], "--policy must be"),
        (
            vec!["--policy", "zero"],
            "--policy must equal the frozen value reuse-sibling",
        ),
        (
            vec!["--max-order-evals", "0"],
            "--max-order-evals must be positive",
        ),
        (
            vec!["--max-order-evals", "31"],
            "--max-order-evals must equal the frozen value 32",
        ),
        (vec!["--input-bits", "12"], "unknown flag"),
        (vec!["--train-csv", "train.csv"], "unknown flag"),
    ] {
        let mut arguments = vec![
            "learn-care",
            "missing-public-root",
            opaque_id,
            output_dir.to_str().unwrap(),
            "--folds",
            "5",
            "--seed",
            &seed,
            "--policy",
            "reuse-sibling",
            "--max-order-evals",
            "32",
        ];
        let flag = tail[0];
        if let Some(position) = arguments.iter().position(|argument| *argument == flag) {
            arguments[position + 1] = tail[1];
        } else {
            arguments.extend(tail);
        }
        let result = Command::new(binary).args(arguments).output().unwrap();
        assert!(!result.status.success());
        assert!(
            String::from_utf8_lossy(&result.stderr).contains(expected),
            "stderr did not contain {expected:?}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert!(!output_dir.exists());
    }
}

#[test]
fn frozen_baseline_requires_the_fixed_metrics_artifact_name() {
    let output = Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .args([
            "frozen-baseline",
            "public-root",
            "rb-000000000000000000000000",
            "out",
            "--method",
            "zero-fill",
            "--metrics-json",
            "out/alternate.json",
        ])
        .output()
        .unwrap();

    assert!(!output.status.success());
    assert!(
        String::from_utf8_lossy(&output.stderr)
            .contains("--metrics-json must equal OUTPUT_DIR/metrics.json")
    );
}

#[test]
fn frozen_baseline_rejects_modified_training_bytes_before_creating_outputs() {
    let (_temporary_parent, root) = modified_frozen_bundle();
    let output_dir = root.parent().unwrap().join("output");
    let opaque_id = include_str!("../reblind/manifest.csv")
        .lines()
        .nth(1)
        .unwrap()
        .split(',')
        .next()
        .unwrap();

    let output = Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .env("OCCAM_REBLIND_PUBLIC_ROOT", &root)
        .args([
            "frozen-baseline",
            root.to_str().unwrap(),
            opaque_id,
            output_dir.to_str().unwrap(),
            "--method",
            "zero-fill",
            "--metrics-json",
            output_dir.join("metrics.json").to_str().unwrap(),
        ])
        .output()
        .unwrap();

    assert!(!output.status.success());
    assert!(
        String::from_utf8_lossy(&output.stderr)
            .contains("train.csv byte length does not match manifest")
    );
    assert!(!output_dir.exists());
}

#[test]
fn export_visible_rejects_nonfrozen_folds_and_malformed_seed_without_output() {
    let (temporary_parent, root) = modified_frozen_bundle();
    let parent = temporary_parent.0.as_path();
    let binary = env!("CARGO_BIN_EXE_occam-circuit-hmyuuu");
    let opaque_id = "rb-000000000000000000000000";

    let folds_output = parent.join("bad-folds");
    let result = Command::new(binary)
        .env_remove("OCCAM_REBLIND_PUBLIC_ROOT")
        .args([
            "export-visible",
            root.to_str().unwrap(),
            opaque_id,
            folds_output.to_str().unwrap(),
            "--seed",
            &"00".repeat(32),
            "--folds",
            "4",
        ])
        .output()
        .unwrap();
    assert!(!result.status.success());
    assert!(String::from_utf8_lossy(&result.stderr).contains("--folds must equal"));
    assert!(!folds_output.exists());

    let seed_output = parent.join("bad-seed");
    let result = Command::new(binary)
        .env_remove("OCCAM_REBLIND_PUBLIC_ROOT")
        .args([
            "export-visible",
            root.to_str().unwrap(),
            opaque_id,
            seed_output.to_str().unwrap(),
            "--seed",
            "not-a-64-hex-seed",
            "--folds",
            "5",
        ])
        .output()
        .unwrap();
    assert!(!result.status.success());
    assert!(String::from_utf8_lossy(&result.stderr).contains("64 lowercase hex"));
    assert!(!seed_output.exists());
}

#[test]
fn export_visible_rejects_an_output_override_argument() {
    let (temporary_parent, root) = modified_frozen_bundle();
    let output_dir = temporary_parent.0.join("output");
    let result = Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .env_remove("OCCAM_REBLIND_PUBLIC_ROOT")
        .args([
            "export-visible",
            root.to_str().unwrap(),
            "rb-000000000000000000000000",
            output_dir.to_str().unwrap(),
            "--seed",
            &"00".repeat(32),
            "--folds",
            "5",
            "--output",
            "alternate.csv",
        ])
        .output()
        .unwrap();

    assert!(!result.status.success());
    assert!(String::from_utf8_lossy(&result.stderr).contains("usage:"));
    assert!(!output_dir.exists());
}
