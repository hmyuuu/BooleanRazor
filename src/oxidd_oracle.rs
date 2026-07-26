use oxidd::bcdd::{BCDDFunction, BCDDManagerRef};
use std::collections::HashSet;

use oxidd::{BooleanFunction, Edge, Function, InnerNode, Manager, ManagerRef, Node, NodeID, VarNo};

use crate::table::CompleteTable;

pub struct OxiddForest {
    _manager: BCDDManagerRef,
    nvars: usize,
    logical_to_varno: Vec<VarNo>,
    varno_to_logical: Vec<usize>,
    roots: Vec<BCDDFunction>,
}

impl OxiddForest {
    pub fn build(table: &CompleteTable, order: Vec<usize>) -> Result<Self, String> {
        validate_table(table)?;
        validate_order(table.ninputs, &order)?;

        let manager = oxidd::bcdd::new_manager(1 << 20, 1 << 18, 1);
        let nvars = VarNo::try_from(table.ninputs)
            .map_err(|_| "complete table dimensions overflow".to_string())?;
        let (variables, false_function, true_function) = manager
            .with_manager_exclusive(|m| {
                let variables = m
                    .add_vars(nvars)
                    .map(|var| BCDDFunction::var(m, var))
                    .collect::<Result<Vec<_>, _>>()?;
                Ok::<_, oxidd::error::OutOfMemory>((
                    variables,
                    BCDDFunction::f(m),
                    BCDDFunction::t(m),
                ))
            })
            .map_err(|error| format!("OxiDD variable allocation failed: {error}"))?;

        let mut logical_to_varno = vec![0; table.ninputs];
        for (rank, &logical) in order.iter().enumerate() {
            logical_to_varno[logical] = rank as VarNo;
        }

        let mut roots = Vec::with_capacity(table.noutputs);
        for output in 0..table.noutputs {
            roots.push(build_output(
                table,
                output,
                0,
                0,
                &order,
                &variables,
                &false_function,
                &true_function,
            )?);
        }

        Ok(Self {
            _manager: manager,
            nvars: table.ninputs,
            varno_to_logical: order.clone(),
            logical_to_varno,
            roots,
        })
    }

    pub fn evaluate_mask(&self, logical_mask: usize) -> Result<Vec<bool>, String> {
        let row_count = table_row_count(self.nvars)?;
        if logical_mask >= row_count {
            return Err(format!(
                "logical mask {logical_mask} is out of range for {} variables",
                self.nvars
            ));
        }
        let assignment = self
            .logical_to_varno
            .iter()
            .enumerate()
            .map(|(logical, &var)| (var, logical_mask & (1usize << logical) != 0))
            .collect::<Vec<_>>();
        Ok(self
            .roots
            .iter()
            .map(|root| root.eval(assignment.iter().copied()))
            .collect())
    }

    pub fn evaluate_all(&self) -> Result<Vec<Vec<bool>>, String> {
        (0..table_row_count(self.nvars)?)
            .map(|mask| self.evaluate_mask(mask))
            .collect()
    }

    pub fn node_count(&self, output: usize) -> Result<usize, String> {
        self.roots
            .get(output)
            .map(Function::node_count)
            .ok_or_else(|| format!("output {output} is out of range"))
    }

    pub fn varno_for_logical_input(&self, logical_input: usize) -> Result<VarNo, String> {
        self.logical_to_varno
            .get(logical_input)
            .copied()
            .ok_or_else(|| format!("logical input {logical_input} is out of range"))
    }

    pub fn logical_input_for_varno(&self, varno: VarNo) -> Result<usize, String> {
        self.varno_to_logical
            .get(varno as usize)
            .copied()
            .ok_or_else(|| format!("variable number {varno} is out of range"))
    }

    pub fn shared_node_count(&self) -> usize {
        self.roots[0].with_manager_shared(|manager, _| {
            let mut seen = HashSet::<NodeID>::new();
            let mut stack = self
                .roots
                .iter()
                .map(|root| manager.clone_edge(root.as_edge(manager)))
                .collect::<Vec<_>>();
            while let Some(edge) = stack.pop() {
                if seen.insert(edge.node_id())
                    && let Node::Inner(node) = manager.get_node(&edge)
                {
                    stack.extend(node.children().map(|child| manager.clone_edge(&child)));
                }
                manager.drop_edge(edge);
            }
            seen.len()
        })
    }
}

fn build_output(
    table: &CompleteTable,
    output: usize,
    rank: usize,
    logical_mask: usize,
    order: &[usize],
    variables: &[BCDDFunction],
    false_function: &BCDDFunction,
    true_function: &BCDDFunction,
) -> Result<BCDDFunction, String> {
    if rank == order.len() {
        return Ok(if table.outputs[logical_mask][output] {
            true_function.clone()
        } else {
            false_function.clone()
        });
    }

    let low = build_output(
        table,
        output,
        rank + 1,
        logical_mask,
        order,
        variables,
        false_function,
        true_function,
    )?;
    let high = build_output(
        table,
        output,
        rank + 1,
        logical_mask | (1usize << order[rank]),
        order,
        variables,
        false_function,
        true_function,
    )?;
    variables[rank]
        .ite(&high, &low)
        .map_err(|error| format!("OxiDD ITE allocation failed: {error}"))
}

fn validate_table(table: &CompleteTable) -> Result<(), String> {
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
    Ok(())
}

fn validate_order(nvars: usize, order: &[usize]) -> Result<(), String> {
    if order.len() != nvars {
        return Err(format!(
            "variable order length {} does not match {nvars} inputs",
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

fn table_row_count(ninputs: usize) -> Result<usize, String> {
    let shift =
        u32::try_from(ninputs).map_err(|_| "complete table dimensions overflow".to_string())?;
    1usize
        .checked_shl(shift)
        .ok_or_else(|| "complete table dimensions overflow".to_string())
}
