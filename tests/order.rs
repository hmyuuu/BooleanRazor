use std::path::Path;
use std::process::{Command, Output};

use occam_circuit_hmyuuu::bits::encode_lsb;
use occam_circuit_hmyuuu::instances::{complete_table, instance_by_slug};
use occam_circuit_hmyuuu::order::{
    OrderScore, OrderScorer, adjacent_hill_climb, adjacent_hill_climb_with_callback, beam_search,
    beam_search_with_callback, search_csv_bytes, seed_orders,
};
use occam_circuit_hmyuuu::robdd::SharedRobdd;
use occam_circuit_hmyuuu::table::CompleteTable;

fn two_bit_add_table() -> CompleteTable {
    CompleteTable::from_fn(4, 3, |mask| (mask & 3) + ((mask >> 2) & 3))
}

#[test]
fn order_score_ranks_xag_then_bdd_then_numeric_order() {
    let scores = vec![
        OrderScore {
            order: vec![0, 1],
            bdd_nodes: 1,
            xag_gates: 9,
        },
        OrderScore {
            order: vec![1, 0],
            bdd_nodes: 99,
            xag_gates: 8,
        },
        OrderScore {
            order: vec![1, 0],
            bdd_nodes: 4,
            xag_gates: 8,
        },
        OrderScore {
            order: vec![0, 1],
            bdd_nodes: 4,
            xag_gates: 8,
        },
    ];
    let mut sorted = scores.clone();
    sorted.sort_by(|left, right| left.ranking_key().cmp(&right.ranking_key()));
    assert_eq!(
        sorted,
        vec![
            scores[3].clone(),
            scores[2].clone(),
            scores[1].clone(),
            scores[0].clone()
        ]
    );
}

#[test]
fn scorer_matches_direct_robdd_xag_and_exhaustive_semantics() {
    let table = two_bit_add_table();
    let order = vec![0, 2, 1, 3];
    let forest = SharedRobdd::build(&table, order.clone()).unwrap();
    let circuit = forest.extract_xag().unwrap();

    let mut scorer = OrderScorer::new(&table).unwrap();
    let score = scorer.score(&order).unwrap();
    assert_eq!(score.bdd_nodes, forest.shared_node_count());
    assert_eq!(score.xag_gates, circuit.reachable_gate_count().unwrap());
    assert_eq!(circuit.evaluate_all().unwrap(), table.outputs);
    assert_eq!(scorer.unique_evaluations(), 1);
}

#[test]
fn scorer_cache_is_keyed_by_the_full_order() {
    let table = two_bit_add_table();
    let mut scorer = OrderScorer::new(&table).unwrap();
    let first = scorer.score(&[0, 1, 2, 3]).unwrap();
    let again = scorer.score(&[0, 1, 2, 3]).unwrap();
    assert_eq!(first, again);
    assert_eq!(scorer.unique_evaluations(), 1);

    scorer.score(&[0, 2, 1, 3]).unwrap();
    assert_eq!(scorer.unique_evaluations(), 2);
}

#[test]
fn scorer_rejects_malformed_orders_and_tables_without_counting_them() {
    let table = two_bit_add_table();
    let mut scorer = OrderScorer::new(&table).unwrap();
    for (order, message) in [
        (vec![0, 1, 2], "length"),
        (vec![0, 1, 2, 4], "out of range"),
        (vec![0, 1, 1, 3], "duplicate"),
    ] {
        assert!(scorer.score(&order).unwrap_err().contains(message));
    }
    assert_eq!(scorer.unique_evaluations(), 0);

    let wrong_rows = CompleteTable {
        ninputs: 2,
        noutputs: 1,
        outputs: vec![vec![false]],
    };
    assert!(OrderScorer::new(&wrong_rows).unwrap_err().contains("rows"));
    let wrong_width = CompleteTable {
        ninputs: 1,
        noutputs: 2,
        outputs: vec![vec![false], vec![true]],
    };
    assert!(
        OrderScorer::new(&wrong_width)
            .unwrap_err()
            .contains("output width")
    );
    let no_outputs = CompleteTable {
        ninputs: 0,
        noutputs: 0,
        outputs: vec![vec![]],
    };
    assert!(
        OrderScorer::new(&no_outputs)
            .unwrap_err()
            .contains("at least one output")
    );
    let overflow = CompleteTable {
        ninputs: usize::MAX,
        noutputs: 1,
        outputs: vec![],
    };
    assert!(
        OrderScorer::new(&overflow)
            .unwrap_err()
            .contains("overflow")
    );
}

