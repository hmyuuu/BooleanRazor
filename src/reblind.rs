use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::{BufRead, BufReader, Cursor, Read};
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

use crate::bits::{encode_bits, encode_lsb, parse_bits};
use crate::table::{CompleteTable, PartialTable, row_index};

const MANIFEST_HEADER: &str =
    "opaque_id,input_bits,output_bits,train_rows,test_policy,observed_fraction,public_sha256";
const FORBIDDEN: [&str; 7] = [
    "family",
    "generator",
    "ground_truth",
    "test_outputs",
    "secret",
    "seed",
    "sealed",
];
const CSV_HEADER_SCAN_LIMIT: usize = 4096;
const JSON_SCAN_LIMIT: usize = 64 * 1024;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PublicInstance {
    pub opaque_id: String,
    pub input_bits: usize,
    pub output_bits: usize,
    pub train: PartialTable,
}

impl PublicInstance {
    pub fn full_domain(&self) -> impl Iterator<Item = Vec<bool>> + '_ {
        (0..(1usize << self.input_bits)).map(move |mask| encode_lsb(mask as u64, self.input_bits))
    }

    pub fn visible_folds(&self, seed_hex: &str, folds: usize) -> Result<Vec<Vec<usize>>, String> {
        if folds == 0 {
            return Err("fold count must be positive".into());
        }
        let seed = decode_selection_seed(seed_hex)?;
        let mut ranked: Vec<_> = self
            .train
            .rows
            .iter()
            .enumerate()
            .map(|(row, (input, _))| {
                let mut hasher = Sha256::new();
                hasher.update(&seed);
                hasher.update(encode_bits(input).as_bytes());
                (hasher.finalize().to_vec(), row_index(input), row)
            })
            .collect();
        ranked.sort();
        let mut result = vec![Vec::new(); folds];
        for (rank, (_, _, row)) in ranked.into_iter().enumerate() {
            result[rank % folds].push(row);
        }
        Ok(result)
    }

    pub fn import_completed_table(&self, csv: impl AsRef<[u8]>) -> Result<CompleteTable, String> {
        self.import_completed_table_reader(BufReader::new(Cursor::new(csv.as_ref())))
    }

    pub fn import_completed_table_reader(
        &self,
        mut reader: impl BufRead,
    ) -> Result<CompleteTable, String> {
        let header = read_bounded_canonical_csv_line(
            &mut reader,
            "completed-table.csv",
            b"input,output\n".len(),
        )?;
        if header.as_deref() != Some("input,output") {
            return Err("completed-table.csv must start with input,output".into());
        }
        let row_bytes = canonical_table_row_bytes(self.input_bits, self.output_bits)?;
        let shift = u32::try_from(self.input_bits)
            .map_err(|_| "completed-table.csv dimensions overflow".to_string())?;
        let expected_rows = 1usize
            .checked_shl(shift)
            .ok_or_else(|| "completed-table.csv dimensions overflow".to_string())?;
        let mut outputs = Vec::with_capacity(expected_rows);
        for expected_mask in 0..expected_rows {
            let line =
                read_bounded_canonical_csv_line(&mut reader, "completed-table.csv", row_bytes)?
                    .ok_or_else(|| "completed-table.csv has too few rows".to_string())?;
            let (input, output) = parse_table_row(&line, self.input_bits, self.output_bits)?;
            if row_index(&input) != expected_mask {
                return Err(
                    "completed-table.csv inputs must be strictly increasing numeric masks".into(),
                );
            }
            outputs.push(output);
        }
        if read_bounded_canonical_csv_line(&mut reader, "completed-table.csv", row_bytes)?.is_some()
        {
            return Err("completed-table.csv has too many rows".into());
        }
        let completed = CompleteTable {
            ninputs: self.input_bits,
            noutputs: self.output_bits,
            outputs,
        };
        self.train.validate_against(&completed)?;
        Ok(completed)
    }
}

pub fn validate_selection_seed(seed_hex: &str) -> Result<(), String> {
    decode_selection_seed(seed_hex).map(|_| ())
}

fn decode_selection_seed(seed_hex: &str) -> Result<Vec<u8>, String> {
    let seed = decode_lower_hex(seed_hex, "selection seed")?;
    if seed.len() != 32 {
        return Err("selection seed must be exactly 64 lowercase hex characters".into());
    }
    Ok(seed)
}

