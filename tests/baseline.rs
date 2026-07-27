use occam_circuit_hmyuuu::baseline::{FrozenBaseline, complete_frozen_baseline};
use occam_circuit_hmyuuu::bits::encode_lsb;
#[cfg(feature = "oxidd-oracle")]
use occam_circuit_hmyuuu::oxidd_oracle::OxiddForest;
use occam_circuit_hmyuuu::robdd::SharedRobdd;
use occam_circuit_hmyuuu::table::{PartialTable, row_index};

fn partial(ninputs: usize, noutputs: usize, rows: &[(usize, usize)]) -> PartialTable {
    PartialTable {
        ninputs,
        noutputs,
        rows: rows
            .iter()
            .map(|&(input, output)| {
                (
                    encode_lsb(input as u64, ninputs),
                    encode_lsb(output as u64, noutputs),
                )
            })
            .collect(),
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

fn brute_nearest(table: &PartialTable, input: usize) -> Vec<bool> {
    table
        .rows
        .iter()
        .enumerate()
        .min_by_key(|(row, (observed_input, _))| {
            (
                (input ^ row_index(observed_input)).count_ones(),
                row_index(observed_input),
                *row,
            )
        })
        .unwrap()
        .1
        .1
        .clone()
}

#[test]
fn zero_fill_restores_observations_and_zeros_every_unseen_row() {
    let source = partial(3, 2, &[(5, 3), (1, 2), (7, 1)]);
    let (completed, circuit) = complete_frozen_baseline(&source, FrozenBaseline::ZeroFill).unwrap();

    source.validate_against(&completed).unwrap();
    for mask in 0..8 {
        let expected = match mask {
            1 => vec![false, true],
            5 => vec![true, true],
            7 => vec![true, false],
            _ => vec![false, false],
        };
        assert_eq!(completed.outputs[mask], expected);
    }
    assert_eq!(circuit.evaluate_all().unwrap(), completed.outputs);
}

#[test]
fn hamming_nearest_breaks_distance_ties_by_numeric_input_before_row_order() {
    // Input 0 is one bit from both observed inputs. Input 1 must win even
    // though input 4 appeared first.
    let source = partial(3, 2, &[(4, 1), (1, 2)]);
    let (completed, _) =
        complete_frozen_baseline(&source, FrozenBaseline::HammingOneNearest).unwrap();

    assert_eq!(completed.outputs[0], vec![false, true]);
    source.validate_against(&completed).unwrap();
}

#[test]
fn hamming_nearest_matches_the_brute_force_definition_on_all_small_partial_domains() {
    for ninputs in 0usize..=3 {
        let row_count = 1usize << ninputs;
        for observed_set in 1usize..(1usize << row_count) {
            let rows = (0..row_count)
                .rev()
                .filter(|input| observed_set & (1usize << input) != 0)
                .map(|input| (input, input ^ (input >> 1)))
                .collect::<Vec<_>>();
            let source = partial(ninputs, ninputs.max(1), &rows);
            let (completed, _) =
                complete_frozen_baseline(&source, FrozenBaseline::HammingOneNearest).unwrap();

            for input in 0..row_count {
                assert_eq!(
                    completed.outputs[input],
                    brute_nearest(&source, input),
                    "ninputs={ninputs} observed_set={observed_set:#x} input={input}"
                );
            }
            source.validate_against(&completed).unwrap();
        }
    }
}

#[test]
fn both_methods_emit_exact_circuits_and_keep_the_lower_of_two_frozen_orders() {
    let source = partial(4, 3, &[(0, 0), (3, 5), (6, 7), (9, 2), (15, 4)]);
    for method in [FrozenBaseline::ZeroFill, FrozenBaseline::HammingOneNearest] {
        let (completed, selected) = complete_frozen_baseline(&source, method).unwrap();
        assert_eq!(selected.evaluate_all().unwrap(), completed.outputs);

        let grouped = SharedRobdd::build(&completed, grouped_order(source.ninputs))
            .unwrap()
            .extract_xag()
            .unwrap();
        let interleaved = SharedRobdd::build(&completed, interleaved_order(source.ninputs))
            .unwrap()
            .extract_xag()
            .unwrap();
        let expected_gates = grouped
            .reachable_gate_count()
            .unwrap()
            .min(interleaved.reachable_gate_count().unwrap());
        assert_eq!(selected.reachable_gate_count().unwrap(), expected_gates);
    }
}

#[test]
fn duplicate_observations_and_reruns_are_byte_identical() {
    let source = partial(4, 2, &[(8, 3), (2, 1), (2, 1), (13, 2)]);
    for method in [FrozenBaseline::ZeroFill, FrozenBaseline::HammingOneNearest] {
        let (first_table, first_circuit) = complete_frozen_baseline(&source, method).unwrap();
        let (second_table, second_circuit) = complete_frozen_baseline(&source, method).unwrap();
        assert_eq!(first_table, second_table);
        assert_eq!(
            first_circuit.to_netlist().unwrap().as_bytes(),
            second_circuit.to_netlist().unwrap().as_bytes()
        );
    }
}

#[test]
fn malformed_partial_tables_fail_closed() {
    let empty = PartialTable {
        ninputs: 2,
        noutputs: 1,
        rows: Vec::new(),
    };
    assert!(
        complete_frozen_baseline(&empty, FrozenBaseline::ZeroFill)
            .unwrap_err()
            .contains("at least one")
    );

    let conflicting = partial(2, 1, &[(1, 0), (1, 1)]);
    assert!(
        complete_frozen_baseline(&conflicting, FrozenBaseline::HammingOneNearest)
            .unwrap_err()
            .contains("conflicting")
    );

    let wrong_input_width = PartialTable {
        ninputs: 2,
        noutputs: 1,
        rows: vec![(vec![false], vec![true])],
    };
    assert!(
        complete_frozen_baseline(&wrong_input_width, FrozenBaseline::ZeroFill)
            .unwrap_err()
            .contains("input width")
    );

    let no_outputs = partial(2, 0, &[(0, 0)]);
    assert!(
        complete_frozen_baseline(&no_outputs, FrozenBaseline::ZeroFill)
            .unwrap_err()
            .contains("at least one output")
    );
}

#[cfg(feature = "oxidd-oracle")]
#[test]
fn completed_baselines_agree_with_oxidd_for_both_frozen_orders() {
    let source = partial(4, 3, &[(0, 1), (3, 6), (5, 2), (10, 7), (14, 4)]);
    for method in [FrozenBaseline::ZeroFill, FrozenBaseline::HammingOneNearest] {
        let (completed, _) = complete_frozen_baseline(&source, method).unwrap();
        for order in [
            grouped_order(source.ninputs),
            interleaved_order(source.ninputs),
        ] {
            let oracle = OxiddForest::build(&completed, order).unwrap();
            assert_eq!(oracle.evaluate_all().unwrap(), completed.outputs);
        }
    }
}
