use occam_circuit_hmyuuu::netlist::Netlist;
use occam_circuit_hmyuuu::xag::{Circuit, Xag};

#[test]
fn xag_simplifies_and_hash_conses_in_challenge_metric() {
    let mut g = Xag::new(2);
    let a = g.input(0);
    let b = g.input(1);

    assert_eq!(g.xor(a, g.f()), a);
    assert_eq!(g.xor(a, g.t()), !a);
    assert_eq!(g.xor(a, a), g.f());
    assert_eq!(g.xor(a, !a), g.t());
    assert_eq!(g.and(a, g.f()), g.f());
    assert_eq!(g.and(a, g.t()), a);
    assert_eq!(g.and(a, a), a);
    assert_eq!(g.and(a, !a), g.f());

    let p = g.xor(a, b);
    assert_eq!(p, g.xor(b, a));
    assert_eq!(!p, g.xor(!a, b));
    assert_eq!(!p, g.xor(a, !b));
    assert_eq!(p, g.xor(!a, !b));
    let q = g.and(a, b);
    assert_eq!(q, g.and(b, a));
    assert_eq!(g.reachable_gate_count(&[p, q]), 2);
    assert_eq!(g.reachable_gate_count(&[p, p, !p]), 1);
}

#[test]
fn netlist_serialization_is_canonical_and_omits_dead_gates() {
    let mut g = Xag::new(2);
    let a = g.input(0);
    let b = g.input(1);
    let dead = g.and(a, b);
    let out = g.xor(a, b);
    assert_ne!(dead, out);

    let circuit = Circuit::new(g, vec![out]);
    let first = circuit.to_netlist().unwrap();
    let second = circuit.to_netlist().unwrap();
    assert_eq!(first, "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n");
    assert_eq!(first, second);
}

#[test]
fn xag_evaluates_two_input_algebra_exhaustively() {
    let mut g = Xag::new(2);
    let a = g.input(0);
    let b = g.input(1);
    let ab_and = g.and(a, b);
    let ab_xor = g.xor(a, b);
    let ab_or = g.or(a, b);
    let circuit = Circuit::new(g, vec![ab_and, ab_xor, ab_or, !ab_or]);

    for mask in 0..4 {
        let a_value = mask & 1 != 0;
        let b_value = mask & 2 != 0;
        assert_eq!(
            circuit.evaluate(&[a_value, b_value]).unwrap(),
            vec![
                a_value & b_value,
                a_value ^ b_value,
                a_value | b_value,
                !(a_value | b_value),
            ]
        );
        let expected_u64 = u64::from(a_value & b_value)
            | (u64::from(a_value ^ b_value) << 1)
            | (u64::from(a_value | b_value) << 2)
            | (u64::from(!(a_value | b_value)) << 3);
        assert_eq!(
            circuit.evaluate_u64(&[a_value, b_value]).unwrap(),
            expected_u64
        );
    }
    assert!(circuit.evaluate(&[false]).unwrap_err().contains("2 inputs"));
}

#[test]
fn mux_compaction_preserves_three_input_truth_table() {
    let mut g = Xag::new(3);
    let select = g.input(0);
    let then_value = g.input(1);
    let else_value = g.input(2);
    let dead = g.xor(select, then_value);
    let mux = g.mux(select, then_value, else_value);
    assert_ne!(dead, mux);

    let (compact, outputs) = g.compact(&[mux, !mux]);
    assert_eq!(
        compact.reachable_gate_count(&outputs),
        g.reachable_gate_count(&[mux, !mux])
    );
    let compact_circuit = Circuit::new(compact, outputs);
    for mask in 0..8 {
        let values = [mask & 1 != 0, mask & 2 != 0, mask & 4 != 0];
        let expected = if values[0] { values[1] } else { values[2] };
        assert_eq!(
            compact_circuit.evaluate(&values).unwrap(),
            vec![expected, !expected]
        );
    }
}

#[test]
fn serialized_netlist_round_trips_all_assignments_and_only_counts_live_union() {
    let mut g = Xag::new(3);
    let a = g.input(0);
    let b = g.input(1);
    let c = g.input(2);
    let shared = g.xor(a, b);
    let first = g.and(shared, c);
    let second = g.or(shared, c);
    let _dead = g.and(a, b);
    let reachable = g.reachable_gate_count(&[first, second]);
    let circuit = Circuit::new(g, vec![first, second]);
    let text = circuit.to_netlist().unwrap();
    let netlist = Netlist::parse(&text).unwrap();

    assert_eq!(reachable, 3);
    assert_eq!(
        text.lines().filter(|line| line.contains(" = ")).count(),
        reachable
    );
    assert!(!text.contains(" OR "));
    assert!(!text.contains(" NAND "));
    assert!(!text.contains(" NOR "));
    assert!(!text.contains(" XNOR "));

    for mask in 0..8 {
        let values = [mask & 1 != 0, mask & 2 != 0, mask & 4 != 0];
        assert_eq!(
            netlist.evaluate(&values).unwrap(),
            circuit.evaluate(&values).unwrap()
        );
    }
}

#[test]
fn parser_accepts_all_six_official_binary_operations() {
    let text = "\
INPUTS 2
w1 = AND x1 x2
w2 = OR x1 x2
w3 = XOR x1 x2
w4 = NAND x1 x2
w5 = NOR x1 x2
w6 = XNOR x1 x2
OUTPUTS w1 w2 w3 w4 w5 w6
";
    let netlist = Netlist::parse(text).unwrap();

    for mask in 0..4 {
        let a = mask & 1 != 0;
        let b = mask & 2 != 0;
        assert_eq!(
            netlist.evaluate(&[a, b]).unwrap(),
            vec![a & b, a | b, a ^ b, !(a & b), !(a | b), !(a ^ b)]
        );
    }
}

#[test]
fn constant_outputs_materialize_exactly_one_canonical_xor() {
    let g = Xag::new(1);
    let circuit = Circuit::new(g, vec![Xag::constant(false), Xag::constant(true)]);
    let text = circuit.to_netlist().unwrap();
    assert_eq!(text, "INPUTS 1\nw1 = XOR x1 x1\nOUTPUTS w1 ~w1\n");
    assert_eq!(
        Netlist::parse(&text).unwrap().evaluate(&[false]).unwrap(),
        vec![false, true]
    );
}

#[test]
fn parser_rejects_invalid_width_references_and_noncanonical_layout() {
    assert!(
        Netlist::parse("INPUTS two\nOUTPUTS x1\n")
            .unwrap_err()
            .contains("INPUTS")
    );
    assert!(
        Netlist::parse("INPUTS 1\nw1 = XOR x1 x2\nOUTPUTS w1\n")
            .unwrap_err()
            .contains("input")
    );
    assert!(
        Netlist::parse("INPUTS 1\nw2 = XOR x1 x1\nOUTPUTS w2\n")
            .unwrap_err()
            .contains("w1")
    );
    assert!(
        Netlist::parse("INPUTS 1\nw1 = IMPLIES x1 x1\nOUTPUTS w1\n")
            .unwrap_err()
            .contains("operation")
    );
    assert!(
        Netlist::parse("INPUTS 1\nw1 = XOR x1 x1\n")
            .unwrap_err()
            .contains("OUTPUTS")
    );
}
