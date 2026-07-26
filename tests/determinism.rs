use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use occam_circuit_hmyuuu::instances::MYSTERY_INSTANCES;

struct TempDir(PathBuf);

impl TempDir {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("occam-determinism-{}-{nonce}", std::process::id()));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn run_solve(data_root: &Path, output_root: &Path) {
    let output = Command::new(env!("CARGO_BIN_EXE_occam-circuit-hmyuuu"))
        .args(["solve-v1"])
        .arg(data_root)
        .arg(output_root)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "solve-v1 failed:\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}

fn collect_bytes(root: &Path) -> BTreeMap<PathBuf, Vec<u8>> {
    fn visit(root: &Path, directory: &Path, artifacts: &mut BTreeMap<PathBuf, Vec<u8>>) {
        let mut entries: Vec<_> = fs::read_dir(directory)
            .unwrap()
            .map(|entry| entry.unwrap().path())
            .collect();
        entries.sort();
        for path in entries {
            if path.is_dir() {
                visit(root, &path, artifacts);
            } else {
                let relative = path.strip_prefix(root).unwrap().to_path_buf();
                assert!(
                    artifacts
                        .insert(relative, fs::read(&path).unwrap())
                        .is_none()
                );
            }
        }
    }

    let mut artifacts = BTreeMap::new();
    visit(root, root, &mut artifacts);
    artifacts
}

#[test]
fn solve_v1_is_byte_identical_in_two_fresh_roots() {
    let Some(data_root) = std::env::var_os("OCCAM_V1_ROOT").map(PathBuf::from) else {
        println!("skipped solve_v1_is_byte_identical_in_two_fresh_roots: OCCAM_V1_ROOT unset");
        return;
    };
    let temporary = TempDir::new();
    let first = temporary.0.join("first");
    let second = temporary.0.join("second");
    run_solve(&data_root, &first);
    run_solve(&data_root, &second);

    let first_artifacts = collect_bytes(&first);
    let second_artifacts = collect_bytes(&second);
    let mut expected_paths = Vec::new();
    for spec in &MYSTERY_INSTANCES {
        expected_paths.push(PathBuf::from(format!("{}.txt", spec.slug)));
        expected_paths.push(
            PathBuf::from("predictions")
                .join(spec.slug)
                .join("test_outputs.csv"),
        );
    }
    expected_paths.sort();

    assert_eq!(
        first_artifacts.keys().cloned().collect::<Vec<_>>(),
        expected_paths
    );
    assert_eq!(first_artifacts, second_artifacts);

    let committed_root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let committed_artifacts: BTreeMap<_, _> = expected_paths
        .into_iter()
        .map(|relative| {
            let bytes = fs::read(committed_root.join(&relative)).unwrap();
            (relative, bytes)
        })
        .collect();
    assert_eq!(first_artifacts, committed_artifacts);
}
