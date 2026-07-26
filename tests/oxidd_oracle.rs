#![cfg(feature = "oxidd-oracle")]

use std::time::Instant;

use occam_circuit_hmyuuu::instances::{Family, semantic_output};
use occam_circuit_hmyuuu::oxidd_oracle::OxiddForest;
use occam_circuit_hmyuuu::robdd::SharedRobdd;
use occam_circuit_hmyuuu::table::CompleteTable;
use oxidd::bcdd::BCDDFunction;
use oxidd::{BooleanFunction, Manager, ManagerRef};

#[test]
fn oxidd_bcdd_agrees_with_custom_forest_on_every_assignment() {
    let table = CompleteTable::from_fn(6, 6, |mask| {
        let x = mask & 7;
        let y = (mask >> 3) & 7;
        x * y
    });
    let order = vec![0, 3, 1, 4, 2, 5];
    let custom = SharedRobdd::build(&table, order.clone()).unwrap();
    let oracle = OxiddForest::build(&table, order).unwrap();
    for mask in 0..64 {
        assert_eq!(
            oracle.evaluate_mask(mask).unwrap(),
            custom.evaluate_mask(mask).unwrap()
        );
    }
}

#[test]
fn complement_outputs_share_the_terminal_inclusive_node_union() {
    let table = CompleteTable::from_fn(4, 2, |mask| {
        let parity = (mask.count_ones() & 1) as usize;
        parity | ((parity ^ 1) << 1)
    });
    let order = vec![2, 0, 3, 1];
    let custom = SharedRobdd::build(&table, order.clone()).unwrap();
    let oracle = OxiddForest::build(&table, order).unwrap();

    assert_eq!(oracle.node_count(0).unwrap(), oracle.node_count(1).unwrap());
    assert_eq!(oracle.shared_node_count(), oracle.node_count(0).unwrap());
    assert_eq!(oracle.shared_node_count(), custom.shared_node_count());
    println!(
        "complement_identity custom_nodes={} oxidd_nodes={}",
        custom.shared_node_count(),
        oracle.shared_node_count()
    );
}

#[test]
fn swapped_order_keeps_logical_inputs_distinct_from_varnos() {
    let table = CompleteTable::from_fn(2, 2, |mask| mask);
    let oracle = OxiddForest::build(&table, vec![1, 0]).unwrap();

    assert_eq!(oracle.varno_for_logical_input(0).unwrap(), 1);
    assert_eq!(oracle.varno_for_logical_input(1).unwrap(), 0);
    assert_eq!(oracle.logical_input_for_varno(0).unwrap(), 1);
    assert_eq!(oracle.logical_input_for_varno(1).unwrap(), 0);
    for mask in 0..4 {
        assert_eq!(oracle.evaluate_mask(mask).unwrap(), table.outputs[mask]);
    }
}

#[test]
fn rejects_invalid_orders_and_malformed_complete_tables() {
    fn build_error(table: &CompleteTable, order: Vec<usize>) -> String {
        match OxiddForest::build(table, order) {
            Ok(_) => panic!("malformed OxiDD forest unexpectedly built"),
            Err(error) => error,
        }
    }

    let table = CompleteTable::from_fn(3, 1, |mask| mask & 1);
    assert!(build_error(&table, vec![0, 1]).contains("length"));
    assert!(build_error(&table, vec![0, 1, 1]).contains("duplicate"));
    assert!(build_error(&table, vec![0, 1, 3]).contains("range"));

    let wrong_rows = CompleteTable {
        ninputs: 2,
        noutputs: 1,
        outputs: vec![vec![false]; 3],
    };
    assert!(build_error(&wrong_rows, vec![0, 1]).contains("rows"));
    let wrong_width = CompleteTable {
        ninputs: 1,
        noutputs: 2,
        outputs: vec![vec![false], vec![true]],
    };
    assert!(build_error(&wrong_width, vec![0]).contains("width"));
    let zero_outputs = CompleteTable {
        ninputs: 0,
        noutputs: 0,
        outputs: vec![Vec::new()],
    };
    assert!(build_error(&zero_outputs, Vec::new()).contains("at least one output"));
    let overflowing = CompleteTable {
        ninputs: usize::BITS as usize,
        noutputs: 0,
        outputs: Vec::new(),
    };
    assert!(build_error(&overflowing, Vec::new()).contains("dimensions"));
}

#[test]
fn evaluate_all_returns_the_complete_table_in_logical_mask_order() {
    let table = CompleteTable::from_fn(3, 3, |mask| {
        let x = mask & 1;
        let y = (mask >> 1) & 3;
        x + y
    });
    let oracle = OxiddForest::build(&table, vec![2, 0, 1]).unwrap();
    assert_eq!(oracle.evaluate_all().unwrap(), table.outputs);
}

#[test]
fn oxidd_ite_cofactors_are_high_then_low_and_complements_are_identity() {
    let manager = oxidd::bcdd::new_manager(128, 64, 1);
    let (condition, high, low) = manager.with_manager_exclusive(|m| {
        m.add_vars(2);
        (
            BCDDFunction::var(m, 0).unwrap(),
            BCDDFunction::var(m, 1).unwrap(),
            BCDDFunction::not_var(m, 1).unwrap(),
        )
    });

    let mux = condition.ite(&high, &low).unwrap();
    let (actual_high, actual_low) = mux.cofactors().unwrap();
    assert!(actual_high == high);
    assert!(actual_low == low);
    assert!(mux.not().unwrap().not().unwrap() == mux);

    for condition_value in [false, true] {
        for branch_value in [false, true] {
            assert_eq!(
                mux.eval([(0, condition_value), (1, branch_value)]),
                if condition_value {
                    branch_value
                } else {
                    !branch_value
                }
            );
        }
    }
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
fn all_v1_families_match_custom_robdds_and_complete_tables_for_two_orders() {
    let total_started = Instant::now();
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
            let custom = SharedRobdd::build(&table, order.clone()).unwrap();
            let custom_rows = (0..table.outputs.len())
                .map(|mask| custom.evaluate_mask(mask).unwrap())
                .collect::<Vec<_>>();
            assert_eq!(custom_rows, table.outputs, "{label} {order_name} custom");

            // Keep only this case's manager alive: each iteration drops the oracle
            // before constructing the next grouped/interleaved case.
            let oracle = OxiddForest::build(&table, order).unwrap();
            let oracle_rows = oracle.evaluate_all().unwrap();
            assert_eq!(oracle_rows, table.outputs, "{label} {order_name} OxiDD");
            assert_eq!(
                oracle_rows, custom_rows,
                "{label} {order_name} differential"
            );
            assert_eq!(
                oracle.shared_node_count(),
                custom.shared_node_count(),
                "{label} {order_name} shared union"
            );
            let root_counts = (0..output_bits)
                .map(|output| oracle.node_count(output).unwrap())
                .collect::<Vec<_>>();
            println!(
                "family={label} order={order_name} custom_nodes={} oxidd_nodes={} root_counts={root_counts:?} elapsed_ms={}",
                custom.shared_node_count(),
                oracle.shared_node_count(),
                case_started.elapsed().as_millis()
            );
        }
    }
    println!(
        "oxidd_release_differential_total_ms={}",
        total_started.elapsed().as_millis()
    );
}
