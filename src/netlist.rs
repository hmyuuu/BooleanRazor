use crate::xag::{Circuit, Op};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum NetOp {
    And,
    Or,
    Xor,
    Nand,
    Nor,
    Xnor,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Base {
    Input(usize),
    Gate(usize),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct NetLit {
    base: Base,
    inverted: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct NetGate {
    op: NetOp,
    left: NetLit,
    right: NetLit,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Netlist {
    ninputs: usize,
    gates: Vec<NetGate>,
    outputs: Vec<NetLit>,
}

impl Netlist {
    pub fn parse(text: &str) -> Result<Self, String> {
        let lines: Vec<_> = text.lines().collect();
        let first = lines
            .first()
            .ok_or_else(|| "missing INPUTS line".to_string())?;
        let header: Vec<_> = first.split_whitespace().collect();
        if header.len() != 2 || header[0] != "INPUTS" {
            return Err("expected `INPUTS <count>`".into());
        }
        let ninputs = header[1]
            .parse::<usize>()
            .map_err(|_| "INPUTS count must be a non-negative integer".to_string())?;

        let mut gates = Vec::new();
        let mut outputs = None;
        for line in &lines[1..] {
            if line.split_whitespace().next() == Some("OUTPUTS") {
                if outputs.is_some() {
                    return Err("duplicate OUTPUTS line".into());
                }
                let fields: Vec<_> = line.split_whitespace().collect();
                if fields.first() != Some(&"OUTPUTS") {
                    return Err("expected OUTPUTS followed by literals".into());
                }
                let parsed = fields[1..]
                    .iter()
                    .map(|field| parse_literal(field, ninputs, gates.len()))
                    .collect::<Result<Vec<_>, _>>()?;
                outputs = Some(parsed);
                continue;
            }
            if outputs.is_some() {
                return Err("gate definitions cannot follow OUTPUTS".into());
            }

            let fields: Vec<_> = line.split_whitespace().collect();
            if fields.len() != 5 || fields[1] != "=" {
                return Err("gate must have form `wN = OP left right`".into());
            }
            let expected_name = format!("w{}", gates.len() + 1);
            if fields[0] != expected_name {
                return Err(format!("expected gate {expected_name}"));
            }
            let op = parse_op(fields[2])?;
            let left = parse_literal(fields[3], ninputs, gates.len())?;
            let right = parse_literal(fields[4], ninputs, gates.len())?;
            gates.push(NetGate { op, left, right });
        }

        let outputs = outputs.ok_or_else(|| "missing OUTPUTS line".to_string())?;
        Ok(Self {
            ninputs,
            gates,
            outputs,
        })
    }

    pub fn evaluate(&self, inputs: &[bool]) -> Result<Vec<bool>, String> {
        if inputs.len() != self.ninputs {
            return Err(format!(
                "expected {} inputs, got {}",
                self.ninputs,
                inputs.len()
            ));
        }
        let mut gate_values = Vec::with_capacity(self.gates.len());
        for gate in &self.gates {
            let left = literal_value(gate.left, inputs, &gate_values);
            let right = literal_value(gate.right, inputs, &gate_values);
            let value = match gate.op {
                NetOp::And => left & right,
                NetOp::Or => left | right,
                NetOp::Xor => left ^ right,
                NetOp::Nand => !(left & right),
                NetOp::Nor => !(left | right),
                NetOp::Xnor => !(left ^ right),
            };
            gate_values.push(value);
        }
        Ok(self
            .outputs
            .iter()
            .map(|output| literal_value(*output, inputs, &gate_values))
            .collect())
    }
}

fn parse_op(text: &str) -> Result<NetOp, String> {
    match text {
        "AND" => Ok(NetOp::And),
        "OR" => Ok(NetOp::Or),
        "XOR" => Ok(NetOp::Xor),
        "NAND" => Ok(NetOp::Nand),
        "NOR" => Ok(NetOp::Nor),
        "XNOR" => Ok(NetOp::Xnor),
        _ => Err(format!("unsupported operation {text}")),
    }
}

fn parse_literal(text: &str, ninputs: usize, available_gates: usize) -> Result<NetLit, String> {
    let (inverted, name) = match text.strip_prefix('~') {
        Some(name) if !name.is_empty() && !name.starts_with('~') => (true, name),
        Some(_) => return Err("invalid complemented literal".into()),
        None => (false, text),
    };
    let base = if let Some(index) = name.strip_prefix('x') {
        let index = parse_one_based(index, "input")?;
        if index > ninputs {
            return Err(format!("input x{index} is out of range"));
        }
        Base::Input(index - 1)
    } else if let Some(index) = name.strip_prefix('w') {
        let index = parse_one_based(index, "gate")?;
        if index > available_gates {
            return Err(format!("gate w{index} is not available yet"));
        }
        Base::Gate(index - 1)
    } else {
        return Err(format!("invalid literal {text}"));
    };
    Ok(NetLit { base, inverted })
}

fn parse_one_based(text: &str, kind: &str) -> Result<usize, String> {
    let index = text
        .parse::<usize>()
        .map_err(|_| format!("{kind} index must be an integer"))?;
    if index == 0 {
        return Err(format!("{kind} indices start at 1"));
    }
    Ok(index)
}

fn literal_value(literal: NetLit, inputs: &[bool], gates: &[bool]) -> bool {
    let value = match literal.base {
        Base::Input(index) => inputs[index],
        Base::Gate(index) => gates[index],
    };
    value ^ literal.inverted
}

pub(crate) fn serialize(circuit: &Circuit) -> Result<String, String> {
    let (graph, outputs) = circuit.graph.compact(&circuit.outputs);
    let needs_constant = outputs.iter().any(|output| graph.is_constant(*output));
    if needs_constant && graph.input_count() == 0 {
        return Err("cannot materialize a constant without an input".into());
    }

    let mut text = format!("INPUTS {}\n", graph.input_count());
    for (index, gate) in graph.gates().iter().enumerate() {
        let op = match gate.op {
            Op::And => "AND",
            Op::Xor => "XOR",
        };
        text.push_str(&format!(
            "w{} = {op} {} {}\n",
            index + 1,
            graph.format_literal(gate.left),
            graph.format_literal(gate.right)
        ));
    }

    let constant_wire = graph.gates().len() + 1;
    if needs_constant {
        text.push_str(&format!("w{constant_wire} = XOR x1 x1\n"));
    }
    text.push_str("OUTPUTS");
    for output in outputs {
        text.push(' ');
        if graph.is_constant(output) {
            if graph.constant_value(output) {
                text.push('~');
            }
            text.push_str(&format!("w{constant_wire}"));
        } else {
            text.push_str(&graph.format_literal(output));
        }
    }
    text.push('\n');
    Ok(text)
}
