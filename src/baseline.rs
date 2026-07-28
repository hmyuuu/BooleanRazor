use crate::robdd::SharedRobdd;
use crate::table::{CompleteTable, PartialTable, row_index};
use crate::xag::Circuit;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FrozenBaseline {
    ZeroFill,
    HammingOneNearest,
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct Nearest {
    distance: usize,
    input: usize,
    row: usize,
}

pub fn complete_frozen_baseline(
    table: &PartialTable,
    method: FrozenBaseline,
) -> Result<(CompleteTable, Circuit), String> {
    let completed = complete_frozen_table(table, method)?;
    let grouped = extract_verified(&completed, grouped_order(table.ninputs))?;
    let interleaved = extract_verified(&completed, interleaved_order(table.ninputs))?;
    let selected = if interleaved.reachable_gate_count()? < grouped.reachable_gate_count()? {
        interleaved
    } else {
        grouped
    };
    Ok((completed, selected))
}

pub fn complete_frozen_table(
    table: &PartialTable,
    method: FrozenBaseline,
) -> Result<CompleteTable, String> {
    let row_count = validate_partial_table(table)?;
    let outputs = match method {
        FrozenBaseline::ZeroFill => zero_fill(table, row_count),
        FrozenBaseline::HammingOneNearest => hamming_one_nearest(table, row_count)?,
    };
    let completed = CompleteTable {
        ninputs: table.ninputs,
        noutputs: table.noutputs,
        outputs,
    };
    table.validate_against(&completed)?;
    Ok(completed)
}

fn validate_partial_table(table: &PartialTable) -> Result<usize, String> {
    if table.rows.is_empty() {
        return Err("partial table must contain at least one row".into());
    }
    if table.noutputs == 0 {
        return Err("partial table must contain at least one output".into());
    }
    let shift = u32::try_from(table.ninputs)
        .map_err(|_| "partial table dimensions overflow".to_string())?;
    let row_count = 1usize
        .checked_shl(shift)
        .ok_or_else(|| "partial table dimensions overflow".to_string())?;

    let mut observed: Vec<Option<&Vec<bool>>> = vec![None; row_count];
    for (input, output) in &table.rows {
        if input.len() != table.ninputs {
            return Err("partial table input width does not match ninputs".into());
        }
        if output.len() != table.noutputs {
            return Err("partial table output width does not match noutputs".into());
        }
        let input = row_index(input);
        if let Some(previous) = &observed[input] {
            if *previous != output {
                return Err("duplicate input has conflicting output".into());
            }
        } else {
            observed[input] = Some(output);
        }
    }
    Ok(row_count)
}

fn zero_fill(table: &PartialTable, row_count: usize) -> Vec<Vec<bool>> {
    let mut outputs = vec![vec![false; table.noutputs]; row_count];
    for (input, output) in &table.rows {
        outputs[row_index(input)] = output.clone();
    }
    outputs
}

fn hamming_one_nearest(table: &PartialTable, row_count: usize) -> Result<Vec<Vec<bool>>, String> {
    let mut nearest = vec![None; row_count];
    for (row, (input, _)) in table.rows.iter().enumerate() {
        let input = row_index(input);
        let source = Nearest {
            distance: 0,
            input,
            row,
        };
        if nearest[input].is_none_or(|current| source < current) {
            nearest[input] = Some(source);
        }
    }

    // A separable Hamming-distance transform. After dimension d, each label
    // is optimal among sources that differ only in dimensions 0..=d.
    for bit in 0..table.ninputs {
        let stride = 1usize << bit;
        let block = stride
            .checked_mul(2)
            .ok_or_else(|| "partial table dimensions overflow".to_string())?;
        for base in (0..row_count).step_by(block) {
            for offset in 0..stride {
                let low = base + offset;
                let high = low + stride;
                let old_low = nearest[low];
                let old_high = nearest[high];
                nearest[low] = best(old_low, crossed(old_high)?);
                nearest[high] = best(old_high, crossed(old_low)?);
            }
        }
    }

    nearest
        .into_iter()
        .map(|source| {
            source
                .map(|source| table.rows[source.row].1.clone())
                .ok_or_else(|| "nearest baseline left an input unassigned".to_string())
        })
        .collect()
}

fn crossed(source: Option<Nearest>) -> Result<Option<Nearest>, String> {
    source
        .map(|source| {
            Ok(Nearest {
                distance: source
                    .distance
                    .checked_add(1)
                    .ok_or_else(|| "Hamming distance overflow".to_string())?,
                ..source
            })
        })
        .transpose()
}

fn best(left: Option<Nearest>, right: Option<Nearest>) -> Option<Nearest> {
    match (left, right) {
        (Some(left), Some(right)) => Some(left.min(right)),
        (left, right) => left.or(right),
    }
}

fn grouped_order(ninputs: usize) -> Vec<usize> {
    (0..ninputs).collect()
}

fn interleaved_order(ninputs: usize) -> Vec<usize> {
    let split = ninputs.div_ceil(2);
    (0..split)
        .flat_map(|bit| [Some(bit), (bit + split < ninputs).then_some(bit + split)])
        .flatten()
        .collect()
}

fn extract_verified(table: &CompleteTable, order: Vec<usize>) -> Result<Circuit, String> {
    let circuit = SharedRobdd::build(table, order)?.extract_xag()?;
    if circuit.evaluate_all()? != table.outputs {
        return Err("frozen baseline circuit verification failed".into());
    }
    Ok(circuit)
}
