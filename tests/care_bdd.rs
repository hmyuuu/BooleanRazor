use occam_circuit_hmyuuu::bits::encode_lsb;
use occam_circuit_hmyuuu::care_bdd::{
    BlindOrderScorer, BlindScore, EmptyCarePolicy, blind_adjacent_hill_climb, blind_beam_search,
    blind_beam_search_with_callback, blind_search_csv_bytes, blind_seed_orders, complete_care_set,
    cross_validate_care_set,
};
use occam_circuit_hmyuuu::netlist::Netlist;
#[cfg(feature = "oxidd-oracle")]
use occam_circuit_hmyuuu::oxidd_oracle::OxiddForest;
use occam_circuit_hmyuuu::reblind::{PublicInstance, visible_folds};
use occam_circuit_hmyuuu::table::{CompleteTable, PartialTable};

const SEED: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

fn partial_from_masks<F>(
    ninputs: usize,
    noutputs: usize,
    masks: impl IntoIterator<Item = usize>,
    mut function: F,
) -> PartialTable
where
    F: FnMut(usize) -> usize,
{
    PartialTable {
        ninputs,
        noutputs,
        rows: masks
            .into_iter()
            .map(|mask| {
                (
                    encode_lsb(mask as u64, ninputs),
                    encode_lsb(function(mask) as u64, noutputs),
                )
            })
            .collect(),
    }
}

#[test]
fn reuse_sibling_completes_unseen_branches_and_preserves_every_care_row() {
    let partial = PartialTable::parse("input,output\n00,0\n10,1\n", 2, 1).unwrap();

    let (completed, circuit) =
        complete_care_set(&partial, &[0, 1], EmptyCarePolicy::ReuseSibling).unwrap();

    assert_eq!(
        completed.outputs,
        vec![vec![false], vec![true], vec![false], vec![true]]
    );
    for (input, output) in &partial.rows {
        assert_eq!(&circuit.evaluate(input).unwrap(), output);
    }
    assert_eq!(circuit.evaluate_all().unwrap(), completed.outputs);
}

#[test]
fn empty_care_policy_controls_missing_branch_completion() {
    let partial = PartialTable::parse("input,output\n00,0\n10,1\n", 2, 1).unwrap();

    let (reuse, reuse_circuit) =
        complete_care_set(&partial, &[1, 0], EmptyCarePolicy::ReuseSibling).unwrap();
    let (zero, zero_circuit) = complete_care_set(&partial, &[1, 0], EmptyCarePolicy::Zero).unwrap();

    assert_eq!(
        reuse.outputs,
        vec![vec![false], vec![true], vec![false], vec![true]]
    );
    assert_eq!(
        zero.outputs,
        vec![vec![false], vec![true], vec![false], vec![false]]
    );
    assert_eq!(reuse_circuit.reachable_gate_count().unwrap(), 0);
    assert!(
        zero_circuit.reachable_gate_count().unwrap()
            > reuse_circuit.reachable_gate_count().unwrap()
    );
}

#[test]
fn every_order_and_policy_preserves_all_observed_rows_and_extracts_exact_xag() {
    let partial = partial_from_masks(3, 2, [0, 1, 3, 4, 6, 7], |mask| {
        ((mask & 1) ^ ((mask >> 1) & 1)) | (((mask >> 2) & 1) << 1)
    });
    for order in [
        vec![0, 1, 2],
        vec![0, 2, 1],
        vec![1, 0, 2],
        vec![1, 2, 0],
        vec![2, 0, 1],
        vec![2, 1, 0],
    ] {
        for policy in [EmptyCarePolicy::ReuseSibling, EmptyCarePolicy::Zero] {
            let (completed, circuit) = complete_care_set(&partial, &order, policy).unwrap();
            partial.validate_against(&completed).unwrap();
            assert_eq!(circuit.evaluate_all().unwrap(), completed.outputs);
        }
    }
}

#[test]
fn malformed_tables_conflicts_and_incomplete_orders_are_rejected() {
    let conflicting = PartialTable {
        ninputs: 1,
        noutputs: 1,
        rows: vec![(vec![false], vec![false]), (vec![false], vec![true])],
    };
    assert!(
        complete_care_set(&conflicting, &[0], EmptyCarePolicy::ReuseSibling)
            .unwrap_err()
            .contains("conflicting")
    );

    let partial = PartialTable::parse("input,output\n00,0\n10,1\n", 2, 1).unwrap();
    assert!(
        complete_care_set(&partial, &[0], EmptyCarePolicy::ReuseSibling)
            .unwrap_err()
            .contains("length")
    );
    assert!(
        complete_care_set(&partial, &[0, 0], EmptyCarePolicy::ReuseSibling)
            .unwrap_err()
            .contains("duplicate")
    );
    assert!(
        complete_care_set(&partial, &[0, 2], EmptyCarePolicy::ReuseSibling)
            .unwrap_err()
            .contains("range")
    );
}

