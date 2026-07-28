use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

use occam_circuit_hmyuuu::reblind::PublicSuite;

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
    assert!(String::from_utf8_lossy(&output.stderr).contains("train.csv digest"));
    assert!(!output_dir.exists());
}