#[test]
fn seeds_have_exact_sequence_and_stable_first_occurrence_deduplication() {
    assert_eq!(seed_orders(0).unwrap(), vec![vec![]]);
    assert_eq!(seed_orders(1).unwrap(), vec![vec![0, 1], vec![1, 0]]);
    assert_eq!(
        seed_orders(2).unwrap(),
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
    assert!(seed_orders(usize::MAX).unwrap_err().contains("overflow"));
}

#[test]
fn adjacent_hill_climb_uses_best_adjacent_improvement_and_obeys_hard_bound() {
    let table = two_bit_add_table();
    let start = vec![0, 1, 2, 3];

    let mut zero_scorer = OrderScorer::new(&table).unwrap();
    let zero = adjacent_hill_climb(&mut zero_scorer, &start, 0).unwrap();
    assert_eq!(zero.finalists.len(), 1);
    assert_eq!(zero.finalists[0].order, start);
    assert_eq!(zero.rounds_completed, 0);
    assert_eq!(zero_scorer.unique_evaluations(), 1);

    let mut scorer = OrderScorer::new(&table).unwrap();
    let one = adjacent_hill_climb(&mut scorer, &start, 1).unwrap();
    let mut direct = OrderScorer::new(&table).unwrap();
    let start_score = direct.score(&start).unwrap();
    let best_neighbor = (0..start.len() - 1)
        .map(|index| {
            let mut order = start.clone();
            order.swap(index, index + 1);
            direct.score(&order).unwrap()
        })
        .min()
        .unwrap();
    let expected = if best_neighbor < start_score {
        best_neighbor
    } else {
        start_score
    };
    assert_eq!(one.finalists[0], expected);
    assert!(one.rounds_completed <= 1);
    assert!(scorer.unique_evaluations() <= 1 + start.len() - 1);
    if one.finalists[0].order != start {
        let differences = one.finalists[0]
            .order
            .iter()
            .zip(&start)
            .enumerate()
            .filter_map(|(index, (left, right))| (left != right).then_some(index))
            .collect::<Vec<_>>();
        assert_eq!(differences.len(), 2);
        assert_eq!(differences[1], differences[0] + 1);
    }
    assert!(one.history.windows(2).all(|pair| {
        pair[1].best.ranking_key() < pair[0].best.ranking_key() && pair[1].round > pair[0].round
    }));
}

#[test]
fn beam_is_elitist_bounded_stable_and_deduplicates_seeds_and_neighbors() {
    let table = two_bit_add_table();
    let duplicated = vec![vec![0, 1, 2, 3], vec![0, 1, 2, 3], vec![0, 2, 1, 3]];
    let mut scorer = OrderScorer::new(&table).unwrap();
    let result = beam_search(&mut scorer, &duplicated, 2, 1).unwrap();
    let mut initial_scorer = OrderScorer::new(&table).unwrap();
    let initial_best = duplicated
        .iter()
        .map(|seed| initial_scorer.score(seed).unwrap())
        .min()
        .unwrap();
    assert!(result.finalists[0] <= initial_best);
    assert!(result.finalists.len() <= 2);
    assert!(
        result
            .finalists
            .windows(2)
            .all(|pair| pair[0].ranking_key() <= pair[1].ranking_key())
    );
    assert_ne!(result.finalists[0].order, result.finalists[1].order);
    assert!(result.rounds_completed <= 1);
    assert!(scorer.unique_evaluations() <= 2 + 2 * (table.ninputs - 1));
    assert!(result.history.windows(2).all(|pair| {
        pair[1].best.ranking_key() < pair[0].best.ranking_key() && pair[1].round > pair[0].round
    }));
}

#[test]
fn beam_round_zero_plateau_and_argument_errors_are_exact() {
    let table = two_bit_add_table();
    let initial_seeds = vec![vec![0, 1, 2, 3], vec![0, 2, 1, 3]];
    let mut initial_scorer = OrderScorer::new(&table).unwrap();
    let initial = beam_search(&mut initial_scorer, &initial_seeds, 1, 0).unwrap();
    assert_eq!(initial.rounds_completed, 0);
    assert_eq!(initial_scorer.unique_evaluations(), 2);
    assert_eq!(initial.history.len(), 1);

    let constant = CompleteTable::from_fn(0, 1, |_| 0);
    let seeds = vec![vec![], vec![]];
    let mut scorer = OrderScorer::new(&constant).unwrap();
    let result = beam_search(&mut scorer, &seeds, 1, 99).unwrap();
    assert_eq!(result.finalists.len(), 1);
    assert_eq!(result.history.len(), 1);
    assert_eq!(result.rounds_completed, 1);
    assert_eq!(scorer.unique_evaluations(), 1);

    let mut scorer = OrderScorer::new(&table).unwrap();
    assert!(
        beam_search(&mut scorer, &[], 1, 1)
            .unwrap_err()
            .contains("seed")
    );
    assert!(
        beam_search(&mut scorer, &[vec![0, 1, 2, 3]], 0, 1)
            .unwrap_err()
            .contains("beam width")
    );
    assert!(
        beam_search(&mut scorer, &[vec![0, 1, 1, 3]], 1, 1)
            .unwrap_err()
            .contains("duplicate")
    );
}

#[test]
fn callback_variants_emit_recorded_progress_and_propagate_errors() {
    let table = two_bit_add_table();
    let mut scorer = OrderScorer::new(&table).unwrap();
    let mut callbacks = Vec::new();
    let result =
        beam_search_with_callback(&mut scorer, &seed_orders(2).unwrap(), 4, 2, |progress| {
            callbacks.push(progress.clone());
            Ok(())
        })
        .unwrap();
    assert_eq!(callbacks, result.history);

    let mut scorer = OrderScorer::new(&table).unwrap();
    let error = adjacent_hill_climb_with_callback(&mut scorer, &[0, 1, 2, 3], 2, |_| {
        Err("callback stopped".into())
    })
    .unwrap_err();
    assert_eq!(error, "callback stopped");
    assert_eq!(scorer.unique_evaluations(), 1);

    let mut scorer = OrderScorer::new(&table).unwrap();
    let error = beam_search_with_callback(&mut scorer, &seed_orders(2).unwrap(), 4, 2, |_| {
        Err("beam callback stopped".into())
    })
    .unwrap_err();
    assert_eq!(error, "beam callback stopped");
}

#[test]
fn search_is_stable_and_scores_xag_not_only_bdd_nodes() {
    let table = CompleteTable::from_fn(6, 6, |mask| {
        let x = mask & 7;
        let y = (mask >> 3) & 7;
        x + y
    });
    let seeds = seed_orders(3).unwrap();
    let mut first = OrderScorer::new(&table).unwrap();
    let mut second = OrderScorer::new(&table).unwrap();
    let a = beam_search(&mut first, &seeds, 8, 3).unwrap();
    let b = beam_search(&mut second, &seeds, 8, 3).unwrap();
    assert_eq!(a, b);
    assert!(
        a.finalists
            .windows(2)
            .all(|w| w[0].ranking_key() <= w[1].ranking_key())
    );
}

#[test]
fn search_csv_is_byte_stable_with_exact_lf_rows() {
    let finalists = vec![
        OrderScore {
            order: vec![0, 2, 1, 3],
            bdd_nodes: 17,
            xag_gates: 11,
        },
        OrderScore {
            order: vec![1, 3, 0, 2],
            bdd_nodes: 19,
            xag_gates: 12,
        },
    ];
    let expected = b"instance,rank,xag_gates,bdd_nodes,order\n\
mystery-A,0,11,17,0:2:1:3\n\
mystery-A,1,12,19,1:3:0:2\n";
    assert_eq!(search_csv_bytes("mystery-A", &finalists).unwrap(), expected);
    assert_eq!(
        search_csv_bytes("mystery-A", &finalists).unwrap(),
        search_csv_bytes("mystery-A", &finalists).unwrap()
    );
    assert!(
        search_csv_bytes("bad,slug", &finalists)
            .unwrap_err()
            .contains("instance")
    );
}

#[test]
fn instance_helpers_are_exact_and_semantic() {
    let spec = instance_by_slug("mystery-C").unwrap();
    assert_eq!(spec.slug, "mystery-C");
    let table = complete_table(spec).unwrap();
    assert_eq!(table.ninputs, 12);
    assert_eq!(table.noutputs, 12);
    assert_eq!(table.outputs[63 | (63 << 6)], encode_lsb(3969, 12));
    assert!(instance_by_slug("Mystery-C").unwrap_err().contains("exact"));
}

#[test]
fn cli_rejects_strict_flag_and_slug_errors_before_data_access() {
    let binary = env!("CARGO_BIN_EXE_occam-circuit-hmyuuu");
    for (arguments, expected) in [
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-A",
                "--beam",
                "0",
                "--rounds",
                "1",
            ],
            "beam width",
        ),
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-A",
                "--beam",
                "1",
                "--rounds",
                "0",
            ],
            "round count",
        ),
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-A",
                "--beam",
                "1",
                "--beam",
                "2",
                "--rounds",
                "1",
            ],
            "duplicate flag",
        ),
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-A",
                "--beam",
                "1",
                "--rounds",
                "1",
                "--extra",
                "2",
            ],
            "unknown flag",
        ),
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-a",
                "--beam",
                "1",
                "--rounds",
                "1",
            ],
            "exact mystery slug",
        ),
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-A",
                "--beam",
                "many",
                "--rounds",
                "1",
            ],
            "nonnegative integer",
        ),
        (
            vec![
                "search-order",
                "/does/not/exist",
                "mystery-A",
                "--beam",
                "1",
            ],
            "missing required flag --rounds",
        ),
    ] {
        let output = Command::new(binary).args(arguments).output().unwrap();
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
        assert!(
            String::from_utf8_lossy(&output.stderr).contains(expected),
            "stderr did not contain {expected:?}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
}

fn run_search(binary: &str, data_root: &Path) -> Output {
    Command::new(binary)
        .args(["search-order"])
        .arg(data_root)
        .args(["mystery-D", "--beam", "3", "--rounds", "1"])
        .output()
        .unwrap()
}

#[test]
fn cli_search_is_byte_deterministic_and_separates_csv_from_progress() {
    let Some(data_root) = std::env::var_os("OCCAM_V1_ROOT") else {
        println!("skipped CLI search test: OCCAM_V1_ROOT unset");
        return;
    };
    let binary = env!("CARGO_BIN_EXE_occam-circuit-hmyuuu");
    let first = run_search(binary, Path::new(&data_root));
    let second = run_search(binary, Path::new(&data_root));
    assert!(first.status.success());
    assert_eq!(first.stdout, second.stdout);
    assert_eq!(first.stderr, second.stderr);
    let stdout = String::from_utf8(first.stdout).unwrap();
    assert!(stdout.starts_with("instance,rank,xag_gates,bdd_nodes,order\n"));
    assert!(
        stdout
            .lines()
            .skip(1)
            .all(|line| line.starts_with("mystery-D,"))
    );
    assert!(!stdout.contains("round="));
    let stderr = String::from_utf8(first.stderr).unwrap();
    assert!(stderr.contains("mystery-D round=0"));
    assert!(stderr.contains("mystery-D complete rounds=1 finalists=3 unique_evaluations="));
    #[cfg(feature = "oxidd-oracle")]
    assert_eq!(stderr.matches("oxidd finalist=").count(), 3);
}
