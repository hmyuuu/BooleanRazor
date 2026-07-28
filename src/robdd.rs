use std::collections::{BTreeSet, HashMap};
use std::ops::Not;

use crate::table::{CompleteTable, row_index};
use crate::xag::{Circuit, Lit, Xag};

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct NodeId(u32);

impl NodeId {
    const FALSE: Self = Self(0);

    fn index(self) -> usize {
        self.0 as usize
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct BddEdge {
    node: NodeId,
    inverted: bool,
}

impl BddEdge {
    const FALSE: Self = Self {
        node: NodeId::FALSE,
        inverted: false,
    };

    const fn constant(value: bool) -> Self {
        Self {
            inverted: value,
            ..Self::FALSE
        }
    }
}

impl Not for BddEdge {
    type Output = Self;

    fn not(self) -> Self::Output {
        Self {
            inverted: !self.inverted,
            ..self
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct BddNode {
    var: usize,
    low: BddEdge,
    high: BddEdge,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct NodeKey {
    var: usize,
    low: BddEdge,
    high: BddEdge,
}

#[derive(Debug)]
pub struct SharedRobdd {
    nvars: usize,
    order: Vec<usize>,
    nodes: Vec<BddNode>,
    unique: HashMap<NodeKey, NodeId>,
    roots: Vec<BddEdge>,
}

struct Builder<'a> {
    table: &'a CompleteTable,
    order: Vec<usize>,
    nodes: Vec<BddNode>,
    unique: HashMap<NodeKey, NodeId>,
}

impl Builder<'_> {
    fn build_output(
        &mut self,
        output: usize,
        depth: usize,
        logical_mask: usize,
    ) -> Result<BddEdge, String> {
        if depth == self.order.len() {
            return Ok(BddEdge::constant(self.table.outputs[logical_mask][output]));
        }

        let var = self.order[depth];
        let low = self.build_output(output, depth + 1, logical_mask)?;
        let high_mask = logical_mask | (1usize << var);
        let high = self.build_output(output, depth + 1, high_mask)?;
        self.mk(var, low, high)
    }

    fn mk(&mut self, var: usize, low: BddEdge, high: BddEdge) -> Result<BddEdge, String> {
        canonical_mk(&mut self.nodes, &mut self.unique, var, low, high)
    }
}

fn canonical_mk(
    nodes: &mut Vec<BddNode>,
    unique: &mut HashMap<NodeKey, NodeId>,
    var: usize,
    mut low: BddEdge,
    mut high: BddEdge,
) -> Result<BddEdge, String> {
    if low == high {
        return Ok(low);
    }

    let output_inverted = low.inverted;
    if output_inverted {
        low = !low;
        high = !high;
    }
    let key = NodeKey { var, low, high };
    let node = if let Some(node) = unique.get(&key) {
        *node
    } else {
        let raw_id = nodes
            .len()
            .checked_add(1)
            .ok_or_else(|| "ROBDD node dimensions overflow".to_string())?;
        let raw_id =
            u32::try_from(raw_id).map_err(|_| "ROBDD node dimensions overflow".to_string())?;
        let node = NodeId(raw_id);
        nodes.push(BddNode { var, low, high });
        unique.insert(key, node);
        node
    };
    Ok(BddEdge {
        node,
        inverted: output_inverted,
    })
}

impl SharedRobdd {
    pub fn build(table: &CompleteTable, order: Vec<usize>) -> Result<Self, String> {
        let row_count = table_row_count(table.ninputs)?;
        if table.outputs.len() != row_count {
            return Err(format!(
                "complete table has {} rows, expected {row_count}",
                table.outputs.len()
            ));
        }
        if table
            .outputs
            .iter()
            .any(|output| output.len() != table.noutputs)
        {
            return Err("complete table output width does not match noutputs".into());
        }
        if table.noutputs == 0 {
            return Err("complete table must contain at least one output".into());
        }
        validate_order(table.ninputs, &order)?;

        let mut builder = Builder {
            table,
            order,
            nodes: Vec::new(),
            unique: HashMap::new(),
        };
        let mut roots = Vec::new();
        roots
            .try_reserve_exact(table.noutputs)
            .map_err(|_| "ROBDD root dimensions overflow".to_string())?;
        for output in 0..table.noutputs {
            roots.push(builder.build_output(output, 0, 0)?);
        }

        let forest = Self {
            nvars: table.ninputs,
            order: builder.order,
            nodes: builder.nodes,
            unique: builder.unique,
            roots,
        };
        forest.validate_invariants()?;
        Ok(forest)
    }

    pub(crate) fn new_care(nvars: usize, order: Vec<usize>) -> Result<Self, String> {
        validate_order(nvars, &order)?;
        Ok(Self {
            nvars,
            order,
            nodes: Vec::new(),
            unique: HashMap::new(),
            roots: Vec::new(),
        })
    }

    pub(crate) const fn care_constant(value: bool) -> BddEdge {
        BddEdge::constant(value)
    }

    pub(crate) fn mk_care_node(
        &mut self,
        var: usize,
        low: BddEdge,
        high: BddEdge,
    ) -> Result<BddEdge, String> {
        canonical_mk(&mut self.nodes, &mut self.unique, var, low, high)
    }

    pub(crate) fn finish_care(mut self, roots: Vec<BddEdge>) -> Result<Self, String> {
        if roots.is_empty() {
            return Err("care ROBDD must contain at least one output root".into());
        }
        self.roots = roots;
        self.validate_invariants()?;
        Ok(self)
    }

    pub fn roots(&self) -> &[BddEdge] {
        &self.roots
    }

    pub fn reachable_node_ids(&self) -> Vec<NodeId> {
        let mut reachable = BTreeSet::from([NodeId::FALSE]);
        let mut stack = self.roots.clone();
        while let Some(edge) = stack.pop() {
            if !reachable.insert(edge.node) || edge.node == NodeId::FALSE {
                continue;
            }
            let node = self.nodes[edge.node.index() - 1];
            stack.push(node.low);
            stack.push(node.high);
        }
        reachable.into_iter().collect()
    }

    pub fn shared_node_count(&self) -> usize {
        self.reachable_node_ids().len()
    }

    pub fn evaluate(&self, input: &[bool]) -> Result<Vec<bool>, String> {
        if input.len() != self.nvars {
            return Err(format!(
                "expected {} ROBDD inputs, got {}",
                self.nvars,
                input.len()
            ));
        }
        let logical_mask = row_index(input);
        self.roots
            .iter()
            .map(|root| self.evaluate_edge(*root, logical_mask))
            .collect()
    }

    pub fn evaluate_mask(&self, logical_mask: usize) -> Result<Vec<bool>, String> {
        let row_count = table_row_count(self.nvars)?;
        if logical_mask >= row_count {
            return Err(format!(
                "logical mask {logical_mask} is out of range for {} variables",
                self.nvars
            ));
        }
        self.roots
            .iter()
            .map(|root| self.evaluate_edge(*root, logical_mask))
            .collect()
    }

    pub fn validate_invariants(&self) -> Result<(), String> {
        validate_order(self.nvars, &self.order)?;
        if self.unique.len() != self.nodes.len() {
            return Err("ROBDD unique table length does not match node storage".into());
        }

        let mut rank = vec![usize::MAX; self.nvars];
        for (position, &var) in self.order.iter().enumerate() {
            rank[var] = position;
        }
        let node_limit = self.nodes.len();
        for (index, node) in self.nodes.iter().enumerate() {
            let id = index + 1;
            if node.var >= self.nvars {
                return Err("ROBDD node variable is out of range".into());
            }
            if node.low == node.high {
                return Err("ROBDD reduction invariant violated".into());
            }
            if node.low.inverted {
                return Err("ROBDD low edge is complemented".into());
            }
            for child in [node.low, node.high] {
                if child.node.index() > node_limit {
                    return Err("ROBDD child node is out of range".into());
                }
                if child.node != NodeId::FALSE {
                    if child.node.index() >= id {
                        return Err("ROBDD child is not topologically earlier than parent".into());
                    }
                    let child_node = self.nodes[child.node.index() - 1];
                    if rank[child_node.var] <= rank[node.var] {
                        return Err("ROBDD child does not follow variable order".into());
                    }
                }
            }

            let key = NodeKey {
                var: node.var,
                low: node.low,
                high: node.high,
            };
            let expected =
                NodeId(u32::try_from(id).map_err(|_| {
                    "ROBDD invariant validation node dimensions overflow".to_string()
                })?);
            if self.unique.get(&key) != Some(&expected) {
                return Err("ROBDD unique table is inconsistent".into());
            }
        }
        for root in &self.roots {
            if root.node.index() > node_limit {
                return Err("ROBDD root node is out of range".into());
            }
        }
        let reachable = self.reachable_node_ids();
        if reachable.len() != self.nodes.len() + 1
            || reachable
                .iter()
                .enumerate()
                .any(|(expected, node)| node.index() != expected)
        {
            return Err("ROBDD storage contains nodes outside the reachable union".into());
        }
        Ok(())
    }

    pub fn extract_xag(&self) -> Result<Circuit, String> {
        self.validate_invariants()?;
        let mut graph = Xag::new(self.nvars);
        let mut memo = vec![None; self.nodes.len() + 1];
        memo[0] = Some(graph.f());
        let mut outputs = Vec::new();
        outputs
            .try_reserve_exact(self.roots.len())
            .map_err(|_| "XAG output dimensions overflow".to_string())?;
        for root in &self.roots {
            outputs.push(self.extract_edge(*root, &mut graph, &mut memo)?);
        }
        let (graph, outputs) = graph.compact(&outputs)?;
        Circuit::new(graph, outputs)
    }

    fn evaluate_edge(&self, mut edge: BddEdge, logical_mask: usize) -> Result<bool, String> {
        let mut inverted = false;
        loop {
            inverted ^= edge.inverted;
            if edge.node == NodeId::FALSE {
                return Ok(inverted);
            }
            let node = self
                .nodes
                .get(edge.node.index() - 1)
                .ok_or_else(|| "ROBDD edge references an out-of-range node".to_string())?;
            edge = if ((logical_mask >> node.var) & 1) == 0 {
                node.low
            } else {
                node.high
            };
        }
    }

    fn extract_edge(
        &self,
        edge: BddEdge,
        graph: &mut Xag,
        memo: &mut [Option<Lit>],
    ) -> Result<Lit, String> {
        let regular = self.extract_regular(edge.node, graph, memo)?;
        Ok(if edge.inverted { !regular } else { regular })
    }

    fn extract_regular(
        &self,
        node_id: NodeId,
        graph: &mut Xag,
        memo: &mut [Option<Lit>],
    ) -> Result<Lit, String> {
        if let Some(literal) = memo[node_id.index()] {
            return Ok(literal);
        }
        let node = *self
            .nodes
            .get(node_id.index() - 1)
            .ok_or_else(|| "ROBDD extraction found an out-of-range node".to_string())?;
        let low = self.extract_edge(node.low, graph, memo)?;
        let high = self.extract_edge(node.high, graph, memo)?;
        let difference = graph.xor(low, high)?;
        let selected_difference = graph.and(graph.input(node.var), difference)?;
        let literal = graph.xor(low, selected_difference)?;
        memo[node_id.index()] = Some(literal);
        Ok(literal)
    }
}

fn table_row_count(nvars: usize) -> Result<usize, String> {
    let shift =
        u32::try_from(nvars).map_err(|_| "complete table dimensions overflow".to_string())?;
    1usize
        .checked_shl(shift)
        .ok_or_else(|| "complete table dimensions overflow".to_string())
}

fn validate_order(nvars: usize, order: &[usize]) -> Result<(), String> {
    if order.len() != nvars {
        return Err(format!(
            "variable order length {} does not match {nvars}",
            order.len()
        ));
    }
    let mut seen = vec![false; nvars];
    for &var in order {
        if var >= nvars {
            return Err(format!("variable order entry {var} is out of range"));
        }
        if seen[var] {
            return Err(format!("variable order contains duplicate entry {var}"));
        }
        seen[var] = true;
    }
    Ok(())
}