fn read_bounded_canonical_csv_line(
    reader: &mut impl BufRead,
    label: &str,
    max_bytes: usize,
) -> Result<Option<String>, String> {
    let read_limit = max_bytes
        .checked_add(1)
        .ok_or_else(|| format!("{label} canonical width overflows"))?;
    let mut bytes = Vec::with_capacity(read_limit);
    let count = reader
        .take(read_limit as u64)
        .read_until(b'\n', &mut bytes)
        .map_err(|error| format!("read {label}: {error}"))?;
    if count == 0 {
        return Ok(None);
    }
    if bytes.len() > max_bytes {
        return Err(format!("{label} line exceeds canonical width"));
    }
    if bytes.contains(&b'\r') {
        return Err(format!("{label} must use LF, not CRLF"));
    }
    if bytes.last() != Some(&b'\n') {
        return Err(format!("{label} must end with one LF"));
    }
    bytes.pop();
    String::from_utf8(bytes)
        .map(Some)
        .map_err(|_| format!("{label} must be valid UTF-8"))
}

fn canonical_table_row_bytes(ninputs: usize, noutputs: usize) -> Result<usize, String> {
    ninputs
        .checked_add(noutputs)
        .and_then(|width| width.checked_add(2))
        .ok_or_else(|| "canonical table row width overflows".to_string())
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PublicSuite {
    instances: Vec<PublicInstance>,
}

impl PublicSuite {
    pub fn load_frozen(root: &Path) -> Result<Self, String> {
        let expected_commitment = tracked_commitment()?;
        let expected_manifest = include_bytes!("../reblind/manifest.csv");
        let environment_root = std::env::var_os("OCCAM_REBLIND_PUBLIC_ROOT").ok_or_else(|| {
            "OCCAM_REBLIND_PUBLIC_ROOT must name the supplied public root".to_string()
        })?;
        let root = canonical_public_root(root)?;
        let environment_root = canonical_public_root(Path::new(&environment_root))?;
        if root != environment_root {
            return Err(
                "PUBLIC_ROOT and OCCAM_REBLIND_PUBLIC_ROOT must canonicalize to the same directory"
                    .into(),
            );
        }
        if root.file_name().and_then(|name| name.to_str()) != Some(expected_commitment.as_str()) {
            return Err("public root basename does not equal the tracked commitment".into());
        }
        let manifest = strict_regular_bytes_exact(
            &root.join("manifest.csv"),
            "manifest.csv",
            expected_manifest.len(),
            "tracked manifest",
        )?;
        if manifest != expected_manifest {
            return Err("public manifest does not match the tracked frozen manifest".into());
        }
        load_checked(&root, &expected_commitment, &manifest)
    }

    pub fn instances(&self) -> &[PublicInstance] {
        &self.instances
    }

    pub fn instance(&self, opaque_id: &str) -> Result<&PublicInstance, String> {
        self.instances
            .iter()
            .find(|instance| instance.opaque_id == opaque_id)
            .ok_or_else(|| format!("unknown opaque instance {opaque_id:?}"))
    }

    #[cfg(test)]
    pub(crate) fn load_with_trust(root: &Path, trust: BundleTrust) -> Result<Self, String> {
        let root = canonical_public_root(root)?;
        let manifest = strict_regular_bytes_exact(
            &root.join("manifest.csv"),
            "manifest.csv",
            trust.manifest.len(),
            "test trust",
        )?;
        if manifest != trust.manifest {
            return Err("synthetic manifest does not match its test trust".into());
        }
        load_checked(&root, &trust.commitment, &manifest)
    }
}

#[cfg(test)]
#[derive(Clone, Debug)]
pub(crate) struct BundleTrust {
    commitment: String,
    manifest: Vec<u8>,
}

#[cfg(test)]
impl BundleTrust {
    pub(crate) fn new(commitment: impl Into<String>, manifest: Vec<u8>) -> Self {
        Self {
            commitment: commitment.into(),
            manifest,
        }
    }
}

pub fn scan_public_bundle(root: &Path) -> Result<Vec<String>, String> {
    let root = canonical_public_root(root)?;
    let mut findings = Vec::new();
    scan_directory(&root, &root, &mut findings)?;
    Ok(findings)
}

fn load_checked(
    root: &Path,
    _commitment: &str,
    manifest_bytes: &[u8],
) -> Result<PublicSuite, String> {
    let records = parse_manifest(manifest_bytes)?;
    let expected_paths: BTreeSet<_> = records
        .iter()
        .flat_map(|record| {
            [
                PathBuf::from("manifest.csv"),
                PathBuf::from("instances")
                    .join(&record.opaque_id)
                    .join("train.csv"),
            ]
        })
        .collect();
    let expected_directories: BTreeSet<_> = std::iter::once(PathBuf::from("instances"))
        .chain(
            records
                .iter()
                .map(|record| PathBuf::from("instances").join(&record.opaque_id)),
        )
        .collect();
    let actual_paths = regular_relative_paths(root)?;
    if actual_paths.files != expected_paths || actual_paths.directories != expected_directories {
        return Err("public bundle has missing or extra files".into());
    }
    for record in &records {
        let train_path = root
            .join("instances")
            .join(&record.opaque_id)
            .join("train.csv");
        validate_regular_file_exact_metadata(
            &train_path,
            "train.csv",
            canonical_train_file_bytes(record)?,
            "manifest",
        )?;
    }
    let findings = scan_public_bundle(root)?;
    if !findings.is_empty() {
        return Err(format!(
            "public bundle leaks forbidden metadata: {}",
            findings.join(", ")
        ));
    }

    let mut strata = BTreeMap::new();
    let mut instances = Vec::with_capacity(records.len());
    for record in records {
        let train_path = root
            .join("instances")
            .join(&record.opaque_id)
            .join("train.csv");
        let expected_bytes = canonical_train_file_bytes(&record)?;
        let bytes =
            strict_regular_bytes_exact(&train_path, "train.csv", expected_bytes, "manifest")?;
        if public_digest(&record.fields(), &bytes) != record.public_sha256 {
            return Err(format!(
                "{} train.csv digest does not match manifest",
                record.opaque_id
            ));
        }
        let train = parse_canonical_partial(&bytes, record.input_bits, record.output_bits)?;
        if train.rows.len() != record.train_rows {
            return Err(format!(
                "{} train row count does not match manifest",
                record.opaque_id
            ));
        }
        let key = (record.input_bits, record.observed_fraction.clone());
        if let Some(previous) = strata.insert(key, train.rows.len()) {
            if previous != train.rows.len() {
                return Err(
                    "public bundle has unequal train counts within a width/fraction stratum".into(),
                );
            }
        }
        instances.push(PublicInstance {
            opaque_id: record.opaque_id,
            input_bits: record.input_bits,
            output_bits: record.output_bits,
            train,
        });
    }
    Ok(PublicSuite { instances })
}

#[derive(Debug)]
struct ManifestRecord {
    opaque_id: String,
    input_bits: usize,
    output_bits: usize,
    train_rows: usize,
    observed_fraction: String,
    public_sha256: String,
    digest_fields: [String; 6],
}

impl ManifestRecord {
    fn fields(&self) -> [&str; 6] {
        [
            &self.digest_fields[0],
            &self.digest_fields[1],
            &self.digest_fields[2],
            &self.digest_fields[3],
            &self.digest_fields[4],
            &self.digest_fields[5],
        ]
    }
}

fn parse_manifest(bytes: &[u8]) -> Result<Vec<ManifestRecord>, String> {
    let text = canonical_utf8(bytes, "manifest.csv")?;
    let mut lines = text.split_terminator('\n');
    if lines.next() != Some(MANIFEST_HEADER) {
        return Err("manifest.csv has an invalid header".into());
    }
    let mut records = Vec::new();
    let mut previous = None;
    for line in lines {
        let fields: Vec<_> = line.split(',').collect();
        if fields.len() != 7 {
            return Err("manifest.csv rows must have exactly seven columns".into());
        }
        let [
            opaque_id,
            input_bits,
            output_bits,
            train_rows,
            test_policy,
            observed_fraction,
            public_sha256,
        ] = fields.as_slice()
        else {
            unreachable!()
        };
        if !valid_opaque_id(opaque_id) {
            return Err("manifest.csv has an invalid opaque_id".into());
        }
        if previous
            .as_ref()
            .is_some_and(|prior: &String| prior.as_str() >= *opaque_id)
        {
            return Err("manifest.csv opaque IDs must be strictly sorted and unique".into());
        }
        previous = Some((*opaque_id).to_string());
        let input_bits = canonical_usize(input_bits, "input_bits")?;
        if !matches!(input_bits, 12 | 16 | 20) {
            return Err("manifest.csv input_bits must be 12, 16, or 20".into());
        }
        let output_bits = canonical_usize(output_bits, "output_bits")?;
        if output_bits != input_bits + 1 {
            return Err("manifest.csv output_bits must equal input_bits + 1".into());
        }
        let train_rows = canonical_usize(train_rows, "train_rows")?;
        if train_rows == 0 || train_rows >= (1usize << input_bits) {
            return Err("manifest.csv train_rows is outside the visible partial domain".into());
        }
        if *test_policy != "all-unobserved" {
            return Err("manifest.csv test_policy must equal all-unobserved".into());
        }
        if !matches!(*observed_fraction, "0.03" | "0.10") {
            return Err("manifest.csv observed_fraction must be 0.03 or 0.10".into());
        }
        if !valid_hex_64(public_sha256) {
            return Err("manifest.csv public_sha256 must be lowercase 64-hex".into());
        }
        records.push(ManifestRecord {
            opaque_id: (*opaque_id).to_string(),
            input_bits,
            output_bits,
            train_rows,
            observed_fraction: (*observed_fraction).to_string(),
            public_sha256: (*public_sha256).to_string(),
            digest_fields: [
                (*opaque_id).to_string(),
                input_bits.to_string(),
                output_bits.to_string(),
                train_rows.to_string(),
                (*test_policy).to_string(),
                (*observed_fraction).to_string(),
            ],
        });
    }
    if records.is_empty() {
        return Err("manifest.csv must contain at least one opaque instance".into());
    }
    Ok(records)
}

fn parse_canonical_partial(
    bytes: &[u8],
    ninputs: usize,
    noutputs: usize,
) -> Result<PartialTable, String> {
    let text = canonical_utf8(bytes, "train.csv")?;
    let mut lines = text.split_terminator('\n');
    if lines.next() != Some("input,output") {
        return Err("train.csv must start with input,output".into());
    }
    let mut rows = Vec::new();
    let mut previous = None;
    for line in lines {
        let (input, output) = parse_table_row(line, ninputs, noutputs)?;
        let mask = row_index(&input);
        if previous.is_some_and(|prior| prior >= mask) {
            return Err("train.csv inputs must be strictly increasing numeric masks".into());
        }
        previous = Some(mask);
        rows.push((input, output));
    }
    if rows.is_empty() {
        return Err("train.csv must contain at least one visible row".into());
    }
    Ok(PartialTable {
        ninputs,
        noutputs,
        rows,
    })
}

fn parse_table_row(
    line: &str,
    ninputs: usize,
    noutputs: usize,
) -> Result<(Vec<bool>, Vec<bool>), String> {
    if line.bytes().filter(|byte| *byte == b',').count() != 1 {
        return Err("table rows must contain exactly one comma".into());
    }
    let (input, output) = line.split_once(',').expect("one comma always splits");
    Ok((parse_bits(input, ninputs)?, parse_bits(output, noutputs)?))
}

fn canonical_utf8<'a>(bytes: &'a [u8], label: &str) -> Result<&'a str, String> {
    if bytes.contains(&b'\r') {
        return Err(format!("{label} must use LF, not CRLF"));
    }
    if !bytes.ends_with(b"\n") {
        return Err(format!("{label} must end with one LF"));
    }
    std::str::from_utf8(bytes).map_err(|_| format!("{label} must be valid UTF-8"))
}

