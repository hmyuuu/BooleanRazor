/// Parse a release-order bit string: character zero is the least significant bit.
pub fn parse_bits(text: &str, width: usize) -> Result<Vec<bool>, String> {
    if text.len() != width {
        return Err(format!("expected {width} bits, got {}", text.len()));
    }

    text.bytes()
        .map(|byte| match byte {
            b'0' => Ok(false),
            b'1' => Ok(true),
            _ => Err("bits must contain only ASCII binary digits".into()),
        })
        .collect()
}

/// Render release-order bits, with the least significant bit first.
pub fn encode_bits(bits: &[bool]) -> String {
    bits.iter()
        .map(|bit| if *bit { '1' } else { '0' })
        .collect()
}

/// Decode release-order bits into an unsigned integer.
pub fn decode_lsb(bits: &[bool]) -> u64 {
    bits.iter().enumerate().fold(0u64, |value, (index, bit)| {
        if *bit && index < u64::BITS as usize {
            value | (1u64 << index)
        } else {
            value
        }
    })
}

/// Encode the low `width` bits of an unsigned integer in release order.
pub fn encode_lsb(value: u64, width: usize) -> Vec<bool> {
    (0..width)
        .map(|index| index < u64::BITS as usize && (value & (1u64 << index)) != 0)
        .collect()
}

/// Encode an unsigned integer only when it fits within `width` bits.
pub fn encode_lsb_checked(value: u64, width: usize) -> Result<Vec<bool>, String> {
    if width < u64::BITS as usize && value >= (1u64 << width) {
        return Err(format!("value {value} does not fit in {width} bits"));
    }
    Ok(encode_lsb(value, width))
}
