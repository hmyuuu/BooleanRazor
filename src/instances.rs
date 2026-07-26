#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Family {
    Add,
    AbsDiff,
    Multiply,
    SumSquares,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InstanceSpec {
    pub slug: &'static str,
    pub input_bits: usize,
    pub output_bits: usize,
    pub family: Family,
    pub commitment: &'static str,
}

pub const MYSTERY_INSTANCES: [InstanceSpec; 4] = [
    InstanceSpec {
        slug: "mystery-A",
        input_bits: 16,
        output_bits: 9,
        family: Family::Add,
        commitment: "51e3f026def41778ecd0d7dcaee9f970b9937488e6716891932b73824c16d4c7",
    },
    InstanceSpec {
        slug: "mystery-B",
        input_bits: 14,
        output_bits: 7,
        family: Family::AbsDiff,
        commitment: "e2c9d0e23ee36bfc0f12d7f39fdfe2ca5a8abe8eb194fec56500733694b75c28",
    },
    InstanceSpec {
        slug: "mystery-C",
        input_bits: 12,
        output_bits: 12,
        family: Family::Multiply,
        commitment: "c7b37413844bf0b10ebad0010046469f500354a22cc2ba95cbe42709f8e8337d",
    },
    InstanceSpec {
        slug: "mystery-D",
        input_bits: 10,
        output_bits: 11,
        family: Family::SumSquares,
        commitment: "b445a717483303fa3c5d8a1f7abe81888b267b7c472121c9c464fa9766808580",
    },
];

pub fn semantic_output(family: Family, _n: usize, x: u64, y: u64) -> u64 {
    match family {
        Family::Add => x + y,
        Family::AbsDiff => x.abs_diff(y),
        Family::Multiply => x * y,
        Family::SumSquares => x * x + y * y,
    }
}