#[test]
fn folds_reuse_task13_seed_rule_and_cover_visible_rows_once() {
    let partial = partial_from_masks(4, 2, 0..13, |mask| {
        ((mask & 1) ^ ((mask >> 1) & 1)) | (((mask >> 2) & 1) << 1)
    });
    let instance = PublicInstance {
        opaque_id: "synthetic-only".into(),
        input_bits: 4,
        output_bits: 2,
        train: partial.clone(),
    };
    let shared = visible_folds(&partial, SEED, 5).unwrap();

    assert_eq!(shared, instance.visible_folds(SEED, 5).unwrap());
    assert_eq!(shared, visible_folds(&partial, SEED, 5).unwrap());
    let mut covered = shared.into_iter().flatten().collect::<Vec<_>>();
    covered.sort_unstable();
    assert_eq!(covered, (0..partial.rows.len()).collect::<Vec<_>>());
    assert!(visible_folds(&partial, "00", 5).unwrap_err().contains("64"));
    assert!(
        visible_folds(
            &partial,
            "ABCDEF0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            5
        )
        .unwrap_err()
        .contains("lowercase")
    );
}

#[test]
fn cross_validation_is_deterministic_and_scores_only_visible_rows() {
    let partial = partial_from_masks(4, 2, 0..13, |mask| {
        ((mask & 1) ^ ((mask >> 1) & 1)) | (((mask >> 2) & 1) << 1)
    });
    let first = cross_validate_care_set(
        &partial,
        &[0, 2, 1, 3],
        EmptyCarePolicy::ReuseSibling,
        5,
        SEED,
    )
    .unwrap();
    let second = cross_validate_care_set(
        &partial,
        &[0, 2, 1, 3],
        EmptyCarePolicy::ReuseSibling,
        5,
        SEED,
    )
    .unwrap();

    assert_eq!(first, second);
    assert_eq!(first.validation_rows, partial.rows.len());
    assert_eq!(first.validation_bits, partial.rows.len() * partial.noutputs);
    assert!(first.validation_exact_rows <= first.validation_rows);
    assert!(first.validation_bit_correct <= first.validation_bits);
}

#[test]
fn cross_validation_does_not_require_full_domain_enumeration() {
    let ninputs = usize::BITS as usize;
    let mut high = vec![false; ninputs];
    high[0] = true;
    let partial = PartialTable {
        ninputs,
        noutputs: 1,
        rows: vec![(vec![false; ninputs], vec![false]), (high, vec![true])],
    };

    let score = cross_validate_care_set(
        &partial,
        &(0..ninputs).collect::<Vec<_>>(),
        EmptyCarePolicy::ReuseSibling,
        2,
        SEED,
    )
    .unwrap();

    assert_eq!(score.validation_rows, 2);
}

#[test]
fn blind_score_uses_exact_integer_ties_and_the_frozen_tie_break_order() {
    fn score(
        order: Vec<usize>,
        policy: EmptyCarePolicy,
        exact: (usize, usize),
        gates: usize,
        bits: (usize, usize),
        nodes: usize,
    ) -> BlindScore {
        BlindScore {
            order,
            policy,
            validation_exact_rows: exact.0,
            validation_rows: exact.1,
            validation_bit_correct: bits.0,
            validation_bits: bits.1,
            refit_xag_gates: gates,
            refit_bdd_nodes: nodes,
        }
    }

    let best_accuracy = score(vec![1, 0], EmptyCarePolicy::Zero, (3, 4), 100, (3, 4), 100);
    let worse_accuracy = score(
        vec![0, 1],
        EmptyCarePolicy::ReuseSibling,
        (2, 4),
        1,
        (4, 4),
        1,
    );
    assert!(best_accuracy < worse_accuracy);

    let mut exact_tie_breaks = vec![
        score(vec![1, 0], EmptyCarePolicy::Zero, (2, 4), 5, (6, 8), 3),
        score(
            vec![0, 1],
            EmptyCarePolicy::ReuseSibling,
            (1, 2),
            5,
            (6, 8),
            3,
        ),
        score(
            vec![1, 0],
            EmptyCarePolicy::ReuseSibling,
            (1, 2),
            4,
            (4, 8),
            9,
        ),
        score(
            vec![1, 0],
            EmptyCarePolicy::ReuseSibling,
            (1, 2),
            5,
            (7, 8),
            9,
        ),
    ];
    exact_tie_breaks.sort();
    assert_eq!(exact_tie_breaks[0].refit_xag_gates, 4);
    assert_eq!(exact_tie_breaks[1].validation_bit_correct, 7);
    assert_eq!(exact_tie_breaks[2].policy, EmptyCarePolicy::ReuseSibling);
    assert_eq!(exact_tie_breaks[2].order, vec![0, 1]);
}

