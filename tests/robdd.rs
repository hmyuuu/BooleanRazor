use std::time::Instant;

use occam_circuit_hmyuuu::bits::encode_lsb;
use occam_circuit_hmyuuu::instances::{Family, semantic_output};
use occam_circuit_hmyuuu::robdd::SharedRobdd;
use occam_circuit_hmyuuu::table::CompleteTable;

fn permutations(n: usize) -> Vec<Vec<usize>> {
    fn generate(prefix: &mut Vec<usize>, remaining: &mut Vec<usize>, out: &mut Vec<Vec<usize>>) {
        if remaining.is_empty() {
            out.push(prefix.clone());
            return;
        }
        for index in 0..remaining.len() {
            let variable = remaining.remove(index);
            prefix.push(variable);
            generate(prefix, remaining, out);
            prefix.pop();
            remaining.insert(index, variable);
        }
    }

    let mut out = Vec::new();
    generate(&mut Vec::new(), &mut (0..n).collect(), &mut out);
    out
}

fn scalar_table(nvars: usize, function: usize) -> CompleteTable {
    CompleteTable::from_fn(nvars, 1, |mask| (function >> mask) & 1)
}

#[test]
fn complemented_forest_shares_outputs_and_extracts_exact_xag() {
    let table = CompleteTable::from_fn(3, 2, |mask| {
        let parity = (mask.count_ones() & 1) as usize;
        parity | ((parity ^ 1) << 1)
    });
    let forest = SharedRobdd::build(&table, vec![0, 1, 2]).unwrap();
    assert_eq!(forest.roots()[1], !forest.roots()[0]);
    assert_eq!(
        forest.shared_node_count(),
        forest.reachable_node_ids().len()
    );
    forest.validate_invariants().unwrap();

    let circuit = forest.extract_xag().unwrap();
    assert_eq!(circuit.reachable_gate_count().unwrap(), 2);
    for mask in 0..8 {
        let input = encode_lsb(mask as u64, 3);
        assert_eq!(forest.evaluate(&input).unwrap(), table.outputs[mask]);
        assert_eq!(forest.evaluate_mask(mask).unwrap(), table.outputs[mask]);
        assert_eq!(circuit.evaluate(&input).unwrap(), table.outputs[mask]);
    }
}

#[test]
fn rejects_invalid_orders_and_malformed_complete_tables() {
    let table = CompleteTable::from_fn(3, 1, |mask| mask & 1);
    assert!(
        SharedRobdd::build(&table, vec![0, 1])
            .unwrap_err()
            .contains("length")
    );
    assert!(
        SharedRobdd::build(&table, vec![0, 1, 1])
            .unwrap_err()
            .contains("duplicate")
    );
    assert!(
        SharedRobdd::build(&table, vec![0, 1, 3])
            .unwrap_err()
            .contains("range")
    );

    let wrong_rows = CompleteTable {
        ninputs: 2,
        noutputs: 1,
        outputs: vec![vec![false]; 3],
    };
    assert!(
        SharedRobdd::build(&wrong_rows, vec![0, 1])
            .unwrap_err()
            .contains("rows")
    );
    let wrong_width = CompleteTable {
        ninputs: 1,
        noutputs: 2,
        outputs: vec![vec![false], vec![true]],
    };
    assert!(
        SharedRobdd::build(&wrong_width, vec![0])
            .unwrap_err()
            .contains("width")
    );
    let zero_outputs = CompleteTable {
        ninputs: 0,
        noutputs: 0,
        outputs: vec![Vec::new()],
    };
    assert!(
        SharedRobdd::build(&zero_outputs, Vec::new())
            .unwrap_err()
            .contains("at least one output")
    );
    let overflowing = CompleteTable {
        ninputs: usize::BITS as usize,
        noutputs: 0,
        outputs: Vec::new(),
    };
    assert!(
        SharedRobdd::build(&overflowing, Vec::new())
            .unwrap_err()
            .contains("dimensions")
    );
}