fn public_digest(fields: &[&str; 6], train: &[u8]) -> String {
    let mut hasher = Sha256::new();
    for field in fields {
        hasher.update((field.len() as u64).to_be_bytes());
        hasher.update(field.as_bytes());
    }
    hasher.update((train.len() as u64).to_be_bytes());
    hasher.update(train);
    format!("{:x}", hasher.finalize())
}

fn canonical_usize(value: &str, label: &str) -> Result<usize, String> {
    if value.is_empty()
        || (value.len() > 1 && value.starts_with('0'))
        || !value.bytes().all(|byte| byte.is_ascii_digit())
    {
        return Err(format!("{label} must be a canonical decimal integer"));
    }
    value
        .parse()
        .map_err(|_| format!("{label} is out of range"))
}

fn valid_opaque_id(value: &str) -> bool {
    value.len() == 27
        && value.starts_with("rb-")
        && value[3..]
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn valid_hex_64(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn decode_lower_hex(value: &str, label: &str) -> Result<Vec<u8>, String> {
    if !valid_hex_64(value) {
        return Err(format!(
            "{label} must be exactly 64 lowercase hex characters"
        ));
    }
    (0..value.len())
        .step_by(2)
        .map(|index| {
            u8::from_str_radix(&value[index..index + 2], 16)
                .map_err(|_| format!("{label} is invalid"))
        })
        .collect()
}

fn tracked_commitment() -> Result<String, String> {
    let bytes = include_bytes!("../reblind/COMMITMENT.txt");
    let value = canonical_utf8(bytes, "tracked COMMITMENT.txt")?
        .strip_suffix('\n')
        .unwrap();
    if !valid_hex_64(value) {
        return Err("tracked COMMITMENT.txt is invalid".into());
    }
    Ok(value.to_string())
}

fn canonical_public_root(root: &Path) -> Result<PathBuf, String> {
    let metadata = fs::symlink_metadata(root).map_err(|error| format!("public root: {error}"))?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err("public root must be a real directory, not a symlink".into());
    }
    fs::canonicalize(root).map_err(|error| format!("canonicalize public root: {error}"))
}

fn canonical_train_file_bytes(record: &ManifestRecord) -> Result<usize, String> {
    let row_bytes = canonical_table_row_bytes(record.input_bits, record.output_bits)?;
    record
        .train_rows
        .checked_mul(row_bytes)
        .and_then(|rows| rows.checked_add(b"input,output\n".len()))
        .ok_or_else(|| format!("{} train.csv byte length overflows", record.opaque_id))
}

fn strict_regular_bytes_exact(
    path: &Path,
    label: &str,
    expected_len: usize,
    authority: &str,
) -> Result<Vec<u8>, String> {
    validate_regular_file_exact_metadata(path, label, expected_len, authority)?;
    let file = fs::File::open(path).map_err(|error| format!("{label}: {error}"))?;
    let mut bytes = Vec::with_capacity(expected_len);
    file.take(
        expected_len
            .checked_add(1)
            .ok_or_else(|| format!("{label} byte length overflows"))? as u64,
    )
    .read_to_end(&mut bytes)
    .map_err(|error| format!("{label}: {error}"))?;
    if bytes.len() != expected_len {
        return Err(format!("{label} byte length does not match {authority}"));
    }
    Ok(bytes)
}

fn validate_regular_file_exact_metadata(
    path: &Path,
    label: &str,
    expected_len: usize,
    authority: &str,
) -> Result<(), String> {
    let metadata = fs::symlink_metadata(path).map_err(|error| format!("{label}: {error}"))?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(format!("{label} must be a regular non-symlink file"));
    }
    #[cfg(unix)]
    if std::os::unix::fs::PermissionsExt::mode(&metadata.permissions()) & 0o111 != 0 {
        return Err(format!("{label} must not be executable"));
    }
    if metadata.len() != expected_len as u64 {
        return Err(format!("{label} byte length does not match {authority}"));
    }
    Ok(())
}

