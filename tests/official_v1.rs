use occam_circuit_hmyuuu::instances::{Family, MYSTERY_INSTANCES, semantic_output};

#[test]
fn v1_contract_is_exact_and_fixed() {
    let dims: Vec<_> = MYSTERY_INSTANCES
        .iter()
        .map(|s| (s.slug, s.input_bits, s.output_bits, s.family))
        .collect();
    assert_eq!(
        dims,
        vec![
            ("mystery-A", 16, 9, Family::Add),
            ("mystery-B", 14, 7, Family::AbsDiff),
            ("mystery-C", 12, 12, Family::Multiply),
            ("mystery-D", 10, 11, Family::SumSquares),
        ]
    );
    assert_eq!(semantic_output(Family::Add, 8, 255, 255), 510);
    assert_eq!(semantic_output(Family::AbsDiff, 7, 3, 90), 87);
    assert_eq!(semantic_output(Family::Multiply, 6, 63, 63), 3969);
    assert_eq!(semantic_output(Family::SumSquares, 5, 31, 31), 1922);
}
