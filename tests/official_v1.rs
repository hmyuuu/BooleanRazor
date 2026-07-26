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
    let commitments: Vec<_> = MYSTERY_INSTANCES.iter().map(|s| s.commitment).collect();
    assert_eq!(
        commitments,
        vec![
            "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
            "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
            "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
            "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
        ]
    );
    assert_eq!(semantic_output(Family::Add, 8, 255, 255), 510);
    assert_eq!(semantic_output(Family::AbsDiff, 7, 3, 90), 87);
    assert_eq!(semantic_output(Family::Multiply, 6, 63, 63), 3969);
    assert_eq!(semantic_output(Family::SumSquares, 5, 31, 31), 1922);
}