#[test]
fn retained_order_scoring_is_cached_and_shared_across_complement_outputs() {
    let scalar = partial_from_masks(3, 1, 0..8, |mask| mask.count_ones() as usize & 1);
    let paired = partial_from_masks(3, 2, 0..8, |mask| {
        let parity = mask.count_ones() as usize & 1;
        parity | ((parity ^ 1) << 1)
    });
    let order = [2, 0, 1];
    let mut scalar_scorer = BlindOrderScorer::new(&scalar, 5, SEED).unwrap();
    let scalar_score = scalar_scorer
        .score_retained(&order, EmptyCarePolicy::ReuseSibling)
        .unwrap();
    let mut paired_scorer = BlindOrderScorer::new(&paired, 5, SEED).unwrap();
    let first = paired_scorer
        .score_retained(&order, EmptyCarePolicy::ReuseSibling)
        .unwrap();
    let second = paired_scorer
        .score_retained(&order, EmptyCarePolicy::ReuseSibling)
        .unwrap();

    assert_eq!(first, second);
    assert_eq!(paired_scorer.unique_cv_evaluations(), 1);
    assert_eq!(first.refit_bdd_nodes, scalar_score.refit_bdd_nodes);
}

#[test]
fn retained_score_uses_the_serialized_challenge_cost_for_constants() {
    let partial = partial_from_masks(2, 1, [0, 1, 2], |_| 1);
    let order = [0, 1];
    let mut scorer = BlindOrderScorer::new(&partial, 3, SEED).unwrap();

    let score = scorer
        .score_retained(&order, EmptyCarePolicy::ReuseSibling)
        .unwrap();
    let (_, circuit) = complete_care_set(&partial, &order, EmptyCarePolicy::ReuseSibling).unwrap();
    let emitted = Netlist::parse(&circuit.to_netlist().unwrap()).unwrap();

    assert_eq!(emitted.gate_count(), 1);
    assert_eq!(score.refit_xag_gates, emitted.gate_count());
}

#[test]
fn changing_an_unavailable_hidden_table_cannot_change_the_result() {
    let partial = partial_from_masks(3, 1, [0, 1, 4, 7], |mask| mask & 1);
    let hidden_a = CompleteTable::from_fn(3, 1, |mask| mask & 1);
    let hidden_b = CompleteTable::from_fn(3, 1, |mask| (mask >> 1) & 1);

    let a = complete_care_set(&partial, &[2, 1, 0], EmptyCarePolicy::ReuseSibling).unwrap();
    let b = complete_care_set(&partial, &[2, 1, 0], EmptyCarePolicy::ReuseSibling).unwrap();

    assert_ne!(hidden_a, hidden_b);
    assert_eq!(a.0, b.0);
    assert_eq!(
        a.1.reachable_gate_count().unwrap(),
        b.1.reachable_gate_count().unwrap()
    );
}

#[cfg(feature = "oxidd-oracle")]
#[test]
fn synthetic_oxidd_oracle_agrees_with_three_reduced_finalists() {
    let partial = partial_from_masks(3, 2, [0, 1, 3, 4, 6, 7], |mask| {
        ((mask & 1) ^ ((mask >> 1) & 1)) | (((mask >> 2) & 1) << 1)
    });
    for order in [vec![2, 0, 1], vec![0, 2, 1], vec![1, 0, 2]] {
        let (completed, circuit) =
            complete_care_set(&partial, &order, EmptyCarePolicy::ReuseSibling).unwrap();
        let oracle = OxiddForest::build(&completed, order).unwrap();

        assert_eq!(oracle.evaluate_all().unwrap(), completed.outputs);
        assert_eq!(circuit.evaluate_all().unwrap(), completed.outputs);
    }
}

#[test]
fn blind_seed_orders_are_the_predeclared_deterministic_orders() {
    assert_eq!(
        blind_seed_orders(4).unwrap(),
        vec![
            vec![0, 1, 2, 3],
            vec![1, 0, 3, 2],
            vec![0, 2, 1, 3],
            vec![1, 3, 0, 2],
            vec![3, 2, 1, 0],
            vec![2, 3, 0, 1],
            vec![3, 1, 2, 0],
            vec![2, 0, 3, 1],
        ]
    );
    assert!(blind_seed_orders(3).unwrap_err().contains("even"));
}

