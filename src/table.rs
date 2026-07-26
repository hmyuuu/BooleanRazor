use std::collections::HashMap;

use sha2::{Digest, Sha256};

use crate::bits::{encode_bits, encode_lsb, parse_bits};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PartialTable {
    pub ninputs: usize,
    pub noutputs: usize,
    pub rows: Vec<(Vec<bool>, Vec<bool>)>,
}

impl PartialTable {
    pub fn parse(csv: &str, ninputs: usize, noutputs: usize) -> Result<Self, String> {
        let mut lines = csv.lines();
        if lines.next() != Some("input,output") {
            return Err("expected header input,output".into());
        }

        let mut rows = Vec::new();
        let mut seen = HashMap::new();
        for line in lines {
            if line.bytes().filter(|byte| *byte == b',').count() != 1 {
                return Err("each row must contain exactly one comma".into());
            }
            let (input, output) = line
                .split_once(',')
                .expect("row with exactly one comma always splits");
            let input = parse_bits(input, ninputs)?;
            let output = parse_bits(output, noutputs)?;
            if let Some(previous) = seen.insert(input.clone(), output.clone()) {
                if previous != output {
                    return Err("duplicate input has conflicting output".into());
                }
            }
            rows.push((input, output));
        }
        if rows.is_empty() {
            return Err("table must contain at least one row".into());
        }

        Ok(Self {
            ninputs,
            noutputs,
            rows,
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InputTable {
    pub ninputs: usize,
    pub rows: Vec<Vec<bool>>,
}

impl InputTable {
    pub fn parse(csv: &str, ninputs: usize) -> Result<Self, String> {
        let mut lines = csv.lines();
        if lines.next() != Some("input") {
            return Err("expected header input".into());
        }

        let rows: Result<Vec<_>, _> = lines.map(|line| parse_bits(line, ninputs)).collect();
        let rows = rows?;
        if rows.is_empty() {
            return Err("table must contain at least one row".into());
        }

        Ok(Self { ninputs, rows })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompleteTable {
    pub ninputs: usize,
    pub noutputs: usize,
    pub outputs: Vec<Vec<bool>>,
}

impl CompleteTable {
    pub fn from_fn<F>(ninputs: usize, noutputs: usize, mut function: F) -> Self
    where
        F: FnMut(usize) -> usize,
    {
        let outputs = (0..(1usize << ninputs))
            .map(|mask| encode_lsb(function(mask) as u64, noutputs))
            .collect();
        Self {
            ninputs,
            noutputs,
            outputs,
        }
    }
}

pub fn row_index(input: &[bool]) -> usize {
    input.iter().enumerate().fold(
        0usize,
        |mask, (i, bit)| {
            if *bit { mask | (1usize << i) } else { mask }
        },
    )
}

pub fn prediction_csv_bytes(
    inputs: &InputTable,
    completed: &CompleteTable,
) -> Result<Vec<u8>, String> {
    if inputs.ninputs != completed.ninputs {
        return Err("input width does not match completed table".into());
    }
    let mut out = String::from("input,output\n");
    for input in &inputs.rows {
        let idx = row_index(input);
        out.push_str(&encode_bits(input));
        out.push(',');
        out.push_str(&encode_bits(&completed.outputs[idx]));
        out.push('\n');
    }
    Ok(out.into_bytes())
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
