use crate::instances::Family;
use crate::xag::{Circuit, Lit, Xag};

const WIDTH_ERROR: &str = "arithmetic width overflow";

fn checked_add(left: usize, right: usize) -> Result<usize, String> {
    left.checked_add(right)
        .ok_or_else(|| WIDTH_ERROR.to_string())
}

fn checked_mul(left: usize, right: usize) -> Result<usize, String> {
    left.checked_mul(right)
        .ok_or_else(|| WIDTH_ERROR.to_string())
}

fn checked_sub(left: usize, right: usize) -> Result<usize, String> {
    left.checked_sub(right)
        .ok_or_else(|| WIDTH_ERROR.to_string())
}

fn try_reserve<T>(values: &mut Vec<T>, additional: usize) -> Result<(), String> {
    values
        .try_reserve_exact(additional)
        .map_err(|_| WIDTH_ERROR.to_string())
}

fn empty_columns(count: usize) -> Result<Vec<Vec<Lit>>, String> {
    let mut columns = Vec::new();
    try_reserve(&mut columns, count)?;
    columns.resize_with(count, Vec::new);
    Ok(columns)
}

fn half_adder(graph: &mut Xag, a: Lit, b: Lit) -> Result<(Lit, Lit), String> {
    let sum = graph.xor(a, b)?;
    let carry = graph.and(a, b)?;
    Ok((sum, carry))
}

fn full_adder(graph: &mut Xag, a: Lit, b: Lit, carry: Lit) -> Result<(Lit, Lit), String> {
    let propagate = graph.xor(a, b)?;
    let sum = graph.xor(propagate, carry)?;
    let generate = graph.and(a, b)?;
    let carried = graph.and(propagate, carry)?;
    let next = graph.xor(generate, carried)?;
    Ok((sum, next))
}

fn require_same_nonzero_width(left: &[Lit], right: &[Lit]) -> Result<usize, String> {
    if left.len() != right.len() {
        return Err(format!(
            "operand widths differ: {} and {}",
            left.len(),
            right.len()
        ));
    }
    if left.is_empty() {
        return Err("arithmetic operands must contain at least one bit".into());
    }
    Ok(left.len())
}

pub fn ripple_add(graph: &mut Xag, left: &[Lit], right: &[Lit]) -> Result<Vec<Lit>, String> {
    let width = require_same_nonzero_width(left, right)?;
    let output_width = checked_add(width, 1)?;
    let mut output = Vec::new();
    try_reserve(&mut output, output_width)?;

    let (sum, mut carry) = half_adder(graph, left[0], right[0])?;
    output.push(sum);
    for bit in 1..width {
        let (sum, next) = full_adder(graph, left[bit], right[bit], carry)?;
        output.push(sum);
        carry = next;
    }
    output.push(carry);
    Ok(output)
}

pub fn absolute_difference(
    graph: &mut Xag,
    left: &[Lit],
    right: &[Lit],
) -> Result<Vec<Lit>, String> {
    let width = require_same_nonzero_width(left, right)?;
    let mut difference = Vec::new();
    try_reserve(&mut difference, width)?;

    let first_propagate = graph.xor(left[0], right[0])?;
    difference.push(first_propagate);
    let mut borrow = graph.and(!left[0], right[0])?;

    for bit in 1..width {
        let propagate = graph.xor(left[bit], right[bit])?;
        difference.push(graph.xor(propagate, borrow)?);
        let generate = graph.and(!left[bit], right[bit])?;
        let carried = graph.and(!propagate, borrow)?;
        borrow = graph.xor(generate, carried)?;
    }

    if width == 1 {
        return Ok(difference);
    }

    let mask = borrow;
    let mut absolute = Vec::new();
    try_reserve(&mut absolute, width)?;
    absolute.push(difference[0]);
    let mut prefix = graph.and(mask, difference[0])?;
    for bit in 1..width {
        absolute.push(graph.xor(difference[bit], prefix)?);
        if checked_add(bit, 1)? < width {
            let masked_bit = graph.and(mask, difference[bit])?;
            prefix = graph.or(prefix, masked_bit)?;
        }
    }
    Ok(absolute)
}

fn reduce_heap(
    graph: &mut Xag,
    mut columns: Vec<Vec<Lit>>,
    output_width: usize,
) -> Result<Vec<Lit>, String> {
    if columns.len() <= output_width {
        let required_columns = checked_add(output_width, 1)?;
        let additional = checked_sub(required_columns, columns.len())?;
        try_reserve(&mut columns, additional)?;
        columns.resize_with(required_columns, Vec::new);
    }

    let mut output = Vec::new();
    try_reserve(&mut output, output_width)?;
    for column in 0..output_width {
        while columns[column].len() >= 3 {
            let carry_in = columns[column].pop().unwrap();
            let right = columns[column].pop().unwrap();
            let left = columns[column].pop().unwrap();
            let (sum, carry) = full_adder(graph, left, right, carry_in)?;
            columns[column].push(sum);
            columns[checked_add(column, 1)?].push(carry);
        }

        match columns[column].len() {
            0 => output.push(graph.f()),
            1 => output.push(columns[column].pop().unwrap()),
            2 => {
                let right = columns[column].pop().unwrap();
                let left = columns[column].pop().unwrap();
                let (sum, carry) = half_adder(graph, left, right)?;
                output.push(sum);
                columns[checked_add(column, 1)?].push(carry);
            }
            _ => unreachable!("full-adder reduction leaves at most two bits"),
        }
    }

    if columns[output_width..]
        .iter()
        .any(|column| !column.is_empty())
    {
        return Err(format!(
            "arithmetic result overflowed its declared {output_width}-bit width"
        ));
    }
    Ok(output)
}