#[derive(Default)]
struct BundlePaths {
    files: BTreeSet<PathBuf>,
    directories: BTreeSet<PathBuf>,
}

fn regular_relative_paths(root: &Path) -> Result<BundlePaths, String> {
    let mut paths = BundlePaths::default();
    collect_regular_paths(root, root, &mut paths)?;
    Ok(paths)
}

fn collect_regular_paths(
    root: &Path,
    directory: &Path,
    paths: &mut BundlePaths,
) -> Result<(), String> {
    for entry in fs::read_dir(directory).map_err(|error| format!("read public bundle: {error}"))? {
        let entry = entry.map_err(|error| format!("read public bundle entry: {error}"))?;
        let path = entry.path();
        let metadata = fs::symlink_metadata(&path)
            .map_err(|error| format!("public bundle metadata: {error}"))?;
        if metadata.file_type().is_symlink() {
            return Err("public bundle must not contain symlinks".into());
        }
        if metadata.is_dir() {
            paths.directories.insert(
                path.strip_prefix(root)
                    .expect("walk stays below root")
                    .to_path_buf(),
            );
            collect_regular_paths(root, &path, paths)?;
        } else if metadata.is_file() {
            #[cfg(unix)]
            if std::os::unix::fs::PermissionsExt::mode(&metadata.permissions()) & 0o111 != 0 {
                return Err("public bundle must not contain executable files".into());
            }
            paths.files.insert(
                path.strip_prefix(root)
                    .expect("walk stays below root")
                    .to_path_buf(),
            );
        } else {
            return Err("public bundle contains a non-regular file".into());
        }
    }
    Ok(())
}

