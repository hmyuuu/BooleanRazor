use occam_circuit_hmyuuu::bits::{decode_lsb, encode_lsb, encode_lsb_checked, parse_bits};
use occam_circuit_hmyuuu::table::{
    CompleteTable, InputTable, PartialTable, prediction_csv_bytes, sha256_hex,
};

#[test]
fn lsb_first_round_trip_matches_release_example() {
    let bits = parse_bits("1011", 4).unwrap();
    assert_eq!(decode_lsb(&bits), 13);
    assert_eq!(encode_lsb(13, 4), bits);
}

#[test]
fn prediction_bytes_have_exact_header_order_and_final_newline() {
    let inputs = InputTable::parse("input\n0000\n1000\n", 4).unwrap();
    let table = CompleteTable::from_fn(4, 3, |mask| (mask & 3) + ((mask >> 2) & 3));
    let bytes = prediction_csv_bytes(&inputs, &table).unwrap();
    assert_eq!(bytes, b"input,output\n0000,000\n1000,100\n");
}

#[test]
fn bits_reject_wrong_width_and_non_binary_characters() {
    assert!(
        parse_bits("101", 4)
            .unwrap_err()
            .contains("expected 4 bits")
    );
    assert!(parse_bits("10x1", 4).unwrap_err().contains("binary"));
}

#[test]
fn checked_lsb_encoding_rejects_overflow() {
    assert!(
        encode_lsb_checked(8, 3)
            .unwrap_err()
            .contains("does not fit")
    );
}

#[test]
fn partial_table_rejects_malformed_rows() {
    assert!(
        PartialTable::parse("input\n000,00\n", 3, 2)
            .unwrap_err()
            .contains("input,output")
    );
    assert!(
        PartialTable::parse("input,output\n00,0x\n", 2, 2)
            .unwrap_err()
            .contains("binary")
    );
    assert!(
        PartialTable::parse("input,output\n00,0\n", 3, 1)
            .unwrap_err()
            .contains("expected 3 bits")
    );
    assert!(
        PartialTable::parse("input,output\n00,0\n00,1\n", 2, 1)
            .unwrap_err()
            .contains("conflicting output")
    );
    assert!(
        PartialTable::parse("input,output\n", 2, 1)
            .unwrap_err()
            .contains("at least one row")
    );
    assert!(
        PartialTable::parse("input,output\n00,0,1\n", 2, 1)
            .unwrap_err()
            .contains("one comma")
    );
}

#[test]
fn input_table_rejects_wrong_header_width_and_missing_rows() {
    assert!(
        InputTable::parse("inputs\n00\n", 2)
            .unwrap_err()
            .contains("input")
    );
    assert!(
        InputTable::parse("input\n0\n", 2)
            .unwrap_err()
            .contains("expected 2 bits")
    );
    assert!(
        InputTable::parse("input\n", 2)
            .unwrap_err()
            .contains("at least one row")
    );
}

#[test]
fn predictions_reject_table_width_mismatches() {
    let inputs = InputTable::parse("input\n00\n", 2).unwrap();
    let completed = CompleteTable::from_fn(3, 1, |_| 0);
    assert!(
        prediction_csv_bytes(&inputs, &completed)
            .unwrap_err()
            .contains("input width does not match")
    );
}

#[test]
fn sha256_hex_is_lowercase_digest_of_exact_bytes() {
    assert_eq!(
        sha256_hex(b"abc"),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
}