pub fn unsigned_multiply(graph: &mut Xag, left: &[Lit], right: &[Lit]) -> Result<Vec<Lit>, String> {
    let width = require_same_nonzero_width(left, right)?;
    let output_width = checked_mul(2, width)?;
    let mut columns = empty_columns(checked_add(output_width, 1)?)?;
    for (left_bit, &left_lit) in left.iter().enumerate() {
        for (right_bit, &right_lit) in right.iter().enumerate() {
            columns[checked_add(left_bit, right_bit)?].push(graph.and(left_lit, right_lit)?);
        }
    }
    reduce_heap(graph, columns, output_width)
}

fn sum_squares(graph: &mut Xag, left: &[Lit], right: &[Lit]) -> Result<Vec<Lit>, String> {
    let width = require_same_nonzero_width(left, right)?;
    let output_width = checked_add(checked_mul(2, width)?, 1)?;
    let mut columns = empty_columns(checked_add(output_width, 1)?)?;

    for operand in [left, right] {
        for (bit, &literal) in operand.iter().enumerate() {
            columns[checked_mul(2, bit)?].push(literal);
        }
        for low in 0..width {
            for high in checked_add(low, 1)?..width {
                let column = checked_add(checked_add(low, high)?, 1)?;
                columns[column].push(graph.and(operand[low], operand[high])?);
            }
        }
    }
    reduce_heap(graph, columns, output_width)
}

pub fn synthesize_family(
    family: Family,
    input_width: usize,
    output_width: usize,
) -> Result<Circuit, String> {
    if input_width == 0 {
        return Err("input width must be positive".into());
    }
    let graph_input_width = checked_mul(2, input_width)?;
    let required_output_width = match family {
        Family::Add => checked_add(input_width, 1)?,
        Family::AbsDiff => input_width,
        Family::Multiply => checked_mul(2, input_width)?,
        Family::SumSquares => checked_add(checked_mul(2, input_width)?, 1)?,
    };
    if output_width != required_output_width {
        return Err(format!(
            "{family:?} with {input_width}-bit operands requires {required_output_width} outputs, got {output_width}"
        ));
    }

    let mut graph = Xag::new(graph_input_width);
    let mut left = Vec::new();
    try_reserve(&mut left, input_width)?;
    for bit in 0..input_width {
        left.push(graph.input(bit));
    }
    let mut right = Vec::new();
    try_reserve(&mut right, input_width)?;
    for bit in 0..input_width {
        right.push(graph.input(checked_add(input_width, bit)?));
    }
    let outputs = match family {
        Family::Add => ripple_add(&mut graph, &left, &right)?,
        Family::AbsDiff => absolute_difference(&mut graph, &left, &right)?,
        Family::Multiply => unsigned_multiply(&mut graph, &left, &right)?,
        Family::SumSquares => sum_squares(&mut graph, &left, &right)?,
    };
    Circuit::new(graph, outputs)
}

#[cfg(test)]
mod tests {
    use super::{full_adder, half_adder};
    use crate::xag::{Circuit, Xag};

    #[test]
    fn compressor_cells_preserve_binary_weight() {
        let mut half_graph = Xag::new(2);
        let half_a = half_graph.input(0);
        let half_b = half_graph.input(1);
        let (half_sum, half_carry) = half_adder(&mut half_graph, half_a, half_b).unwrap();
        let half = Circuit::new(half_graph, vec![half_sum, half_carry]).unwrap();
        for mask in 0u64..4 {
            let input = [mask & 1 != 0, mask & 2 != 0];
            assert_eq!(
                u64::from(input[0]) + u64::from(input[1]),
                half.evaluate_u64(&input).unwrap()
            );
        }

        let mut full_graph = Xag::new(3);
        let full_a = full_graph.input(0);
        let full_b = full_graph.input(1);
        let full_carry_in = full_graph.input(2);
        let (full_sum, full_carry) =
            full_adder(&mut full_graph, full_a, full_b, full_carry_in).unwrap();
        let full = Circuit::new(full_graph, vec![full_sum, full_carry]).unwrap();
        for mask in 0u64..8 {
            let input = [mask & 1 != 0, mask & 2 != 0, mask & 4 != 0];
            assert_eq!(
                input.iter().map(|bit| u64::from(*bit)).sum::<u64>(),
                full.evaluate_u64(&input).unwrap()
            );
        }
    }
}