fn scan_directory(root: &Path, directory: &Path, findings: &mut Vec<String>) -> Result<(), String> {
    for entry in fs::read_dir(directory).map_err(|error| format!("scan public bundle: {error}"))? {
        let entry = entry.map_err(|error| format!("scan public bundle entry: {error}"))?;
        let path = entry.path();
        let relative = path.strip_prefix(root).expect("scan stays below root");
        let name = entry.file_name().to_string_lossy().to_ascii_lowercase();
        if let Some(word) = FORBIDDEN.iter().find(|word| name.contains(**word)) {
            findings.push(format!("{} filename contains {word}", relative.display()));
        }
        let metadata =
            fs::symlink_metadata(&path).map_err(|error| format!("scan metadata: {error}"))?;
        if metadata.file_type().is_symlink() {
            findings.push(format!("{} is a symlink", relative.display()));
            continue;
        }
        if metadata.is_dir() {
            scan_directory(root, &path, findings)?;
        } else if metadata.is_file() {
            #[cfg(unix)]
            if std::os::unix::fs::PermissionsExt::mode(&metadata.permissions()) & 0o111 != 0 {
                findings.push(format!("{} is executable", relative.display()));
            }
            if path.extension().is_some_and(|ext| ext == "csv") {
                let file =
                    fs::File::open(&path).map_err(|error| format!("scan CSV file: {error}"))?;
                let mut reader = BufReader::new(file);
                if let Some(header) = read_bounded_canonical_csv_line(
                    &mut reader,
                    "public CSV header",
                    CSV_HEADER_SCAN_LIMIT,
                )? {
                    scan_keys(header.split(','), relative, findings);
                }
            }
            if path.extension().is_some_and(|ext| ext == "json") {
                if metadata.len() > JSON_SCAN_LIMIT as u64 {
                    return Err(format!(
                        "{} exceeds the JSON scan limit",
                        relative.display()
                    ));
                }
                let file =
                    fs::File::open(&path).map_err(|error| format!("scan JSON file: {error}"))?;
                let mut bytes = Vec::with_capacity(metadata.len() as usize);
                file.take((JSON_SCAN_LIMIT + 1) as u64)
                    .read_to_end(&mut bytes)
                    .map_err(|error| format!("scan JSON file: {error}"))?;
                if bytes.len() > JSON_SCAN_LIMIT {
                    return Err(format!(
                        "{} exceeds the JSON scan limit",
                        relative.display()
                    ));
                }
                let text = std::str::from_utf8(&bytes).unwrap_or("");
                scan_jsonish_keys(text, relative, findings);
            }
        } else {
            findings.push(format!("{} is not regular", relative.display()));
        }
    }
    Ok(())
}

