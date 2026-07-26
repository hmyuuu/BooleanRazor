use std::collections::HashMap;
use std::ops::Not;

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Lit {
    node: usize,
    inverted: bool,
}

impl Lit {
    fn with_polarity(self, inverted: bool) -> Self {
        Self {
            node: self.node,
            inverted: self.inverted ^ inverted,
        }
    }
}

impl Not for Lit {
    type Output = Self;

    fn not(self) -> Self::Output {
        self.with_polarity(true)
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub(crate) enum Op {
    And,
    Xor,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub(crate) struct Gate {
    pub(crate) op: Op,
    pub(crate) left: Lit,
    pub(crate) right: Lit,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct GateKey {
    op: Op,
    left: Lit,
    right: Lit,
}

#[derive(Clone, Debug)]
pub struct Xag {
    ninputs: usize,
    gates: Vec<Gate>,
    unique: HashMap<GateKey, Lit>,
}

impl Xag {
    pub fn new(ninputs: usize) -> Self {
        Self {
            ninputs,
            gates: Vec::new(),
            unique: HashMap::new(),
        }
    }

    pub const fn constant(value: bool) -> Lit {
        Lit {
            node: 0,
            inverted: value,
        }
    }

    pub const fn f(&self) -> Lit {
        Self::constant(false)
    }

    pub const fn t(&self) -> Lit {
        Self::constant(true)
    }

    pub fn input(&self, index: usize) -> Lit {
        assert!(
            index < self.ninputs,
            "input index {index} is out of range for {} inputs",
            self.ninputs
        );
        Lit {
            node: index + 1,
            inverted: false,
        }
    }

    pub fn and(&mut self, left: Lit, right: Lit) -> Lit {
        self.assert_valid(left);
        self.assert_valid(right);
        if left == self.f() || right == self.f() {
            return self.f();
        }
        if left == self.t() {
            return right;
        }
        if right == self.t() {
            return left;
        }
        if left == right {
            return left;
        }
        if left == !right {
            return self.f();
        }
        self.intern(Op::And, left, right)
    }

    pub fn xor(&mut self, left: Lit, right: Lit) -> Lit {
        self.assert_valid(left);
        self.assert_valid(right);
        if left == self.f() {
            return right;
        }
        if right == self.f() {
            return left;
        }
        if left == self.t() {
            return !right;
        }
        if right == self.t() {
            return !left;
        }
        if left == right {
            return self.f();
        }
        if left == !right {
            return self.t();
        }
        let output_inverted = left.inverted ^ right.inverted;
        let left = Lit {
            inverted: false,
            ..left
        };
        let right = Lit {
            inverted: false,
            ..right
        };
        self.intern(Op::Xor, left, right)
            .with_polarity(output_inverted)
    }

    pub fn or(&mut self, left: Lit, right: Lit) -> Lit {
        let not_left = !left;
        let not_right = !right;
        !self.and(not_left, not_right)
    }

    pub fn mux(&mut self, select: Lit, then_value: Lit, else_value: Lit) -> Lit {
        let difference = self.xor(then_value, else_value);
        let selected_difference = self.and(select, difference);
        self.xor(else_value, selected_difference)
    }

    pub fn evaluate(&self, inputs: &[bool], outputs: &[Lit]) -> Result<Vec<bool>, String> {
        if inputs.len() != self.ninputs {
            return Err(format!(
                "expected {} inputs, got {}",
                self.ninputs,
                inputs.len()
            ));
        }
        for output in outputs {
            if output.node >= self.node_count() {
                return Err("output literal does not belong to this XAG".into());
            }
        }

        let mut values = vec![false; self.node_count()];
        values[1..1 + self.ninputs].copy_from_slice(inputs);
        for (index, gate) in self.gates.iter().enumerate() {
            let value = match gate.op {
                Op::And => {
                    self.literal_value(gate.left, &values) & self.literal_value(gate.right, &values)
                }
                Op::Xor => {
                    self.literal_value(gate.left, &values) ^ self.literal_value(gate.right, &values)
                }
            };
            values[self.gate_node(index)] = value;
        }
        Ok(outputs
            .iter()
            .map(|output| self.literal_value(*output, &values))
            .collect())
    }

    pub fn reachable_gate_count(&self, outputs: &[Lit]) -> usize {
        self.live_gates(outputs)
            .into_iter()
            .filter(|is_live| *is_live)
            .count()
    }

    pub fn compact(&self, outputs: &[Lit]) -> (Self, Vec<Lit>) {
        let live = self.live_gates(outputs);
        let mut compact = Self::new(self.ninputs);
        let mut remap = vec![self.f(); self.node_count()];
        for input in 0..self.ninputs {
            remap[input + 1] = compact.input(input);
        }

        for (index, gate) in self.gates.iter().enumerate() {
            if live[index] {
                let left = remap[gate.left.node].with_polarity(gate.left.inverted);
                let right = remap[gate.right.node].with_polarity(gate.right.inverted);
                remap[self.gate_node(index)] = match gate.op {
                    Op::And => compact.and(left, right),
                    Op::Xor => compact.xor(left, right),
                };
            }
        }

        let outputs = outputs
            .iter()
            .map(|output| remap[output.node].with_polarity(output.inverted))
            .collect();
        (compact, outputs)
    }

    fn intern(&mut self, op: Op, mut left: Lit, mut right: Lit) -> Lit {
        if right < left {
            std::mem::swap(&mut left, &mut right);
        }
        let key = GateKey { op, left, right };
        if let Some(existing) = self.unique.get(&key) {
            return *existing;
        }

        let literal = Lit {
            node: self.gate_node(self.gates.len()),
            inverted: false,
        };
        self.gates.push(Gate { op, left, right });
        self.unique.insert(key, literal);
        literal
    }

    fn live_gates(&self, outputs: &[Lit]) -> Vec<bool> {
        let mut live = vec![false; self.gates.len()];
        let mut stack = outputs.to_vec();
        while let Some(literal) = stack.pop() {
            self.assert_valid(literal);
            if let Some(index) = self.gate_index(literal.node) {
                if live[index] {
                    continue;
                }
                live[index] = true;
                let gate = self.gates[index];
                stack.push(gate.left);
                stack.push(gate.right);
            }
        }
        live
    }

    fn assert_valid(&self, literal: Lit) {
        assert!(
            literal.node < self.node_count(),
            "literal does not belong to this XAG"
        );
    }

    fn literal_value(&self, literal: Lit, values: &[bool]) -> bool {
        values[literal.node] ^ literal.inverted
    }

    fn node_count(&self) -> usize {
        1 + self.ninputs + self.gates.len()
    }

    fn gate_node(&self, index: usize) -> usize {
        1 + self.ninputs + index
    }

    fn gate_index(&self, node: usize) -> Option<usize> {
        node.checked_sub(1 + self.ninputs)
            .filter(|index| *index < self.gates.len())
    }

    pub(crate) fn input_count(&self) -> usize {
        self.ninputs
    }

    pub(crate) fn gates(&self) -> &[Gate] {
        &self.gates
    }

    pub(crate) fn format_literal(&self, literal: Lit) -> String {
        self.assert_valid(literal);
        let prefix = if literal.inverted { "~" } else { "" };
        if literal.node == 0 {
            format!("{prefix}0")
        } else if literal.node <= self.ninputs {
            format!("{prefix}x{}", literal.node)
        } else {
            format!("{prefix}w{}", literal.node - self.ninputs)
        }
    }

    pub(crate) fn is_constant(&self, literal: Lit) -> bool {
        literal.node == 0
    }

    pub(crate) fn constant_value(&self, literal: Lit) -> bool {
        debug_assert!(self.is_constant(literal));
        literal.inverted
    }
}

#[derive(Clone, Debug)]
pub struct Circuit {
    pub(crate) graph: Xag,
    pub(crate) outputs: Vec<Lit>,
}

impl Circuit {
    pub fn new(graph: Xag, outputs: Vec<Lit>) -> Self {
        for output in &outputs {
            graph.assert_valid(*output);
        }
        Self { graph, outputs }
    }

    pub fn evaluate(&self, inputs: &[bool]) -> Result<Vec<bool>, String> {
        self.graph.evaluate(inputs, &self.outputs)
    }

    pub fn evaluate_u64(&self, inputs: &[bool]) -> Result<u64, String> {
        if self.outputs.len() > u64::BITS as usize {
            return Err("cannot encode more than 64 outputs as u64".into());
        }
        Ok(self
            .evaluate(inputs)?
            .iter()
            .enumerate()
            .fold(0, |value, (index, bit)| value | (u64::from(*bit) << index)))
    }

    pub fn to_netlist(&self) -> Result<String, String> {
        crate::netlist::serialize(self)
    }
}