#[test]
fn blind_beam_search_is_deterministic_and_obeys_the_hard_evaluation_budget() {
    let partial = partial_from_masks(4, 2, 0..13, |mask| {
        ((mask & 1) ^ ((mask >> 1) & 1)) | (((mask >> 2) & 1) << 1)
    });
    let seeds = blind_seed_orders(4).unwrap();
    let mut first_scorer = BlindOrderScorer::new(&partial, 5, SEED).unwrap();
    let first = blind_beam_search(
        &mut first_scorer,
        &seeds,
        EmptyCarePolicy::ReuseSibling,
        3,
        4,
        7,
    )
    .unwrap();
    let mut second_scorer = BlindOrderScorer::new(&partial, 5, SEED).unwrap();
    let second = blind_beam_search(
        &mut second_scorer,
        &seeds,
        EmptyCarePolicy::ReuseSibling,
        3,
        4,
        7,
    )
    .unwrap();

    assert_eq!(first, second);
    assert_eq!(first_scorer.unique_cv_evaluations(), 7);
    assert!(first.budget_exhausted);
    assert!(first.finalists.len() <= 3);
    assert!(first.finalists.windows(2).all(|pair| pair[0] <= pair[1]));
    assert!(first_scorer.unique_retained_evaluations() <= first_scorer.unique_cv_evaluations());
}

#[test]
fn blind_adjacent_search_and_progress_are_stable_and_budget_bounded() {
    let partial = partial_from_masks(4, 2, 0..13, |mask| {
        ((mask & 1) ^ ((mask >> 1) & 1)) | (((mask >> 2) & 1) << 1)
    });
    let start = vec![0, 1, 2, 3];
    let mut scorer = BlindOrderScorer::new(&partial, 5, SEED).unwrap();
    let adjacent =
        blind_adjacent_hill_climb(&mut scorer, &start, EmptyCarePolicy::Zero, 5, 4).unwrap();
    assert_eq!(adjacent.finalists.len(), 1);
    assert!(scorer.unique_cv_evaluations() <= 4);

    let mut scorer = BlindOrderScorer::new(&partial, 5, SEED).unwrap();
    let mut callbacks = Vec::new();
    let result = blind_beam_search_with_callback(
        &mut scorer,
        &blind_seed_orders(4).unwrap(),
        EmptyCarePolicy::ReuseSibling,
        2,
        2,
        12,
        |progress| {
            callbacks.push(progress.clone());
            Ok(())
        },
    )
    .unwrap();
    assert_eq!(callbacks, result.history);
    assert!(result.history.windows(2).all(|pair| {
        pair[1].best < pair[0].best
            && pair[1].round > pair[0].round
            && pair[1].unique_cv_evaluations >= pair[0].unique_cv_evaluations
    }));
}

#[test]
fn blind_search_csv_is_canonical_and_byte_stable() {
    let scores = vec![
        BlindScore {
            order: vec![0, 2, 1, 3],
            policy: EmptyCarePolicy::ReuseSibling,
            validation_exact_rows: 7,
            validation_rows: 10,
            validation_bit_correct: 17,
            validation_bits: 20,
            refit_xag_gates: 11,
            refit_bdd_nodes: 13,
        },
        BlindScore {
            order: vec![1, 3, 0, 2],
            policy: EmptyCarePolicy::Zero,
            validation_exact_rows: 6,
            validation_rows: 10,
            validation_bit_correct: 16,
            validation_bits: 20,
            refit_xag_gates: 9,
            refit_bdd_nodes: 12,
        },
    ];
    let expected = b"instance,rank,validation_exact_rows,validation_rows,refit_xag_gates,validation_bit_correct,validation_bits,refit_bdd_nodes,policy,order\n\
synthetic,0,7,10,11,17,20,13,reuse-sibling,0:2:1:3\n\
synthetic,1,6,10,9,16,20,12,zero,1:3:0:2\n";
    assert_eq!(
        blind_search_csv_bytes("synthetic", &scores).unwrap(),
        expected
    );
    assert_eq!(
        blind_search_csv_bytes("synthetic", &scores).unwrap(),
        blind_search_csv_bytes("synthetic", &scores).unwrap()
    );
    assert!(
        blind_search_csv_bytes("bad,instance", &scores)
            .unwrap_err()
            .contains("instance")
    );
}