#[test]
fn all_scalar_functions_through_three_variables_work_for_every_order() {
    for nvars in 0usize..=3 {
        let row_count = 1usize << nvars;
        let function_count = 1usize << row_count;
        for order in permutations(nvars) {
            for function in 0..function_count {
                let table = scalar_table(nvars, function);
                let forest = SharedRobdd::build(&table, order.clone()).unwrap();
                forest.validate_invariants().unwrap();
                assert_eq!(
                    forest.shared_node_count(),
                    forest.reachable_node_ids().len()
                );
                let circuit = forest.extract_xag().unwrap();

                for mask in 0..row_count {
                    let expected = table.outputs[mask].clone();
                    let input = encode_lsb(mask as u64, nvars);
                    assert_eq!(forest.evaluate_mask(mask).unwrap(), expected);
                    assert_eq!(forest.evaluate(&input).unwrap(), expected);
                    assert_eq!(circuit.evaluate(&input).unwrap(), expected);
                }

                let paired = CompleteTable::from_fn(nvars, 2, |mask| {
                    let bit = (function >> mask) & 1;
                    bit | ((bit ^ 1) << 1)
                });
                let paired_forest = SharedRobdd::build(&paired, order.clone()).unwrap();
                paired_forest.validate_invariants().unwrap();
                assert_eq!(paired_forest.roots()[1], !paired_forest.roots()[0]);
                assert_eq!(
                    paired_forest.shared_node_count(),
                    forest.shared_node_count()
                );
                let paired_xag = paired_forest.extract_xag().unwrap();
                for mask in 0..row_count {
                    assert_eq!(
                        paired_xag
                            .evaluate(&encode_lsb(mask as u64, nvars))
                            .unwrap(),
                        paired.outputs[mask]
                    );
                }
            }
        }
    }
}

#[test]
fn noncomplement_outputs_share_a_reachability_union() {
    let first = CompleteTable::from_fn(3, 1, |mask| (mask & 1) & ((mask >> 1) & 1));
    let second = CompleteTable::from_fn(3, 1, |mask| {
        ((mask & 1) & ((mask >> 1) & 1)) | ((mask >> 2) & 1)
    });
    let both = CompleteTable::from_fn(3, 2, |mask| {
        let shared = (mask & 1) & ((mask >> 1) & 1);
        shared | ((shared | ((mask >> 2) & 1)) << 1)
    });
    let order = vec![2, 0, 1];
    let first_count = SharedRobdd::build(&first, order.clone())
        .unwrap()
        .shared_node_count();
    let second_count = SharedRobdd::build(&second, order.clone())
        .unwrap()
        .shared_node_count();
    let forest = SharedRobdd::build(&both, order).unwrap();

    assert!(forest.shared_node_count() < first_count + second_count - 1);
    assert_ne!(forest.roots()[0], forest.roots()[1]);
    assert_ne!(forest.roots()[0], !forest.roots()[1]);
    forest.validate_invariants().unwrap();
}

#[test]
fn bit_parallel_xag_evaluation_matches_every_scalar_assignment() {
    let table = CompleteTable::from_fn(3, 2, |mask| {
        let shared = (mask & 1) & ((mask >> 1) & 1);
        shared | ((shared | ((mask >> 2) & 1)) << 1)
    });
    let circuit = SharedRobdd::build(&table, vec![2, 0, 1])
        .unwrap()
        .extract_xag()
        .unwrap();
    assert_eq!(circuit.evaluate_all().unwrap(), table.outputs);
}

fn family_table(family: Family, operand_bits: usize, output_bits: usize) -> CompleteTable {
    let input_bits = operand_bits * 2;
    let operand_mask = (1usize << operand_bits) - 1;
    CompleteTable::from_fn(input_bits, output_bits, |mask| {
        let x = (mask & operand_mask) as u64;
        let y = (mask >> operand_bits) as u64;
        semantic_output(family, operand_bits, x, y) as usize
    })
}

fn grouped_order(operand_bits: usize) -> Vec<usize> {
    (0..2 * operand_bits).collect()
}

fn interleaved_order(operand_bits: usize) -> Vec<usize> {
    (0..operand_bits)
        .flat_map(|bit| [bit, operand_bits + bit])
        .collect()
}

#[test]
fn release_diagnostics_are_exact_for_all_v1_families_and_two_orders() {
    let started = Instant::now();
    for (label, family, operand_bits, output_bits) in [
        ("A", Family::Add, 8, 9),
        ("B", Family::AbsDiff, 7, 7),
        ("C", Family::Multiply, 6, 12),
        ("D", Family::SumSquares, 5, 11),
    ] {
        let table = family_table(family, operand_bits, output_bits);
        for (order_name, order) in [
            ("grouped", grouped_order(operand_bits)),
            ("interleaved", interleaved_order(operand_bits)),
        ] {
            let case_started = Instant::now();
            let forest = SharedRobdd::build(&table, order).unwrap();
            forest.validate_invariants().unwrap();
            let circuit = forest.extract_xag().unwrap();
            let xag_gates = circuit.reachable_gate_count().unwrap();
            assert_eq!(
                circuit.evaluate_all().unwrap(),
                table.outputs,
                "{label} {order_name}"
            );
            println!(
                "family={label} order={order_name} bdd_nodes={} xag_gates={} elapsed_ms={}",
                forest.shared_node_count(),
                xag_gates,
                case_started.elapsed().as_millis()
            );
        }
    }
    println!(
        "robdd_diagnostics_total_ms={}",
        started.elapsed().as_millis()
    );
}