fn scan_keys<'a>(
    keys: impl IntoIterator<Item = &'a str>,
    relative: &Path,
    findings: &mut Vec<String>,
) {
    for key in keys {
        let lower = key.trim_matches('"').to_ascii_lowercase();
        if let Some(word) = FORBIDDEN.iter().find(|word| lower.contains(**word)) {
            findings.push(format!("{} key contains {word}", relative.display()));
        }
    }
}

fn scan_jsonish_keys(text: &str, relative: &Path, findings: &mut Vec<String>) {
    for quoted in text.split('"').skip(1).step_by(2) {
        if let Some(word) = FORBIDDEN
            .iter()
            .find(|word| quoted.to_ascii_lowercase().contains(**word))
        {
            findings.push(format!("{} JSON key contains {word}", relative.display()));
        }
    }
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::io::{BufReader, Cursor};
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicUsize, Ordering};

    use sha2::{Digest, Sha256};

    use super::{BundleTrust, PublicSuite, scan_public_bundle};
    use crate::bits::encode_lsb;

    struct SyntheticRoot {
        root: PathBuf,
        trust: BundleTrust,
    }

    impl SyntheticRoot {
        fn path(&self) -> &Path {
            &self.root
        }

        fn trust(&self) -> BundleTrust {
            self.trust.clone()
        }
    }

    impl Drop for SyntheticRoot {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    fn temp_root() -> PathBuf {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let root = std::env::temp_dir().join(format!(
            "occam-reblind-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&root).unwrap();
        root
    }

    fn framed_digest(fields: &[&str], train: &[u8]) -> String {
        let mut hasher = Sha256::new();
        for field in fields {
            hasher.update((field.len() as u64).to_be_bytes());
            hasher.update(field.as_bytes());
        }
        hasher.update((train.len() as u64).to_be_bytes());
        hasher.update(train);
        format!("{:x}", hasher.finalize())
    }

    fn synthetic_public_bundle() -> SyntheticRoot {
        synthetic_public_bundle_with_train(
            b"input,output\n000000000000,0000000000000\n010000000000,0000000000000\n",
        )
    }

    fn synthetic_public_bundle_with_train(train: &[u8]) -> SyntheticRoot {
        let root = temp_root();
        let first = "rb-000000000000000000000001";
        let second = "rb-000000000000000000000002";
        for id in [first, second] {
            let path = root.join("instances").join(id);
            fs::create_dir_all(&path).unwrap();
            fs::write(path.join("train.csv"), train).unwrap();
        }
        let mut manifest = String::from(
            "opaque_id,input_bits,output_bits,train_rows,test_policy,observed_fraction,public_sha256\n",
        );
        for id in [first, second] {
            let fields = [id, "12", "13", "2", "all-unobserved", "0.03"];
            manifest.push_str(&fields.join(","));
            manifest.push(',');
            manifest.push_str(&framed_digest(&fields, train));
            manifest.push('\n');
        }
        fs::write(root.join("manifest.csv"), &manifest).unwrap();
        SyntheticRoot {
            root,
            trust: BundleTrust::new("synthetic-commitment", manifest.into_bytes()),
        }
    }

    fn canonical_candidate() -> Vec<u8> {
        let mut csv = String::from("input,output\n");
        for mask in 0..(1usize << 12) {
            csv.push_str(&crate::bits::encode_bits(&encode_lsb(mask as u64, 12)));
            csv.push_str(",0000000000000\n");
        }
        csv.into_bytes()
    }

    #[test]
    fn public_bundle_import_is_opaque_and_digest_checked() {
        let root = synthetic_public_bundle();
        let suite = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap();
        assert_eq!(suite.instances().len(), 2);
        for instance in suite.instances() {
            assert!(instance.opaque_id.starts_with("rb-"));
            assert_eq!(instance.output_bits, instance.input_bits + 1);
            assert!(instance.train.rows.len() < (1usize << instance.input_bits));
        }
        assert!(scan_public_bundle(root.path()).unwrap().is_empty());
    }

    #[test]
    fn public_bundle_rejects_an_extra_empty_directory() {
        let root = synthetic_public_bundle();
        fs::create_dir(root.path().join("unapproved")).unwrap();

        let error = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap_err();

        assert!(error.contains("missing or extra files"));
    }

    #[test]
    fn completed_table_must_be_canonical_and_training_consistent() {
        let root = synthetic_public_bundle();
        let instance = PublicSuite::load_with_trust(root.path(), root.trust())
            .unwrap()
            .instances()
            .first()
            .unwrap()
            .clone();
        let completed = instance
            .import_completed_table(canonical_candidate())
            .unwrap();
        instance.train.validate_against(&completed).unwrap();
    }

    #[test]
    fn completed_table_reader_accepts_canonical_rows_from_a_small_buffer() {
        let root = synthetic_public_bundle();
        let instance = PublicSuite::load_with_trust(root.path(), root.trust())
            .unwrap()
            .instances()
            .first()
            .unwrap()
            .clone();

        let completed = instance
            .import_completed_table_reader(BufReader::with_capacity(
                1,
                Cursor::new(canonical_candidate()),
            ))
            .unwrap();

        instance.train.validate_against(&completed).unwrap();
    }

    #[test]
    fn completed_table_reader_rejects_a_row_exceeding_canonical_width() {
        let root = synthetic_public_bundle();
        let instance = PublicSuite::load_with_trust(root.path(), root.trust())
            .unwrap()
            .instances()[0]
            .clone();
        let oversized = format!("input,output\n{},{}\n", "0".repeat(12), "0".repeat(1024));

        let error = instance.import_completed_table(oversized).unwrap_err();

        assert!(error.contains("exceeds canonical width"), "{error}");
    }

    #[test]
    fn bundle_rejects_noncanonical_train_length_from_metadata() {
        let train = b"input,output\n\
000000000000,0000000000000\n\
010000000000,0000000000000\n\
110000000000,0000000000000\n";
        let root = synthetic_public_bundle_with_train(train);

        let error = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap_err();

        assert!(
            error.contains("byte length does not match manifest"),
            "{error}"
        );
    }

    #[test]
    fn public_scan_bounds_json_files_and_csv_headers() {
        let json_root = synthetic_public_bundle();
        fs::write(
            json_root.path().join("metadata.json"),
            vec![b' '; 64 * 1024 + 1],
        )
        .unwrap();
        let error = scan_public_bundle(json_root.path()).unwrap_err();
        assert!(error.contains("JSON scan limit"), "{error}");

        let csv_root = synthetic_public_bundle();
        let mut oversized_header = vec![b'x'; 4097];
        oversized_header.push(b'\n');
        fs::write(csv_root.path().join("metadata.csv"), oversized_header).unwrap();
        let error = scan_public_bundle(csv_root.path()).unwrap_err();
        assert!(error.contains("exceeds canonical width"), "{error}");
    }

    #[test]
    fn visible_folds_are_reproducible_and_use_every_visible_row_once() {
        let root = synthetic_public_bundle();
        let instance = PublicSuite::load_with_trust(root.path(), root.trust())
            .unwrap()
            .instances()
            .first()
            .unwrap()
            .clone();
        let first = instance.visible_folds(&"00".repeat(32), 2).unwrap();
        let second = instance.visible_folds(&"00".repeat(32), 2).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.iter().flatten().count(), instance.train.rows.len());
    }

    #[test]
    fn recovered_csv_boundaries_reject_noncanonical_bytes_columns_and_order() {
        let invalid_trains: &[(&[u8], &str)] = &[
            (
                b"input,output\r\n00000000000,0000000000000\n010000000000,0000000000000\n",
                "CRLF",
            ),
            (
                b"input,output\n000000000000,0000000000000\n010000000000,00000000000000",
                "end with one LF",
            ),
            (
                b"input,output\n00000000000,,0000000000000\n010000000000,0000000000000\n",
                "one comma",
            ),
            (
                b"input,output\n000000000000,0000000000000\n000000000000,0000000000000\n",
                "strictly increasing",
            ),
            (
                b"input,output\n000000000000,0000000000000\n000000000000,1000000000000\n",
                "strictly increasing",
            ),
            (
                b"input,output\n010000000000,0000000000000\n000000000000,0000000000000\n",
                "strictly increasing",
            ),
            (
                b"input,output\n000000000000,0000000000000\n010000000000,\xff000000000000\n",
                "valid UTF-8",
            ),
        ];
        for (train, expected) in invalid_trains {
            let root = synthetic_public_bundle_with_train(train);
            let error = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap_err();
            assert!(
                error.contains(expected),
                "expected {expected:?} for invalid train bytes, got {error:?}"
            );
        }

        let root = synthetic_public_bundle();
        let mut manifest = fs::read(root.path().join("manifest.csv")).unwrap();
        let header_end = manifest.iter().position(|byte| *byte == b'\n').unwrap();
        manifest.splice(header_end..header_end, b",extra".iter().copied());
        fs::write(root.path().join("manifest.csv"), &manifest).unwrap();
        let error = PublicSuite::load_with_trust(
            root.path(),
            BundleTrust::new("synthetic-commitment", manifest),
        )
        .unwrap_err();
        assert!(error.contains("invalid header"));

        let root = synthetic_public_bundle();
        let instance = PublicSuite::load_with_trust(root.path(), root.trust())
            .unwrap()
            .instances()[0]
            .clone();
        let canonical = String::from_utf8(canonical_candidate()).unwrap();
        let mut lines: Vec<_> = canonical
            .strip_suffix('\n')
            .unwrap()
            .lines()
            .map(str::to_string)
            .collect();
        let mut duplicate = lines.clone();
        duplicate[2] = duplicate[1].clone();
        let mut unordered = lines.clone();
        unordered.swap(1, 2);
        lines[1].push_str(",extra");
        let candidates = [
            canonical.replace('\n', "\r\n").into_bytes(),
            canonical.strip_suffix('\n').unwrap().as_bytes().to_vec(),
            format!("{}\n", lines.join("\n")).into_bytes(),
            format!("{}\n", duplicate.join("\n")).into_bytes(),
            format!("{}\n", unordered.join("\n")).into_bytes(),
        ];
        for candidate in candidates {
            assert!(instance.import_completed_table(candidate).is_err());
        }
    }

    #[test]
    fn recovered_bundle_boundary_rejects_extra_executable_and_symlink_paths() {
        let root = synthetic_public_bundle();
        fs::write(root.path().join("extra.txt"), b"extra\n").unwrap();
        let error = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap_err();
        assert!(error.contains("missing or extra files"));

        #[cfg(unix)]
        {
            use std::os::unix::fs::{PermissionsExt, symlink};

            let root = synthetic_public_bundle();
            let train = root
                .path()
                .join("instances/rb-000000000000000000000001/train.csv");
            let mut permissions = fs::metadata(&train).unwrap().permissions();
            permissions.set_mode(0o755);
            fs::set_permissions(&train, permissions).unwrap();
            let error = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap_err();
            assert!(error.contains("executable"));

            let root = synthetic_public_bundle();
            let train = root
                .path()
                .join("instances/rb-000000000000000000000001/train.csv");
            fs::remove_file(&train).unwrap();
            symlink(root.path().join("manifest.csv"), &train).unwrap();
            let error = PublicSuite::load_with_trust(root.path(), root.trust()).unwrap_err();
            assert!(error.contains("symlink"));
        }
    }

    #[test]
    fn recovered_visible_folds_reject_malformed_64_hex_seeds() {
        let root = synthetic_public_bundle();
        let instance = PublicSuite::load_with_trust(root.path(), root.trust())
            .unwrap()
            .instances()[0]
            .clone();

        for seed in [
            String::new(),
            "0".repeat(63),
            "0".repeat(66),
            "g".repeat(64),
            "A".repeat(64),
        ] {
            let error = instance.visible_folds(&seed, 5).unwrap_err();
            assert!(error.contains("64 lowercase hex"));
        }
    }
}
