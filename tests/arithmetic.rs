use occam_circuit_hmyuuu::arithmetic::synthesize_family;
use occam_circuit_hmyuuu::instances::{Family, semantic_output};
use occam_circuit_hmyuuu::netlist::Netlist;

fn input_bits(n: usize, x: u64, y: u64) -> Vec<bool> {
    let mut input = Vec::with_capacity(2 * n);
    input.extend((0..n).map(|i| ((x >> i) & 1) != 0));
    input.extend((0..n).map(|i| ((y >> i) & 1) != 0));
    input
}

fn exhaustive(family: Family, n: usize, output_width: usize, expected_gates: usize) {
    let circuit = synthesize_family(family, n, output_width).unwrap();
    let first = circuit.to_netlist().unwrap();
    let second = circuit.to_netlist().unwrap();
    assert_eq!(
        first, second,
        "{family:?} serialization must be deterministic"
    );

    let parsed = Netlist::parse(&first).unwrap();
    assert_eq!(
        first.lines().filter(|line| line.contains(" = ")).count(),
        expected_gates,
        "{family:?} reachable gate upper bound changed"
    );
    assert_eq!(
        first
            .lines()
            .find(|line| line.starts_with("OUTPUTS"))
            .unwrap()
            .split_whitespace()
            .count()
            - 1,
        output_width,
        "{family:?} output width changed"
    );

    for x in 0..(1u64 << n) {
        for y in 0..(1u64 << n) {
            let input = input_bits(n, x, y);
            let expected = semantic_output(family, n, x, y);
            let got = circuit.evaluate_u64(&input).unwrap();
            assert_eq!(got, expected, "{family:?} x={x} y={y}");

            let round_trip = parsed.evaluate(&input).unwrap();
            let round_trip = round_trip
                .iter()
                .enumerate()
                .fold(0, |value, (i, bit)| value | (u64::from(*bit) << i));
            assert_eq!(
                round_trip, expected,
                "{family:?} parsed round trip x={x} y={y}"
            );
        }
    }
}

#[test]
fn add_n8_is_exact() {
    exhaustive(Family::Add, 8, 9, 37);
}

#[test]
fn absdiff_n7_is_exact() {
    exhaustive(Family::AbsDiff, 7, 7, 49);
}

#[test]
fn multiply_n6_is_exact() {
    exhaustive(Family::Multiply, 6, 12, 168);
}

#[test]
fn sum_squares_n5_is_exact() {
    exhaustive(Family::SumSquares, 5, 11, 127);
}

#[test]
fn declared_output_width_is_enforced() {
    assert!(synthesize_family(Family::Add, 8, 8).is_err());
    assert!(synthesize_family(Family::AbsDiff, 7, 8).is_err());
    assert!(synthesize_family(Family::Multiply, 6, 11).is_err());
    assert!(synthesize_family(Family::SumSquares, 5, 10).is_err());
}

#[test]
fn extreme_widths_return_stable_errors_before_allocation() {
    for family in [
        Family::Add,
        Family::AbsDiff,
        Family::Multiply,
        Family::SumSquares,
    ] {
        assert_eq!(
            synthesize_family(family, usize::MAX, 0).unwrap_err(),
            "arithmetic width overflow",
            "{family:?}"
        );
    }
}
