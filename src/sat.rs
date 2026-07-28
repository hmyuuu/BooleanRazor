use std::collections::{BTreeSet, VecDeque};
use std::fs;
use std::io::Write;
use std::ops::Not;
use std::path::{Path, PathBuf};
use std::sync::{
    Arc,
    atomic::{AtomicBool, AtomicU64, Ordering},
};
use std::time::Instant;

use rustsat::solvers::{ControlSignal, Solve, SolverResult, Terminate};
use rustsat::types::{Clause, Lit as SatLit, TernaryVal, Var};
use rustsat_cadical::{CaDiCaL, ProofFormat};

use crate::bits::{encode_bits, encode_lsb};
use crate::netlist::Netlist;
use crate::table::{CompleteTable, sha256_hex};
use crate::xag::{Circuit, Lit, Op, Xag};

const MAX_CUT_INPUTS: usize = 6;
const FROZEN_CUT_BUDGET: usize = 128;
const FROZEN_SOLVER_CALL_BUDGET: usize = 64;
static NEXT_PROOF_TRACE: AtomicU64 = AtomicU64::new(0);
static NEXT_ARTIFACT_PUBLISH: AtomicU64 = AtomicU64::new(0);

struct ProofTrace(PathBuf);

impl ProofTrace {
    fn new() -> Self {
        Self(std::env::temp_dir().join(format!(
            "occam-cadical-proof-{}-{}.drat",
            std::process::id(),
            NEXT_PROOF_TRACE.fetch_add(1, Ordering::Relaxed)
        )))
    }
}

impl Drop for ProofTrace {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

#[derive(Debug)]
pub enum SatResult {
    Sat(Circuit),
    Unsat,
    Timeout,
    Unknown(String),
}

#[derive(Clone, Copy)]
enum RowValue {
    Constant(bool),
    Variable(Var),
}

struct GateVariables {
    xor: Var,
    left_select: Vec<Var>,
    left_inverted: Var,
    left_values: Vec<Var>,
    right_select: Vec<Var>,
    right_inverted: Var,
    right_values: Vec<Var>,
    values: Vec<Var>,
}

struct OutputVariables {
    select: Vec<Var>,
    inverted: Var,
}

struct Encoding {
    clauses: Vec<Vec<SatLit>>,
    next_variable: u32,
    gates: Vec<GateVariables>,
    outputs: Vec<OutputVariables>,
}

impl Encoding {
    fn new() -> Self {
        Self {
            clauses: Vec::new(),
            next_variable: 0,
            gates: Vec::new(),
            outputs: Vec::new(),
        }
    }

    fn variable(&mut self) -> Var {
        let variable = Var::new(self.next_variable);
        self.next_variable += 1;
        variable
    }

    fn variables(&mut self, count: usize) -> Vec<Var> {
        (0..count).map(|_| self.variable()).collect()
    }

    fn clause(&mut self, literals: impl IntoIterator<Item = SatLit>) {
        self.clauses.push(literals.into_iter().collect());
    }

    fn exactly_one(&mut self, variables: &[Var], deadline: Instant) -> Result<(), String> {
        self.exactly_one_with_expiry(variables, || Instant::now() >= deadline)
    }

    fn exactly_one_with_expiry(
        &mut self,
        variables: &[Var],
        mut expired: impl FnMut() -> bool,
    ) -> Result<(), String> {
        if expired() {
            return Err("deadline expired during exactly-one encoding".into());
        }
        self.clause(variables.iter().map(|variable| variable.pos_lit()));
        for left in 0..variables.len() {
            if expired() {
                return Err("deadline expired during exactly-one encoding".into());
            }
            for right in left + 1..variables.len() {
                if expired() {
                    return Err("deadline expired during exactly-one encoding".into());
                }
                self.clause([variables[left].neg_lit(), variables[right].neg_lit()]);
            }
        }
        Ok(())
    }

    fn encode_selected_value(
        &mut self,
        selector: Var,
        source: RowValue,
        inverted: Var,
        value: Var,
    ) {
        match source {
            RowValue::Constant(source) => {
                for polarity in [false, true] {
                    let expected = source ^ polarity;
                    self.clause([
                        selector.neg_lit(),
                        forbid_assignment(inverted, polarity),
                        forbid_assignment(value, !expected),
                    ]);
                }
            }
            RowValue::Variable(source) => {
                for source_value in [false, true] {
                    for polarity in [false, true] {
                        let expected = source_value ^ polarity;
                        self.clause([
                            selector.neg_lit(),
                            forbid_assignment(source, source_value),
                            forbid_assignment(inverted, polarity),
                            forbid_assignment(value, !expected),
                        ]);
                    }
                }
            }
        }
    }

    fn encode_selected_output(
        &mut self,
        selector: Var,
        source: RowValue,
        inverted: Var,
        expected: bool,
    ) {
        match source {
            RowValue::Constant(source) => {
                let required_polarity = source ^ expected;
                self.clause([
                    selector.neg_lit(),
                    forbid_assignment(inverted, !required_polarity),
                ]);
            }
            RowValue::Variable(source) => {
                for source_value in [false, true] {
                    let required_polarity = source_value ^ expected;
                    self.clause([
                        selector.neg_lit(),
                        forbid_assignment(source, source_value),
                        forbid_assignment(inverted, !required_polarity),
                    ]);
                }
            }
        }
    }

    fn encode_gate_truth(&mut self, xor: Var, left: Var, right: Var, output: Var) {
        for is_xor in [false, true] {
            for left_value in [false, true] {
                for right_value in [false, true] {
                    let expected = if is_xor {
                        left_value ^ right_value
                    } else {
                        left_value & right_value
                    };
                    self.clause([
                        forbid_assignment(xor, is_xor),
                        forbid_assignment(left, left_value),
                        forbid_assignment(right, right_value),
                        forbid_assignment(output, !expected),
                    ]);
                }
            }
        }
    }

    fn dimacs_bytes(&self, deadline: Instant) -> Result<Vec<u8>, String> {
        if Instant::now() >= deadline {
            return Err("deadline expired during DIMACS construction".into());
        }
        let mut bytes =
            format!("p cnf {} {}\n", self.next_variable, self.clauses.len()).into_bytes();
        for clause in &self.clauses {
            if Instant::now() >= deadline {
                return Err("deadline expired during DIMACS construction".into());
            }
            for literal in clause {
                bytes.extend_from_slice(literal.to_ipasir().to_string().as_bytes());
                bytes.push(b' ');
            }
            bytes.extend_from_slice(b"0\n");
        }
        if Instant::now() >= deadline {
            return Err("deadline expired during DIMACS construction".into());
        }
        Ok(bytes)
    }
}

fn forbid_assignment(variable: Var, value: bool) -> SatLit {
    variable.lit(value)
}

fn validate_table(table: &CompleteTable) -> Result<(), String> {
    if table.ninputs > MAX_CUT_INPUTS {
        return Err(format!(
            "SAT synthesis supports at most {MAX_CUT_INPUTS} inputs"
        ));
    }
    if table.noutputs == 0 {
        return Err("SAT synthesis requires at least one output".into());
    }
    let expected_rows = 1usize
        .checked_shl(table.ninputs as u32)
        .ok_or_else(|| "truth-table dimensions overflow".to_string())?;
    if table.outputs.len() != expected_rows {
        return Err(format!(
            "complete table has {} rows, expected {expected_rows}",
            table.outputs.len()
        ));
    }
    if table
        .outputs
        .iter()
        .any(|output| output.len() != table.noutputs)
    {
        return Err("complete table row has the wrong output width".into());
    }
    Ok(())
}

fn assert_exhaustive_equivalence_before(
    table: &CompleteTable,
    circuit: &Circuit,
    deadline: Option<Instant>,
) -> Result<(), String> {
    validate_table(table)?;
    for (row, expected) in table.outputs.iter().enumerate() {
        if deadline.is_some_and(|deadline| Instant::now() >= deadline) {
            return Err("deadline expired during exhaustive equivalence".into());
        }
        let inputs = encode_lsb(row as u64, table.ninputs);
        let actual = circuit.evaluate(&inputs)?;
        if actual != *expected {
            return Err(format!("circuit differs from complete table at row {row}"));
        }
    }
    if deadline.is_some_and(|deadline| Instant::now() >= deadline) {
        return Err("deadline expired during exhaustive equivalence".into());
    }
    Ok(())
}

pub fn synthesize_xag_at_most(
    table: &CompleteTable,
    gates: usize,
    deadline: Instant,
) -> Result<SatResult, String> {
    Ok(synthesize_xag_at_most_with_diagnostics(table, gates, deadline, usize::MAX)?.result)
}

struct SynthesisDiagnostics {
    result: SatResult,
    dimacs: Vec<u8>,
    proof: Vec<u8>,
    encoded_bound: Option<usize>,
    solver_calls: usize,
}

fn synthesize_xag_at_most_with_diagnostics(
    table: &CompleteTable,
    gates: usize,
    deadline: Instant,
    max_solver_calls: usize,
) -> Result<SynthesisDiagnostics, String> {
    if Instant::now() >= deadline {
        return Ok(SynthesisDiagnostics {
            result: SatResult::Timeout,
            dimacs: Vec::new(),
            proof: Vec::new(),
            encoded_bound: None,
            solver_calls: 0,
        });
    }
    validate_table(table)?;
    let mut last_dimacs = Vec::new();
    let mut last_proof = Vec::new();
    for (calls, exact_gates) in (0..=gates).enumerate() {
        if Instant::now() >= deadline {
            return Ok(SynthesisDiagnostics {
                result: SatResult::Timeout,
                dimacs: last_dimacs,
                proof: last_proof,
                encoded_bound: exact_gates.checked_sub(1),
                solver_calls: calls,
            });
        }
        if calls == max_solver_calls {
            return Ok(SynthesisDiagnostics {
                result: SatResult::Unknown("frozen solver-call budget exhausted".into()),
                dimacs: last_dimacs,
                proof: last_proof,
                encoded_bound: exact_gates.checked_sub(1),
                solver_calls: calls,
            });
        }
        let exact = synthesize_xag_exactly(table, exact_gates, deadline)?;
        last_dimacs = exact.dimacs;
        last_proof = exact.proof;
        match exact.result {
            SatResult::Unsat if exact_gates < gates => {}
            result => {
                return Ok(SynthesisDiagnostics {
                    result,
                    dimacs: last_dimacs,
                    proof: last_proof,
                    encoded_bound: Some(exact_gates),
                    solver_calls: calls + 1,
                });
            }
        }
    }
    unreachable!("inclusive exact-bound loop always returns at its final bound")
}

struct ExactSynthesis {
    result: SatResult,
    dimacs: Vec<u8>,
    proof: Vec<u8>,
}

fn synthesize_xag_exactly(
    table: &CompleteTable,
    gates: usize,
    deadline: Instant,
) -> Result<ExactSynthesis, String> {
    if Instant::now() >= deadline {
        return Ok(ExactSynthesis {
            result: SatResult::Timeout,
            dimacs: Vec::new(),
            proof: Vec::new(),
        });
    }
    let encoding = match build_encoding(table, gates, deadline) {
        Ok(encoding) => encoding,
        Err(_) if Instant::now() >= deadline => {
            return Ok(ExactSynthesis {
                result: SatResult::Timeout,
                dimacs: Vec::new(),
                proof: Vec::new(),
            });
        }
        Err(error) => return Err(error),
    };
    let dimacs = match encoding.dimacs_bytes(deadline) {
        Ok(dimacs) => dimacs,
        Err(_) if Instant::now() >= deadline => {
            return Ok(ExactSynthesis {
                result: SatResult::Timeout,
                dimacs: Vec::new(),
                proof: Vec::new(),
            });
        }
        Err(error) => return Err(error),
    };
    if Instant::now() >= deadline {
        return Ok(ExactSynthesis {
            result: SatResult::Timeout,
            dimacs,
            proof: Vec::new(),
        });
    }

    let mut solver = CaDiCaL::default();
    let proof_trace = ProofTrace::new();
    solver
        .trace_proof(&proof_trace.0, ProofFormat::Drat { binary: false })
        .map_err(|error| format!("attach CaDiCaL proof trace: {error}"))?;
    if Instant::now() >= deadline {
        return Ok(ExactSynthesis {
            result: SatResult::Timeout,
            dimacs,
            proof: Vec::new(),
        });
    }
    if encoding.next_variable > 0 {
        if let Err(error) = solver.reserve(Var::new(encoding.next_variable - 1)) {
            return Ok(ExactSynthesis {
                result: SatResult::Unknown(format!("CaDiCaL variable reservation failed: {error}")),
                dimacs,
                proof: Vec::new(),
            });
        }
        if Instant::now() >= deadline {
            return Ok(ExactSynthesis {
                result: SatResult::Timeout,
                dimacs,
                proof: Vec::new(),
            });
        }
    }
    for clause in &encoding.clauses {
        if Instant::now() >= deadline {
            return Ok(ExactSynthesis {
                result: SatResult::Timeout,
                dimacs,
                proof: Vec::new(),
            });
        }
        if let Err(error) = solver.add_clause(clause.iter().copied().collect::<Clause>()) {
            return Ok(ExactSynthesis {
                result: SatResult::Unknown(format!("CaDiCaL clause insertion failed: {error}")),
                dimacs,
                proof: Vec::new(),
            });
        }
    }
    let deadline_fired = Arc::new(AtomicBool::new(false));
    let callback_fired = Arc::clone(&deadline_fired);
    solver.attach_terminator(move || {
        if Instant::now() >= deadline {
            callback_fired.store(true, Ordering::Relaxed);
            ControlSignal::Terminate
        } else {
            ControlSignal::Continue
        }
    });
    let solved = match solver.solve() {
        Ok(result) => result,
        Err(error) => {
            return Ok(ExactSynthesis {
                result: SatResult::Unknown(format!("CaDiCaL solve error: {error}")),
                dimacs,
                proof: Vec::new(),
            });
        }
    };
    let result = match solved {
        SolverResult::Unsat => SatResult::Unsat,
        SolverResult::Interrupted => classify_interruption(deadline_fired.load(Ordering::Relaxed)),
        SolverResult::Sat => match decode_model(table, gates, &encoding, &solver, deadline) {
            Ok(circuit) => SatResult::Sat(circuit),
            Err(_) if Instant::now() >= deadline => SatResult::Timeout,
            Err(error) => SatResult::Unknown(format!("invalid SAT model: {error}")),
        },
    };
    if Instant::now() >= deadline {
        return Ok(ExactSynthesis {
            result: SatResult::Timeout,
            dimacs,
            proof: Vec::new(),
        });
    }
    drop(solver);
    let proof = if solved == SolverResult::Unsat {
        let proof = fs::read(&proof_trace.0)
            .map_err(|error| format!("read CaDiCaL proof trace: {error}"))?;
        if Instant::now() >= deadline {
            return Ok(ExactSynthesis {
                result: SatResult::Timeout,
                dimacs,
                proof: Vec::new(),
            });
        }
        proof
    } else {
        Vec::new()
    };
    Ok(ExactSynthesis {
        result,
        dimacs,
        proof,
    })
}

fn classify_interruption(deadline_fired: bool) -> SatResult {
    if deadline_fired {
        SatResult::Timeout
    } else {
        SatResult::Unknown("CaDiCaL interrupted before the absolute deadline".into())
    }
}

fn build_encoding(
    table: &CompleteTable,
    gate_count: usize,
    deadline: Instant,
) -> Result<Encoding, String> {
    let mut encoding = Encoding::new();
    let rows = table.outputs.len();

    for gate in 0..gate_count {
        if Instant::now() >= deadline {
            return Err("deadline expired while encoding SAT instance".into());
        }
        let source_count = 1 + table.ninputs + gate;
        let variables = GateVariables {
            xor: encoding.variable(),
            left_select: encoding.variables(source_count),
            left_inverted: encoding.variable(),
            left_values: encoding.variables(rows),
            right_select: encoding.variables(source_count),
            right_inverted: encoding.variable(),
            right_values: encoding.variables(rows),
            values: encoding.variables(rows),
        };
        encoding.exactly_one(&variables.left_select, deadline)?;
        encoding.exactly_one(&variables.right_select, deadline)?;

        // Constant fanins and two fanins from the same source would simplify,
        // contradicting this exact-bound gate's required reachability.
        encoding.clause([variables.left_select[0].neg_lit()]);
        encoding.clause([variables.right_select[0].neg_lit()]);
        for source in 0..source_count {
            if Instant::now() >= deadline {
                return Err("deadline expired while encoding SAT instance".into());
            }
            encoding.clause([
                variables.left_select[source].neg_lit(),
                variables.right_select[source].neg_lit(),
            ]);
        }
        // Canonical commutative fanin order.
        for left in 0..source_count {
            for right in 0..left {
                if Instant::now() >= deadline {
                    return Err("deadline expired while encoding SAT instance".into());
                }
                encoding.clause([
                    variables.left_select[left].neg_lit(),
                    variables.right_select[right].neg_lit(),
                ]);
            }
        }
        // XOR input negation can be moved to its output for free.
        encoding.clause([variables.xor.neg_lit(), variables.left_inverted.neg_lit()]);

        for row in 0..rows {
            for source in 0..source_count {
                if Instant::now() >= deadline {
                    return Err("deadline expired while encoding SAT instance".into());
                }
                let source_value = row_source(table, &encoding.gates, source, row);
                encoding.encode_selected_value(
                    variables.left_select[source],
                    source_value,
                    variables.left_inverted,
                    variables.left_values[row],
                );
                encoding.encode_selected_value(
                    variables.right_select[source],
                    source_value,
                    variables.right_inverted,
                    variables.right_values[row],
                );
            }
            encoding.encode_gate_truth(
                variables.xor,
                variables.left_values[row],
                variables.right_values[row],
                variables.values[row],
            );
        }
        encoding.gates.push(variables);
    }

    let output_source_count = 1 + table.ninputs + gate_count;
    for output in 0..table.noutputs {
        if Instant::now() >= deadline {
            return Err("deadline expired while encoding SAT instance".into());
        }
        let variables = OutputVariables {
            select: encoding.variables(output_source_count),
            inverted: encoding.variable(),
        };
        encoding.exactly_one(&variables.select, deadline)?;
        for row in 0..rows {
            for source in 0..output_source_count {
                if Instant::now() >= deadline {
                    return Err("deadline expired while encoding SAT instance".into());
                }
                let source_value = row_source(table, &encoding.gates, source, row);
                encoding.encode_selected_output(
                    variables.select[source],
                    source_value,
                    variables.inverted,
                    table.outputs[row][output],
                );
            }
        }
        encoding.outputs.push(variables);
    }

    // Each allocated gate has an immediate later consumer or an output.
    // Acyclicity then guarantees a path from every gate to some output.
    for gate in 0..gate_count {
        if Instant::now() >= deadline {
            return Err("deadline expired while encoding SAT instance".into());
        }
        let source = 1 + table.ninputs + gate;
        let mut consumers = Vec::new();
        for later in gate + 1..gate_count {
            consumers.push(encoding.gates[later].left_select[source].pos_lit());
            consumers.push(encoding.gates[later].right_select[source].pos_lit());
        }
        for output in &encoding.outputs {
            consumers.push(output.select[source].pos_lit());
        }
        encoding.clause(consumers);
    }

    // Forbid duplicate decoded gates. XOR polarity is canonicalized by Xag,
    // so equal XOR source pairs are duplicate regardless of right polarity.
    for earlier in 0..gate_count {
        for later in earlier + 1..gate_count {
            let common_sources = 1 + table.ninputs + earlier;
            for left in 1..common_sources {
                for right in left + 1..common_sources {
                    if Instant::now() >= deadline {
                        return Err("deadline expired while encoding SAT instance".into());
                    }
                    encoding.clause([
                        encoding.gates[earlier].xor.neg_lit(),
                        encoding.gates[later].xor.neg_lit(),
                        encoding.gates[earlier].left_select[left].neg_lit(),
                        encoding.gates[later].left_select[left].neg_lit(),
                        encoding.gates[earlier].right_select[right].neg_lit(),
                        encoding.gates[later].right_select[right].neg_lit(),
                    ]);
                    for left_polarity in [false, true] {
                        for right_polarity in [false, true] {
                            encoding.clause([
                                encoding.gates[earlier].xor.pos_lit(),
                                encoding.gates[later].xor.pos_lit(),
                                encoding.gates[earlier].left_select[left].neg_lit(),
                                encoding.gates[later].left_select[left].neg_lit(),
                                encoding.gates[earlier].right_select[right].neg_lit(),
                                encoding.gates[later].right_select[right].neg_lit(),
                                forbid_assignment(
                                    encoding.gates[earlier].left_inverted,
                                    left_polarity,
                                ),
                                forbid_assignment(
                                    encoding.gates[later].left_inverted,
                                    left_polarity,
                                ),
                                forbid_assignment(
                                    encoding.gates[earlier].right_inverted,
                                    right_polarity,
                                ),
                                forbid_assignment(
                                    encoding.gates[later].right_inverted,
                                    right_polarity,
                                ),
                            ]);
                        }
                    }
                }
            }
        }
    }
    if Instant::now() >= deadline {
        return Err("deadline expired while encoding SAT instance".into());
    }
    Ok(encoding)
}

fn row_source(
    table: &CompleteTable,
    gates: &[GateVariables],
    source: usize,
    row: usize,
) -> RowValue {
    if source == 0 {
        RowValue::Constant(false)
    } else if source <= table.ninputs {
        RowValue::Constant(((row >> (source - 1)) & 1) != 0)
    } else {
        RowValue::Variable(gates[source - 1 - table.ninputs].values[row])
    }
}

fn decode_model(
    table: &CompleteTable,
    gate_count: usize,
    encoding: &Encoding,
    solver: &CaDiCaL<'_, '_>,
    deadline: Instant,
) -> Result<Circuit, String> {
    let mut graph = Xag::new(table.ninputs);
    let mut sources: Vec<Lit> = std::iter::once(graph.f())
        .chain((0..table.ninputs).map(|input| graph.input(input)))
        .collect();
    for gate in 0..gate_count {
        if Instant::now() >= deadline {
            return Err("deadline expired during SAT model decoding".into());
        }
        let variables = &encoding.gates[gate];
        let left_source = selected_source(solver, &variables.left_select)?;
        let right_source = selected_source(solver, &variables.right_select)?;
        let mut left = sources[left_source];
        let mut right = sources[right_source];
        if model_value(solver, variables.left_inverted)? {
            left = left.not();
        }
        if model_value(solver, variables.right_inverted)? {
            right = right.not();
        }
        let literal = if model_value(solver, variables.xor)? {
            graph.xor(left, right)?
        } else {
            graph.and(left, right)?
        };
        sources.push(literal);
    }
    let mut outputs = Vec::with_capacity(table.noutputs);
    for variables in &encoding.outputs {
        if Instant::now() >= deadline {
            return Err("deadline expired during SAT model decoding".into());
        }
        let source = selected_source(solver, &variables.select)?;
        let mut literal = sources[source];
        if model_value(solver, variables.inverted)? {
            literal = literal.not();
        }
        outputs.push(literal);
    }
    let circuit = Circuit::new(graph, outputs)?;
    if circuit.reachable_gate_count()? != gate_count {
        return Err(format!(
            "decoded exact-{gate_count} model does not contain {gate_count} reachable gates"
        ));
    }
    assert_exhaustive_equivalence_before(table, &circuit, Some(deadline))?;
    Ok(circuit)
}

fn selected_source(solver: &CaDiCaL<'_, '_>, selectors: &[Var]) -> Result<usize, String> {
    selected_source_from_results(
        selectors
            .iter()
            .map(|variable| model_value(solver, *variable)),
    )
}

fn selected_source_from_results(
    values: impl IntoIterator<Item = Result<bool, String>>,
) -> Result<usize, String> {
    let mut selected = Vec::new();
    for (source, value) in values.into_iter().enumerate() {
        if value? {
            selected.push(source);
        }
    }
    if selected.len() != 1 {
        return Err(format!(
            "expected exactly one selected source, got {}",
            selected.len()
        ));
    }
    Ok(selected[0])
}

fn model_value(solver: &CaDiCaL<'_, '_>, variable: Var) -> Result<bool, String> {
    solver
        .var_val(variable)
        .map(|value| match value {
            TernaryVal::True => true,
            TernaryVal::False | TernaryVal::DontCare => false,
        })
        .map_err(|error| format!("read CaDiCaL model: {error}"))
}

fn complete_table_from_rows(ninputs: usize, rows: Vec<Vec<bool>>) -> Result<CompleteTable, String> {
    let noutputs = rows
        .first()
        .map(Vec::len)
        .ok_or_else(|| "complete table requires at least one row".to_string())?;
    let table = CompleteTable {
        ninputs,
        noutputs,
        outputs: rows,
    };
    validate_table(&table)?;
    Ok(table)
}

#[derive(Debug)]
enum ResynthesisStatus {
    Sat,
    Unsat,
    Timeout,
    Unknown(String),
}

struct NetlistResynthesis {
    replacement: Option<Circuit>,
    status: ResynthesisStatus,
    cuts_considered: usize,
    solver_calls: usize,
    encoded_bound: Option<usize>,
    requested_bound: Option<usize>,
    dimacs: Vec<u8>,
    proof: Vec<u8>,
}

#[allow(clippy::too_many_arguments)]
fn preserve_resynthesis_deadline_evidence(
    error: String,
    deadline: Instant,
    cuts_considered: usize,
    solver_calls: usize,
    encoded_bound: Option<usize>,
    requested_bound: Option<usize>,
    dimacs: Vec<u8>,
    proof: Vec<u8>,
) -> Result<NetlistResynthesis, String> {
    if Instant::now() < deadline {
        return Err(error);
    }
    Ok(NetlistResynthesis {
        replacement: None,
        status: ResynthesisStatus::Timeout,
        cuts_considered,
        solver_calls,
        encoded_bound,
        requested_bound,
        dimacs,
        proof,
    })
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
enum LocalNode {
    Input(usize),
    Gate(usize),
}

#[derive(Clone, Copy)]
struct LocalLit {
    node: LocalNode,
    inverted: bool,
}

#[derive(Clone, Copy)]
enum LocalOp {
    And,
    Or,
    Xor,
    Nand,
    Nor,
    Xnor,
}

#[derive(Clone, Copy)]
struct LocalGate {
    op: LocalOp,
    left: LocalLit,
    right: LocalLit,
}

struct LocalCircuit {
    ninputs: usize,
    gates: Vec<LocalGate>,
    outputs: Vec<LocalLit>,
}

struct Cut {
    root: usize,
    leaves: Vec<LocalNode>,
    internal_gates: usize,
}

fn resynthesize_local_cuts(text: &str, deadline: Instant) -> Result<NetlistResynthesis, String> {
    resynthesize_local_cuts_with_limits(
        text,
        deadline,
        FROZEN_CUT_BUDGET,
        FROZEN_SOLVER_CALL_BUDGET,
    )
}

fn resynthesize_local_cuts_with_limits(
    text: &str,
    deadline: Instant,
    cut_budget: usize,
    solver_call_budget: usize,
) -> Result<NetlistResynthesis, String> {
    if cut_budget > FROZEN_CUT_BUDGET {
        return Err(format!(
            "cut budget exceeds frozen maximum {FROZEN_CUT_BUDGET}"
        ));
    }
    if solver_call_budget > FROZEN_SOLVER_CALL_BUDGET {
        return Err(format!(
            "solver-call budget exceeds frozen maximum {FROZEN_SOLVER_CALL_BUDGET}"
        ));
    }
    Netlist::parse(text).map_err(|error| format!("parse input netlist: {error}"))?;
    if Instant::now() >= deadline {
        return Ok(NetlistResynthesis {
            replacement: None,
            status: ResynthesisStatus::Timeout,
            cuts_considered: 0,
            solver_calls: 0,
            encoded_bound: None,
            requested_bound: None,
            dimacs: Vec::new(),
            proof: Vec::new(),
        });
    }
    let local = parse_local_circuit(text)?;
    if Instant::now() >= deadline {
        return Ok(NetlistResynthesis {
            replacement: None,
            status: ResynthesisStatus::Timeout,
            cuts_considered: 0,
            solver_calls: 0,
            encoded_bound: None,
            requested_bound: None,
            dimacs: Vec::new(),
            proof: Vec::new(),
        });
    }
    let cuts = match enumerate_cuts(&local, MAX_CUT_INPUTS, cut_budget, deadline) {
        Ok(cuts) => cuts,
        Err(_) if Instant::now() >= deadline => {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Timeout,
                cuts_considered: 0,
                solver_calls: 0,
                encoded_bound: None,
                requested_bound: None,
                dimacs: Vec::new(),
                proof: Vec::new(),
            });
        }
        Err(error) => return Err(error),
    };
    let original_rows = match evaluate_local_all(&local, deadline) {
        Ok(rows) => rows,
        Err(_) if Instant::now() >= deadline => {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Timeout,
                cuts_considered: 0,
                solver_calls: 0,
                encoded_bound: None,
                requested_bound: None,
                dimacs: Vec::new(),
                proof: Vec::new(),
            });
        }
        Err(error) => return Err(error),
    };
    let mut calls = 0usize;
    let mut considered = 0usize;
    let mut last_dimacs = Vec::new();
    let mut last_proof = Vec::new();
    let mut encoded_bound = None;
    let mut requested_bound = None;

    macro_rules! post_solver_phase {
        ($operation:expr) => {
            match $operation {
                Ok(value) => value,
                Err(error) => {
                    return preserve_resynthesis_deadline_evidence(
                        error,
                        deadline,
                        considered,
                        calls,
                        encoded_bound,
                        requested_bound,
                        last_dimacs,
                        last_proof,
                    );
                }
            }
        };
    }

    for cut in cuts {
        if Instant::now() >= deadline {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Timeout,
                cuts_considered: considered,
                solver_calls: calls,
                encoded_bound,
                requested_bound,
                dimacs: last_dimacs,
                proof: last_proof,
            });
        }
        if calls == solver_call_budget {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Unknown("frozen solver-call budget exhausted".into()),
                cuts_considered: considered,
                solver_calls: calls,
                encoded_bound,
                requested_bound,
                dimacs: last_dimacs,
                proof: last_proof,
            });
        }
        considered += 1;
        let table = match cut_table(&local, &cut, deadline) {
            Ok(table) => table,
            Err(_) if Instant::now() >= deadline => {
                return Ok(NetlistResynthesis {
                    replacement: None,
                    status: ResynthesisStatus::Timeout,
                    cuts_considered: considered,
                    solver_calls: calls,
                    encoded_bound,
                    requested_bound,
                    dimacs: last_dimacs,
                    proof: last_proof,
                });
            }
            Err(error) => return Err(error),
        };
        let bound = cut
            .internal_gates
            .checked_sub(1)
            .expect("enumerated cuts contain their root gate");
        requested_bound = Some(bound);
        let first = synthesize_xag_at_most_with_diagnostics(
            &table,
            bound,
            deadline,
            solver_call_budget - calls,
        )?;
        calls += first.solver_calls;
        encoded_bound = first.encoded_bound;
        last_dimacs = first.dimacs;
        last_proof = first.proof;
        let candidate = match first.result {
            SatResult::Unsat => continue,
            SatResult::Timeout => {
                return Ok(NetlistResynthesis {
                    replacement: None,
                    status: ResynthesisStatus::Timeout,
                    cuts_considered: considered,
                    solver_calls: calls,
                    encoded_bound,
                    requested_bound,
                    dimacs: last_dimacs,
                    proof: last_proof,
                });
            }
            SatResult::Unknown(reason) => {
                return Ok(NetlistResynthesis {
                    replacement: None,
                    status: ResynthesisStatus::Unknown(reason),
                    cuts_considered: considered,
                    solver_calls: calls,
                    encoded_bound,
                    requested_bound,
                    dimacs: last_dimacs,
                    proof: last_proof,
                });
            }
            SatResult::Sat(candidate) => candidate,
        };
        if post_solver_phase!(candidate.reachable_gate_count()) >= cut.internal_gates {
            return Err("SAT cut replacement did not reduce reachable challenge gates".into());
        }
        post_solver_phase!(assert_exhaustive_equivalence_before(
            &table,
            &candidate,
            Some(deadline)
        ));

        if calls == solver_call_budget {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Unknown(
                    "deterministic rerun requires another solver call".into(),
                ),
                cuts_considered: considered,
                solver_calls: calls,
                encoded_bound,
                requested_bound,
                dimacs: last_dimacs,
                proof: last_proof,
            });
        }
        let second = post_solver_phase!(synthesize_xag_at_most_with_diagnostics(
            &table,
            bound,
            deadline,
            solver_call_budget - calls,
        ));
        calls += second.solver_calls;
        encoded_bound = second.encoded_bound;
        last_dimacs = second.dimacs;
        last_proof = second.proof;
        let rerun = match second.result {
            SatResult::Sat(rerun) => rerun,
            SatResult::Timeout => {
                return Ok(NetlistResynthesis {
                    replacement: None,
                    status: ResynthesisStatus::Timeout,
                    cuts_considered: considered,
                    solver_calls: calls,
                    encoded_bound,
                    requested_bound,
                    dimacs: last_dimacs,
                    proof: last_proof,
                });
            }
            SatResult::Unknown(reason) => {
                return Ok(NetlistResynthesis {
                    replacement: None,
                    status: ResynthesisStatus::Unknown(reason),
                    cuts_considered: considered,
                    solver_calls: calls,
                    encoded_bound,
                    requested_bound,
                    dimacs: last_dimacs,
                    proof: last_proof,
                });
            }
            SatResult::Unsat => {
                return Ok(NetlistResynthesis {
                    replacement: None,
                    status: ResynthesisStatus::Unknown(
                        "deterministic rerun changed SAT to UNSAT".into(),
                    ),
                    cuts_considered: considered,
                    solver_calls: calls,
                    encoded_bound,
                    requested_bound,
                    dimacs: last_dimacs,
                    proof: last_proof,
                });
            }
        };
        if post_solver_phase!(serialize_before_deadline(&rerun, deadline))
            != post_solver_phase!(serialize_before_deadline(&candidate, deadline))
        {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Unknown("deterministic SAT rerun bytes differ".into()),
                cuts_considered: considered,
                solver_calls: calls,
                encoded_bound,
                requested_bound,
                dimacs: last_dimacs,
                proof: last_proof,
            });
        }

        let rewritten = post_solver_phase!(reinsert_cut(&local, &cut, &candidate, deadline));
        let rewritten_text = post_solver_phase!(serialize_before_deadline(&rewritten, deadline));
        let rewritten_local = post_solver_phase!(parse_local_circuit(&rewritten_text));
        if post_solver_phase!(evaluate_local_all(&rewritten_local, deadline)) != original_rows {
            return Err("reinserted whole circuit failed exhaustive equivalence".into());
        }
        let rewritten_bytes = rewritten_text;
        let rerun_replacement = post_solver_phase!(reinsert_cut(&local, &cut, &rerun, deadline));
        let rerun_rewritten =
            post_solver_phase!(serialize_before_deadline(&rerun_replacement, deadline));
        if rewritten_bytes != rerun_rewritten {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Unknown(
                    "deterministic rewrite serialization differs".into(),
                ),
                cuts_considered: considered,
                solver_calls: calls,
                encoded_bound,
                requested_bound,
                dimacs: last_dimacs,
                proof: last_proof,
            });
        }
        let rewritten_gates = post_solver_phase!(Netlist::parse(&rewritten_bytes)).gate_count();
        if Instant::now() >= deadline {
            return Ok(NetlistResynthesis {
                replacement: None,
                status: ResynthesisStatus::Timeout,
                cuts_considered: considered,
                solver_calls: calls,
                encoded_bound,
                requested_bound,
                dimacs: last_dimacs,
                proof: last_proof,
            });
        }
        if rewritten_gates >= post_solver_phase!(reachable_local_gates(&local, deadline)) {
            continue;
        }
        return Ok(NetlistResynthesis {
            replacement: Some(rewritten),
            status: ResynthesisStatus::Sat,
            cuts_considered: considered,
            solver_calls: calls,
            encoded_bound,
            requested_bound,
            dimacs: last_dimacs,
            proof: last_proof,
        });
    }

    Ok(NetlistResynthesis {
        replacement: None,
        status: ResynthesisStatus::Unsat,
        cuts_considered: considered,
        solver_calls: calls,
        encoded_bound,
        requested_bound,
        dimacs: last_dimacs,
        proof: last_proof,
    })
}

fn parse_local_circuit(text: &str) -> Result<LocalCircuit, String> {
    let mut lines = text.lines();
    let ninputs = lines
        .next()
        .and_then(|line| line.strip_prefix("INPUTS "))
        .and_then(|value| value.parse::<usize>().ok())
        .ok_or_else(|| "invalid INPUTS header".to_string())?;
    let mut gates = Vec::new();
    let mut outputs = None;
    for line in lines {
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.first() == Some(&"OUTPUTS") {
            outputs = Some(
                fields[1..]
                    .iter()
                    .map(|field| parse_local_literal(field, ninputs))
                    .collect::<Result<Vec<_>, _>>()?,
            );
            continue;
        }
        let op = match fields.get(2).copied() {
            Some("AND") => LocalOp::And,
            Some("OR") => LocalOp::Or,
            Some("XOR") => LocalOp::Xor,
            Some("NAND") => LocalOp::Nand,
            Some("NOR") => LocalOp::Nor,
            Some("XNOR") => LocalOp::Xnor,
            _ => return Err("unsupported local gate operation".into()),
        };
        gates.push(LocalGate {
            op,
            left: parse_local_literal(fields[3], ninputs)?,
            right: parse_local_literal(fields[4], ninputs)?,
        });
    }
    Ok(LocalCircuit {
        ninputs,
        gates,
        outputs: outputs.ok_or_else(|| "missing OUTPUTS line".to_string())?,
    })
}

fn parse_local_literal(text: &str, ninputs: usize) -> Result<LocalLit, String> {
    let (inverted, name) = text
        .strip_prefix('~')
        .map_or((false, text), |name| (true, name));
    let node = if let Some(index) = name.strip_prefix('x') {
        LocalNode::Input(
            index
                .parse::<usize>()
                .map_err(|_| "invalid local input".to_string())?
                - 1,
        )
    } else if let Some(index) = name.strip_prefix('w') {
        LocalNode::Gate(
            index
                .parse::<usize>()
                .map_err(|_| "invalid local gate".to_string())?
                - 1,
        )
    } else {
        return Err(format!("invalid local literal {text}"));
    };
    if matches!(node, LocalNode::Input(index) if index >= ninputs) {
        return Err("local input is out of range".into());
    }
    Ok(LocalLit { node, inverted })
}

fn enumerate_cuts(
    circuit: &LocalCircuit,
    max_leaves: usize,
    limit: usize,
    deadline: Instant,
) -> Result<Vec<Cut>, String> {
    let live = live_local_gate_bitmap(circuit, deadline)?;
    let mut cuts = Vec::new();
    for (root, is_live) in live.iter().copied().enumerate() {
        if !is_live {
            continue;
        }
        let initial = vec![LocalNode::Gate(root)];
        let mut queue = VecDeque::from([initial.clone()]);
        let mut seen = BTreeSet::from([initial]);
        while let Some(leaves) = queue.pop_front() {
            if Instant::now() >= deadline {
                return Err("deadline expired during cut enumeration".into());
            }
            for position in 0..leaves.len() {
                let LocalNode::Gate(gate) = leaves[position] else {
                    continue;
                };
                let mut expanded = leaves.clone();
                expanded.remove(position);
                expanded.push(circuit.gates[gate].left.node);
                expanded.push(circuit.gates[gate].right.node);
                expanded.sort_unstable();
                expanded.dedup();
                if expanded.len() > max_leaves || !seen.insert(expanded.clone()) {
                    continue;
                }
                let internal_gates = internal_gate_count(circuit, root, &expanded, deadline)?;
                if internal_gates > 0 {
                    cuts.push(Cut {
                        root,
                        leaves: expanded.clone(),
                        internal_gates,
                    });
                    if cuts.len() == limit {
                        return Ok(cuts);
                    }
                }
                queue.push_back(expanded);
            }
        }
    }
    Ok(cuts)
}

fn internal_gate_count(
    circuit: &LocalCircuit,
    root: usize,
    leaves: &[LocalNode],
    deadline: Instant,
) -> Result<usize, String> {
    let leaves: BTreeSet<_> = leaves.iter().copied().collect();
    let mut seen = BTreeSet::new();
    let mut stack = vec![LocalNode::Gate(root)];
    while let Some(node) = stack.pop() {
        if Instant::now() >= deadline {
            return Err("deadline expired during cut enumeration".into());
        }
        if leaves.contains(&node) {
            continue;
        }
        if let LocalNode::Gate(gate) = node
            && seen.insert(gate)
        {
            stack.push(circuit.gates[gate].left.node);
            stack.push(circuit.gates[gate].right.node);
        }
    }
    Ok(seen.len())
}

fn cut_table(
    circuit: &LocalCircuit,
    cut: &Cut,
    deadline: Instant,
) -> Result<CompleteTable, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired during cut-table construction".into());
    }
    let rows = 1usize << cut.leaves.len();
    let mut outputs = Vec::with_capacity(rows);
    for row in 0..rows {
        if Instant::now() >= deadline {
            return Err("deadline expired during cut-table construction".into());
        }
        let mut memo = vec![None; circuit.gates.len()];
        let value = evaluate_cut_node(
            circuit,
            cut,
            LocalNode::Gate(cut.root),
            row,
            &mut memo,
            deadline,
        )?;
        outputs.push(vec![value]);
    }
    if Instant::now() >= deadline {
        return Err("deadline expired during cut-table construction".into());
    }
    complete_table_from_rows(cut.leaves.len(), outputs)
}

fn evaluate_cut_node(
    circuit: &LocalCircuit,
    cut: &Cut,
    node: LocalNode,
    assignment: usize,
    memo: &mut [Option<bool>],
    deadline: Instant,
) -> Result<bool, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired during cut-table construction".into());
    }
    if let Ok(leaf) = cut.leaves.binary_search(&node) {
        return Ok(((assignment >> leaf) & 1) != 0);
    }
    match node {
        LocalNode::Input(_) => Err("cut traversal reached a non-leaf input".into()),
        LocalNode::Gate(gate) => {
            if let Some(value) = memo[gate] {
                return Ok(value);
            }
            let definition = circuit.gates[gate];
            let left =
                evaluate_cut_literal(circuit, cut, definition.left, assignment, memo, deadline)?;
            let right =
                evaluate_cut_literal(circuit, cut, definition.right, assignment, memo, deadline)?;
            let value = apply_local_op(definition.op, left, right);
            memo[gate] = Some(value);
            Ok(value)
        }
    }
}

fn evaluate_cut_literal(
    circuit: &LocalCircuit,
    cut: &Cut,
    literal: LocalLit,
    assignment: usize,
    memo: &mut [Option<bool>],
    deadline: Instant,
) -> Result<bool, String> {
    Ok(
        evaluate_cut_node(circuit, cut, literal.node, assignment, memo, deadline)?
            ^ literal.inverted,
    )
}

fn apply_local_op(op: LocalOp, left: bool, right: bool) -> bool {
    match op {
        LocalOp::And => left & right,
        LocalOp::Or => left | right,
        LocalOp::Xor => left ^ right,
        LocalOp::Nand => !(left & right),
        LocalOp::Nor => !(left | right),
        LocalOp::Xnor => !(left ^ right),
    }
}

fn evaluate_local_all(circuit: &LocalCircuit, deadline: Instant) -> Result<Vec<Vec<bool>>, String> {
    const MAX_WHOLE_INPUTS: usize = 16;

    if Instant::now() >= deadline {
        return Err("deadline expired during whole-circuit evaluation".into());
    }
    if circuit.ninputs > MAX_WHOLE_INPUTS {
        return Err(format!(
            "whole-circuit exhaustive evaluation supports at most {MAX_WHOLE_INPUTS} inputs"
        ));
    }
    let rows = 1usize
        .checked_shl(circuit.ninputs as u32)
        .ok_or_else(|| "input dimensions overflow".to_string())?;
    let mut outputs = Vec::new();
    outputs
        .try_reserve_exact(rows)
        .map_err(|_| "whole-circuit truth table allocation failed".to_string())?;
    for row in 0..rows {
        if Instant::now() >= deadline {
            return Err("deadline expired during whole-circuit evaluation".into());
        }
        let inputs = encode_lsb(row as u64, circuit.ninputs);
        let mut gates = Vec::with_capacity(circuit.gates.len());
        for gate in &circuit.gates {
            if Instant::now() >= deadline {
                return Err("deadline expired during whole-circuit evaluation".into());
            }
            let left = local_literal_value(gate.left, &inputs, &gates);
            let right = local_literal_value(gate.right, &inputs, &gates);
            gates.push(apply_local_op(gate.op, left, right));
        }
        outputs.push(
            circuit
                .outputs
                .iter()
                .map(|literal| local_literal_value(*literal, &inputs, &gates))
                .collect(),
        );
    }
    if Instant::now() >= deadline {
        return Err("deadline expired during whole-circuit evaluation".into());
    }
    Ok(outputs)
}

fn local_literal_value(literal: LocalLit, inputs: &[bool], gates: &[bool]) -> bool {
    let value = match literal.node {
        LocalNode::Input(input) => inputs[input],
        LocalNode::Gate(gate) => gates[gate],
    };
    value ^ literal.inverted
}

fn canonicalize_local_circuit(
    circuit: &LocalCircuit,
    deadline: Instant,
) -> Result<Circuit, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired during circuit canonicalization".into());
    }
    let mut graph = Xag::new(circuit.ninputs);
    let inputs: Vec<_> = (0..circuit.ninputs)
        .map(|input| graph.input(input))
        .collect();
    let mut gates = Vec::with_capacity(circuit.gates.len());
    for definition in &circuit.gates {
        if Instant::now() >= deadline {
            return Err("deadline expired during circuit canonicalization".into());
        }
        let left = remap_local_literal(definition.left, &inputs, &gates)?;
        let right = remap_local_literal(definition.right, &inputs, &gates)?;
        gates.push(match definition.op {
            LocalOp::And => graph.and(left, right)?,
            LocalOp::Or => graph.or(left, right)?,
            LocalOp::Xor => graph.xor(left, right)?,
            LocalOp::Nand => graph.and(left, right)?.not(),
            LocalOp::Nor => graph.or(left, right)?.not(),
            LocalOp::Xnor => graph.xor(left, right)?.not(),
        });
    }
    let mut outputs = Vec::with_capacity(circuit.outputs.len());
    for literal in &circuit.outputs {
        if Instant::now() >= deadline {
            return Err("deadline expired during circuit canonicalization".into());
        }
        outputs.push(remap_local_literal(*literal, &inputs, &gates)?);
    }
    if Instant::now() >= deadline {
        return Err("deadline expired during circuit canonicalization".into());
    }
    Circuit::new(graph, outputs)
}

fn reinsert_cut(
    circuit: &LocalCircuit,
    cut: &Cut,
    replacement: &Circuit,
    deadline: Instant,
) -> Result<Circuit, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired during cut reinsertion".into());
    }
    let mut graph = Xag::new(circuit.ninputs);
    let inputs: Vec<_> = (0..circuit.ninputs)
        .map(|input| graph.input(input))
        .collect();
    let mut gates = Vec::with_capacity(circuit.gates.len());
    for gate in 0..circuit.gates.len() {
        if Instant::now() >= deadline {
            return Err("deadline expired during cut reinsertion".into());
        }
        let literal = if gate == cut.root {
            let leaf_literals = cut
                .leaves
                .iter()
                .map(|leaf| match *leaf {
                    LocalNode::Input(input) => Ok(inputs[input]),
                    LocalNode::Gate(gate) => gates
                        .get(gate)
                        .copied()
                        .ok_or_else(|| "cut leaf gate is not available".to_string()),
                })
                .collect::<Result<Vec<_>, _>>()?;
            insert_replacement(&mut graph, replacement, &leaf_literals, deadline)?
        } else {
            let definition = circuit.gates[gate];
            let left = remap_local_literal(definition.left, &inputs, &gates)?;
            let right = remap_local_literal(definition.right, &inputs, &gates)?;
            match definition.op {
                LocalOp::And => graph.and(left, right)?,
                LocalOp::Or => graph.or(left, right)?,
                LocalOp::Xor => graph.xor(left, right)?,
                LocalOp::Nand => graph.and(left, right)?.not(),
                LocalOp::Nor => graph.or(left, right)?.not(),
                LocalOp::Xnor => graph.xor(left, right)?.not(),
            }
        };
        gates.push(literal);
    }
    let mut outputs = Vec::with_capacity(circuit.outputs.len());
    for literal in &circuit.outputs {
        if Instant::now() >= deadline {
            return Err("deadline expired during cut reinsertion".into());
        }
        outputs.push(remap_local_literal(*literal, &inputs, &gates)?);
    }
    Circuit::new(graph, outputs)
}

fn remap_local_literal(literal: LocalLit, inputs: &[Lit], gates: &[Lit]) -> Result<Lit, String> {
    let mut mapped = match literal.node {
        LocalNode::Input(input) => inputs[input],
        LocalNode::Gate(gate) => gates
            .get(gate)
            .copied()
            .ok_or_else(|| "gate literal is not available".to_string())?,
    };
    if literal.inverted {
        mapped = mapped.not();
    }
    Ok(mapped)
}

fn insert_replacement(
    target: &mut Xag,
    replacement: &Circuit,
    inputs: &[Lit],
    deadline: Instant,
) -> Result<Lit, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired during replacement insertion".into());
    }
    if replacement.graph.input_count() != inputs.len() || replacement.outputs.len() != 1 {
        return Err("replacement cut dimensions do not match".into());
    }
    let mut sources = std::iter::once(target.f())
        .chain(inputs.iter().copied())
        .collect::<Vec<_>>();
    for gate in replacement.graph.gates() {
        if Instant::now() >= deadline {
            return Err("deadline expired during replacement insertion".into());
        }
        let left = remap_replacement_literal(&replacement.graph, gate.left, &sources)?;
        let right = remap_replacement_literal(&replacement.graph, gate.right, &sources)?;
        sources.push(match gate.op {
            Op::And => target.and(left, right)?,
            Op::Xor => target.xor(left, right)?,
        });
    }
    remap_replacement_literal(&replacement.graph, replacement.outputs[0], &sources)
}

fn remap_replacement_literal(graph: &Xag, literal: Lit, sources: &[Lit]) -> Result<Lit, String> {
    let formatted = graph.format_literal(literal)?;
    let (inverted, name) = formatted
        .strip_prefix('~')
        .map_or((false, formatted.as_str()), |name| (true, name));
    let source = if name == "0" {
        0
    } else if let Some(input) = name.strip_prefix('x') {
        input
            .parse::<usize>()
            .map_err(|_| "invalid replacement input literal".to_string())?
    } else if let Some(gate) = name.strip_prefix('w') {
        graph.input_count()
            + gate
                .parse::<usize>()
                .map_err(|_| "invalid replacement gate literal".to_string())?
    } else {
        return Err("invalid replacement literal".into());
    };
    let mut mapped = sources[source];
    if inverted {
        mapped = mapped.not();
    }
    Ok(mapped)
}

fn live_local_gate_bitmap(circuit: &LocalCircuit, deadline: Instant) -> Result<Vec<bool>, String> {
    let mut live = vec![false; circuit.gates.len()];
    let mut stack: Vec<_> = circuit.outputs.iter().map(|literal| literal.node).collect();
    while let Some(node) = stack.pop() {
        if Instant::now() >= deadline {
            return Err("deadline expired during reachable-gate analysis".into());
        }
        if let LocalNode::Gate(gate) = node {
            if live[gate] {
                continue;
            }
            live[gate] = true;
            stack.push(circuit.gates[gate].left.node);
            stack.push(circuit.gates[gate].right.node);
        }
    }
    Ok(live)
}

fn reachable_local_gates(circuit: &LocalCircuit, deadline: Instant) -> Result<usize, String> {
    Ok(live_local_gate_bitmap(circuit, deadline)?
        .into_iter()
        .filter(|live| *live)
        .count())
}

/// Narrow library-to-binary bridge. The CLI is a separate crate, while the
/// frozen budgets and both deadline windows remain unselectable by callers.
#[doc(hidden)]
pub fn run_resynthesis_command(
    input_path: &Path,
    output_dir: &Path,
    metrics_path: &Path,
) -> Result<(), String> {
    let started = Instant::now();
    run_resynthesis_command_at(
        input_path,
        output_dir,
        metrics_path,
        started + std::time::Duration::from_secs(285),
        started + std::time::Duration::from_secs(300),
    )
}

fn run_resynthesis_command_at(
    input_path: &Path,
    output_dir: &Path,
    metrics_path: &Path,
    deadline: Instant,
    cleanup_deadline: Instant,
) -> Result<(), String> {
    match run_resynthesis_operation_at(
        input_path,
        output_dir,
        metrics_path,
        deadline,
        cleanup_deadline,
    ) {
        Err(error) if classify_command_failure_as_timeout(&error, deadline) => {
            write_censored_timeout_report(output_dir, cleanup_deadline)?;
            Err("resynthesis timed out".into())
        }
        result => result,
    }
}

fn classify_command_failure_as_timeout(error: &str, deadline: Instant) -> bool {
    !error.starts_with("resynthesis solver result is unknown")
        && !error.starts_with("resynthesis timed out")
        && (Instant::now() >= deadline || error.contains("deadline expired"))
}

fn finish_post_solver_with_operation(
    output_dir: &Path,
    mut outcome: NetlistResynthesis,
    deadline: Instant,
    cleanup_deadline: Instant,
    operation: impl FnOnce(&NetlistResynthesis) -> Result<(), String>,
) -> Result<(), String> {
    let censored_error = match &outcome.status {
        ResynthesisStatus::Timeout => Some("resynthesis timed out"),
        ResynthesisStatus::Unknown(_) => Some("resynthesis solver result is unknown"),
        ResynthesisStatus::Sat | ResynthesisStatus::Unsat => None,
    };
    if let Some(error_prefix) = censored_error {
        return match publish_censored_resynthesis(output_dir, outcome, cleanup_deadline) {
            Ok(()) => Err(error_prefix.into()),
            Err(error) => Err(format!(
                "{error_prefix}; censored publication failed: {error}"
            )),
        };
    }

    match operation(&outcome) {
        Ok(()) => Ok(()),
        Err(error) if classify_command_failure_as_timeout(&error, deadline) => {
            outcome.status = ResynthesisStatus::Timeout;
            outcome.replacement = None;
            match publish_censored_resynthesis(output_dir, outcome, cleanup_deadline) {
                Ok(()) => Err("resynthesis timed out".into()),
                Err(publication_error) => Err(format!(
                    "resynthesis timed out; censored publication failed: {publication_error}"
                )),
            }
        }
        Err(error) => Err(error),
    }
}

fn run_resynthesis_operation_at(
    input_path: &Path,
    output_dir: &Path,
    metrics_path: &Path,
    deadline: Instant,
    cleanup_deadline: Instant,
) -> Result<(), String> {
    if metrics_path != output_dir.join("metrics.json") {
        return Err("--metrics-json must equal OUTPUT_DIR/metrics.json".into());
    }
    if Instant::now() >= deadline {
        write_censored_timeout_report(output_dir, cleanup_deadline)?;
        return Err("resynthesis timed out".into());
    }
    let original_bytes =
        fs::read(input_path).map_err(|error| format!("read INPUT_CIRCUIT: {error}"))?;
    if Instant::now() >= deadline {
        write_censored_timeout_report(output_dir, cleanup_deadline)?;
        return Err("resynthesis timed out".into());
    }
    let original_text = std::str::from_utf8(&original_bytes)
        .map_err(|_| "INPUT_CIRCUIT is not valid UTF-8".to_string())?;
    Netlist::parse(original_text).map_err(|error| format!("parse INPUT_CIRCUIT: {error}"))?;
    if Instant::now() >= deadline {
        return Err("deadline expired while parsing INPUT_CIRCUIT".into());
    }
    let local = parse_local_circuit(original_text)?;
    if Instant::now() >= deadline {
        return Err("deadline expired while parsing local circuit".into());
    }
    let canonical = match canonicalize_local_circuit(&local, deadline) {
        Ok(circuit) => circuit,
        Err(_) if Instant::now() >= deadline => {
            write_censored_timeout_report(output_dir, cleanup_deadline)?;
            return Err("resynthesis timed out".into());
        }
        Err(error) => return Err(error),
    };
    let canonical_bytes = serialize_before_deadline(&canonical, deadline)?.into_bytes();
    let original_rows = match evaluate_local_all(&local, deadline) {
        Ok(rows) => rows,
        Err(_) if Instant::now() >= deadline => {
            write_censored_timeout_report(output_dir, cleanup_deadline)?;
            return Err("resynthesis timed out".into());
        }
        Err(error) => return Err(error),
    };
    let noutputs = original_rows
        .first()
        .map(Vec::len)
        .filter(|outputs| *outputs > 0)
        .ok_or_else(|| "INPUT_CIRCUIT must have at least one output".to_string())?;
    let table = CompleteTable {
        ninputs: local.ninputs,
        noutputs,
        outputs: original_rows.clone(),
    };
    let original_gates = Netlist::parse(
        std::str::from_utf8(&canonical_bytes).expect("canonical XAG netlist is valid UTF-8"),
    )?
    .gate_count();
    if Instant::now() >= deadline {
        return Err("deadline expired while measuring canonical circuit".into());
    }

    let outcome = resynthesize_local_cuts(original_text, deadline)?;
    finish_post_solver_with_operation(output_dir, outcome, deadline, cleanup_deadline, |outcome| {
        publish_verified_resynthesis(
            output_dir,
            outcome,
            deadline,
            &canonical_bytes,
            &original_rows,
            &table,
            original_gates,
        )
    })
}

fn publish_verified_resynthesis(
    output_dir: &Path,
    outcome: &NetlistResynthesis,
    deadline: Instant,
    canonical_bytes: &[u8],
    original_rows: &[Vec<bool>],
    table: &CompleteTable,
    original_gates: usize,
) -> Result<(), String> {
    let status = match &outcome.status {
        ResynthesisStatus::Sat => "sat",
        ResynthesisStatus::Unsat => "unsat",
        ResynthesisStatus::Timeout | ResynthesisStatus::Unknown(_) => {
            return Err("censored outcome reached success publication".into());
        }
    };
    let selected_bytes = match &outcome.replacement {
        Some(replacement) => serialize_before_deadline(replacement, deadline)?.into_bytes(),
        None => clone_bytes_before_deadline(canonical_bytes, deadline, "canonical circuit")?,
    };
    let selected_text = std::str::from_utf8(&selected_bytes)
        .map_err(|_| "selected circuit is not valid UTF-8".to_string())?;
    let selected_local = parse_local_circuit(selected_text)?;
    if Instant::now() >= deadline {
        return Err("deadline expired while parsing selected circuit".into());
    }
    let selected_rows = evaluate_local_all(&selected_local, deadline)?;
    if selected_rows != original_rows {
        return Err("selected whole circuit failed exhaustive equivalence".into());
    }
    let selected_gates = Netlist::parse(selected_text)?.gate_count();
    if Instant::now() >= deadline {
        return Err("deadline expired while measuring selected circuit".into());
    }
    let gate_delta = selected_gates as i128 - original_gates as i128;
    let completed_bytes = completed_table_csv_bytes_before_deadline(&table, deadline)?;
    let completed_sha256 = sha256_before_deadline(&completed_bytes, deadline, "completed table")?;
    let circuit_sha256 = sha256_before_deadline(&selected_bytes, deadline, "selected circuit")?;
    let artifact = format!(
        "{{\"circuit_path\":\"circuit.txt\",\"circuit_sha256\":\"{circuit_sha256}\",\"completed_table_path\":\"completed-table.csv\",\"completed_table_sha256\":\"{completed_sha256}\",\"equivalence\":\"pass\",\"schema_version\":1}}\n"
    )
    .into_bytes();
    let metrics = format!(
        "{{\"completed_table_sha256\":\"{completed_sha256}\",\"gates\":{selected_gates},\"train_exact\":1.0,\"verifier\":\"not_run\",\"visible_cv_bit_accuracy\":1.0,\"visible_cv_exact\":1.0}}\n"
    )
    .into_bytes();
    let dimacs_digest = if outcome.dimacs.is_empty() {
        "null".to_string()
    } else {
        format!(
            "\"{}\"",
            sha256_before_deadline(&outcome.dimacs, deadline, "DIMACS")?
        )
    };
    let proof_digest = if outcome.proof.is_empty() {
        "null".to_string()
    } else {
        format!(
            "\"{}\"",
            sha256_before_deadline(&outcome.proof, deadline, "proof")?
        )
    };
    let encoded_bound = outcome
        .encoded_bound
        .map(|bound| bound.to_string())
        .unwrap_or_else(|| "null".into());
    let requested_bound = outcome
        .requested_bound
        .map(|bound| bound.to_string())
        .unwrap_or_else(|| "null".into());
    let sat_report = format!(
        "{{\"cut_budget\":{FROZEN_CUT_BUDGET},\"cuts_considered\":{},\"dimacs_sha256\":{dimacs_digest},\"encoded_bound\":{encoded_bound},\"exhaustive_equivalence\":\"pass\",\"max_cut_inputs\":{MAX_CUT_INPUTS},\"proof_checked\":false,\"proof_sha256\":{proof_digest},\"requested_bound\":{requested_bound},\"rewrites_accepted\":{},\"sat_status\":\"{status}\",\"solver_call_budget\":{FROZEN_SOLVER_CALL_BUDGET},\"solver_calls\":{},\"unknown_reason_sha256\":null,\"verifier_status\":\"not-run\",\"whole_circuit_gate_delta\":{gate_delta}}}\n",
        outcome.cuts_considered,
        usize::from(status == "sat"),
        outcome.solver_calls,
    )
    .into_bytes();

    let mut artifacts = vec![
        ("artifact.json", artifact),
        ("circuit.txt", selected_bytes),
        ("completed-table.csv", completed_bytes),
        ("metrics.json", metrics),
        ("sat-report.json", sat_report),
    ];
    if !outcome.dimacs.is_empty() {
        artifacts.push((
            "sat-instance.cnf",
            clone_bytes_before_deadline(&outcome.dimacs, deadline, "DIMACS artifact")?,
        ));
    }
    if !outcome.proof.is_empty() {
        artifacts.push((
            "sat-proof.drat",
            clone_bytes_before_deadline(&outcome.proof, deadline, "proof artifact")?,
        ));
    }
    publish_command_artifacts(output_dir, artifacts, deadline)
}

fn clone_bytes_before_deadline(
    bytes: &[u8],
    deadline: Instant,
    label: &str,
) -> Result<Vec<u8>, String> {
    if Instant::now() >= deadline {
        return Err(format!("deadline expired before cloning {label}"));
    }
    let cloned = bytes.to_vec();
    if Instant::now() >= deadline {
        return Err(format!("deadline expired while cloning {label}"));
    }
    Ok(cloned)
}

fn sha256_before_deadline(bytes: &[u8], deadline: Instant, label: &str) -> Result<String, String> {
    if Instant::now() >= deadline {
        return Err(format!("deadline expired before hashing {label}"));
    }
    let digest = sha256_hex(bytes);
    if Instant::now() >= deadline {
        return Err(format!("deadline expired while hashing {label}"));
    }
    Ok(digest)
}

fn serialize_before_deadline(circuit: &Circuit, deadline: Instant) -> Result<String, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired before circuit serialization".into());
    }
    let serialized = circuit.to_netlist()?;
    if Instant::now() >= deadline {
        return Err("deadline expired during circuit serialization".into());
    }
    Ok(serialized)
}

fn completed_table_csv_bytes_before_deadline(
    table: &CompleteTable,
    deadline: Instant,
) -> Result<Vec<u8>, String> {
    if Instant::now() >= deadline {
        return Err("deadline expired before completed-table serialization".into());
    }
    let mut csv = String::from("input,output\n");
    for (mask, output) in table.outputs.iter().enumerate() {
        if Instant::now() >= deadline {
            return Err("deadline expired during completed-table serialization".into());
        }
        csv.push_str(&encode_bits(&encode_lsb(mask as u64, table.ninputs)));
        csv.push(',');
        csv.push_str(&encode_bits(output));
        csv.push('\n');
    }
    if Instant::now() >= deadline {
        return Err("deadline expired after completed-table serialization".into());
    }
    Ok(csv.into_bytes())
}

fn publish_command_artifacts(
    output_dir: &Path,
    artifacts: Vec<(&str, Vec<u8>)>,
    deadline: Instant,
) -> Result<(), String> {
    publish_artifacts_atomically_with_expiry(output_dir, artifacts, || Instant::now() >= deadline)
}

fn publish_artifacts_atomically_with_expiry(
    output_dir: &Path,
    artifacts: Vec<(&str, Vec<u8>)>,
    expired: impl FnMut() -> bool,
) -> Result<(), String> {
    publish_artifacts_atomically_with_controls(output_dir, artifacts, expired, |file, bytes| {
        file.write_all(bytes).and_then(|()| file.sync_all())
    })
}

fn publish_artifacts_atomically_with_controls(
    output_dir: &Path,
    artifacts: Vec<(&str, Vec<u8>)>,
    mut expired: impl FnMut() -> bool,
    mut write_and_sync: impl FnMut(&mut fs::File, &[u8]) -> std::io::Result<()>,
) -> Result<(), String> {
    if expired() {
        return Err("deadline expired before artifact publication".into());
    }
    match fs::symlink_metadata(output_dir) {
        Ok(_) => {
            return Err(format!(
                "OUTPUT_DIR already exists: {}",
                output_dir.display()
            ));
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => return Err(format!("inspect OUTPUT_DIR: {error}")),
    }

    let ticket = NEXT_ARTIFACT_PUBLISH.fetch_add(1, Ordering::Relaxed);
    let parent = output_dir
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let output_name = output_dir
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| "OUTPUT_DIR must have a UTF-8 final component".to_string())?;
    let stage_dir = parent.join(format!(
        ".{output_name}.occam-stage-{}-{ticket}",
        std::process::id()
    ));
    fs::create_dir(&stage_dir)
        .map_err(|error| format!("create evidence staging directory: {error}"))?;

    for (name, bytes) in artifacts {
        if expired() {
            let _ = fs::remove_dir_all(&stage_dir);
            return Err("deadline expired during artifact publication".into());
        }
        let staged_path = stage_dir.join(name);
        let mut file = match fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&staged_path)
        {
            Ok(file) => file,
            Err(error) => {
                let _ = fs::remove_dir_all(&stage_dir);
                return Err(format!("stage {}: {error}", staged_path.display()));
            }
        };
        if let Err(error) = write_and_sync(&mut file, &bytes) {
            drop(file);
            let _ = fs::remove_dir_all(&stage_dir);
            return Err(format!("stage {}: {error}", staged_path.display()));
        }
        drop(file);
        if expired() {
            let _ = fs::remove_dir_all(&stage_dir);
            return Err("deadline expired during artifact publication".into());
        }
    }

    let stage_handle = match fs::File::open(&stage_dir) {
        Ok(handle) => handle,
        Err(error) => {
            let _ = fs::remove_dir_all(&stage_dir);
            return Err(format!("open evidence staging directory: {error}"));
        }
    };
    if let Err(error) = stage_handle.sync_all() {
        let _ = fs::remove_dir_all(&stage_dir);
        return Err(format!("sync evidence staging directory: {error}"));
    }
    if expired() {
        let _ = fs::remove_dir_all(&stage_dir);
        return Err("deadline expired during artifact publication".into());
    }
    if output_dir.exists() {
        let _ = fs::remove_dir_all(&stage_dir);
        return Err(format!(
            "OUTPUT_DIR already exists: {}",
            output_dir.display()
        ));
    }
    if let Err(error) = fs::rename(&stage_dir, output_dir) {
        let _ = fs::remove_dir_all(&stage_dir);
        return Err(format!(
            "commit evidence directory {}: {error}",
            output_dir.display()
        ));
    }
    if expired() {
        if let Err(cleanup_error) = fs::remove_dir_all(output_dir) {
            return Err(format!(
                "deadline expired after artifact publication; remove committed evidence: {cleanup_error}"
            ));
        }
        return Err("deadline expired after artifact publication".into());
    }
    let parent_handle = match fs::File::open(parent) {
        Ok(handle) => handle,
        Err(error) => {
            let _ = fs::remove_dir_all(output_dir);
            return Err(format!("open evidence parent directory: {error}"));
        }
    };
    if let Err(error) = parent_handle.sync_all() {
        let _ = fs::remove_dir_all(output_dir);
        return Err(format!("sync evidence parent directory: {error}"));
    }
    if expired() {
        if let Err(cleanup_error) = fs::remove_dir_all(output_dir) {
            return Err(format!(
                "deadline expired after parent directory sync; remove committed evidence: {cleanup_error}"
            ));
        }
        if let Err(cleanup_sync_error) = parent_handle.sync_all() {
            return Err(format!(
                "deadline expired after parent directory sync; sync evidence rollback: {cleanup_sync_error}"
            ));
        }
        return Err("deadline expired after parent directory sync".into());
    }
    Ok(())
}

fn write_censored_timeout_report(
    output_dir: &Path,
    cleanup_deadline: Instant,
) -> Result<(), String> {
    publish_censored_resynthesis(
        output_dir,
        NetlistResynthesis {
            replacement: None,
            status: ResynthesisStatus::Timeout,
            cuts_considered: 0,
            solver_calls: 0,
            encoded_bound: None,
            requested_bound: None,
            dimacs: Vec::new(),
            proof: Vec::new(),
        },
        cleanup_deadline,
    )
}

fn publish_censored_resynthesis(
    output_dir: &Path,
    outcome: NetlistResynthesis,
    cleanup_deadline: Instant,
) -> Result<(), String> {
    let (status, unknown_reason) = match &outcome.status {
        ResynthesisStatus::Timeout => ("timeout", "null".to_string()),
        ResynthesisStatus::Unknown(reason) => (
            "unknown",
            format!(
                "\"{}\"",
                sha256_before_deadline(reason.as_bytes(), cleanup_deadline, "unknown reason")?
            ),
        ),
        ResynthesisStatus::Sat | ResynthesisStatus::Unsat => {
            return Err("only timeout or unknown outcomes may be censored".into());
        }
    };
    let dimacs_digest = if outcome.dimacs.is_empty() {
        "null".to_string()
    } else {
        format!(
            "\"{}\"",
            sha256_before_deadline(&outcome.dimacs, cleanup_deadline, "censored DIMACS")?
        )
    };
    let proof_digest = if outcome.proof.is_empty() {
        "null".to_string()
    } else {
        format!(
            "\"{}\"",
            sha256_before_deadline(&outcome.proof, cleanup_deadline, "censored proof")?
        )
    };
    let encoded_bound = outcome
        .encoded_bound
        .map(|bound| bound.to_string())
        .unwrap_or_else(|| "null".into());
    let requested_bound = outcome
        .requested_bound
        .map(|bound| bound.to_string())
        .unwrap_or_else(|| "null".into());
    let report = format!(
        "{{\"cut_budget\":{FROZEN_CUT_BUDGET},\"cuts_considered\":{},\"dimacs_sha256\":{dimacs_digest},\"encoded_bound\":{encoded_bound},\"exhaustive_equivalence\":\"not-run\",\"max_cut_inputs\":{MAX_CUT_INPUTS},\"proof_checked\":false,\"proof_sha256\":{proof_digest},\"requested_bound\":{requested_bound},\"rewrites_accepted\":0,\"sat_status\":\"{status}\",\"solver_call_budget\":{FROZEN_SOLVER_CALL_BUDGET},\"solver_calls\":{},\"unknown_reason_sha256\":{unknown_reason},\"verifier_status\":\"not-run\",\"whole_circuit_gate_delta\":null}}\n",
        outcome.cuts_considered, outcome.solver_calls,
    )
    .into_bytes();
    let mut artifacts = vec![("sat-report.json", report)];
    if !outcome.dimacs.is_empty() {
        artifacts.push(("sat-instance.cnf", outcome.dimacs));
    }
    if !outcome.proof.is_empty() {
        artifacts.push(("sat-proof.drat", outcome.proof));
    }
    publish_command_artifacts(output_dir, artifacts, cleanup_deadline)
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::io;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{Duration, Instant};

    use super::{
        CompleteTable, Cut, Encoding, LocalNode, NetlistResynthesis, ResynthesisStatus, SatResult,
        assert_exhaustive_equivalence_before, canonicalize_local_circuit,
        classify_command_failure_as_timeout, classify_interruption,
        completed_table_csv_bytes_before_deadline, cut_table, evaluate_local_all,
        finish_post_solver_with_operation, parse_local_circuit,
        preserve_resynthesis_deadline_evidence, publish_artifacts_atomically_with_controls,
        publish_artifacts_atomically_with_expiry, publish_censored_resynthesis,
        publish_command_artifacts, reinsert_cut, resynthesize_local_cuts,
        resynthesize_local_cuts_with_limits, run_resynthesis_command_at,
        selected_source_from_results, serialize_before_deadline, sha256_before_deadline,
        sha256_hex,
    };

    static NEXT_TEMP: AtomicU64 = AtomicU64::new(0);

    struct TempDir(PathBuf);

    impl TempDir {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "occam-sat-unit-{}-{}",
                std::process::id(),
                NEXT_TEMP.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn interrupted_solver_is_unknown_without_the_deadline_signal() {
        assert!(matches!(
            classify_interruption(false),
            SatResult::Unknown(reason) if reason.contains("before the absolute deadline")
        ));
        assert!(matches!(classify_interruption(true), SatResult::Timeout));
    }

    #[test]
    fn selector_decode_propagates_a_model_read_error() {
        let error = selected_source_from_results([
            Ok(false),
            Err("injected model read failure".to_string()),
            Ok(true),
        ])
        .unwrap_err();

        assert_eq!(error, "injected model read failure");
    }

    #[test]
    fn exactly_one_checks_injected_expiry_inside_both_pairwise_loops() {
        let mut outer_encoding = Encoding::new();
        let outer_variables = outer_encoding.variables(1);
        let mut outer_checks = 0usize;
        let outer_error = outer_encoding
            .exactly_one_with_expiry(&outer_variables, || {
                outer_checks += 1;
                outer_checks >= 2
            })
            .unwrap_err();
        assert_eq!(outer_error, "deadline expired during exactly-one encoding");
        assert_eq!(outer_encoding.clauses.len(), 1);

        let mut inner_encoding = Encoding::new();
        let inner_variables = inner_encoding.variables(3);
        let mut inner_checks = 0usize;
        let inner_error = inner_encoding
            .exactly_one_with_expiry(&inner_variables, || {
                inner_checks += 1;
                inner_checks >= 4
            })
            .unwrap_err();
        assert_eq!(inner_error, "deadline expired during exactly-one encoding");
        assert_eq!(inner_encoding.clauses.len(), 2);
    }

    #[test]
    fn expired_rewrite_deadline_is_classified_as_timeout_during_cut_enumeration() {
        let outcome = resynthesize_local_cuts(
            "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n",
            Instant::now() - Duration::from_secs(1),
        )
        .unwrap();

        assert!(matches!(outcome.status, ResynthesisStatus::Timeout));
        assert_eq!(outcome.solver_calls, 0);
    }

    #[test]
    fn internal_rewrite_rejects_budgets_above_the_frozen_limits() {
        let text = "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n";
        let deadline = Instant::now() + Duration::from_secs(5);

        let Err(cut_error) = resynthesize_local_cuts_with_limits(text, deadline, 129, 64) else {
            panic!("an oversized cut budget must be rejected");
        };
        assert_eq!(cut_error, "cut budget exceeds frozen maximum 128");
        let Err(call_error) = resynthesize_local_cuts_with_limits(text, deadline, 128, 65) else {
            panic!("an oversized solver-call budget must be rejected");
        };
        assert_eq!(call_error, "solver-call budget exceeds frozen maximum 64");
    }

    #[test]
    fn every_expensive_non_solver_phase_checks_an_expired_deadline() {
        let expired = Instant::now() - Duration::from_secs(1);
        let local = parse_local_circuit("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n").unwrap();
        let canonical =
            canonicalize_local_circuit(&local, Instant::now() + Duration::from_secs(5)).unwrap();
        let table = CompleteTable::from_fn(2, 1, |row| (row & 1) ^ ((row >> 1) & 1));
        let cut = Cut {
            root: 0,
            leaves: vec![LocalNode::Input(0), LocalNode::Input(1)],
            internal_gates: 1,
        };
        let encoding = Encoding::new();
        let temporary = TempDir::new();

        assert_eq!(
            encoding.dimacs_bytes(expired).unwrap_err(),
            "deadline expired during DIMACS construction"
        );
        assert_eq!(
            evaluate_local_all(&local, expired).unwrap_err(),
            "deadline expired during whole-circuit evaluation"
        );
        assert_eq!(
            cut_table(&local, &cut, expired).unwrap_err(),
            "deadline expired during cut-table construction"
        );
        assert_eq!(
            canonicalize_local_circuit(&local, expired).unwrap_err(),
            "deadline expired during circuit canonicalization"
        );
        assert_eq!(
            assert_exhaustive_equivalence_before(&table, &canonical, Some(expired)).unwrap_err(),
            "deadline expired during exhaustive equivalence"
        );
        assert_eq!(
            reinsert_cut(&local, &cut, &canonical, expired).unwrap_err(),
            "deadline expired during cut reinsertion"
        );
        assert_eq!(
            serialize_before_deadline(&canonical, expired).unwrap_err(),
            "deadline expired before circuit serialization"
        );
        assert_eq!(
            completed_table_csv_bytes_before_deadline(&table, expired).unwrap_err(),
            "deadline expired before completed-table serialization"
        );
        assert_eq!(
            sha256_before_deadline(b"diagnostic", expired, "diagnostic").unwrap_err(),
            "deadline expired before hashing diagnostic"
        );
        assert_eq!(
            publish_command_artifacts(
                &temporary.0.join("cell"),
                vec![("artifact.json", Vec::new())],
                expired,
            )
            .unwrap_err(),
            "deadline expired before artifact publication"
        );
    }

    #[test]
    fn whole_circuit_evaluation_rejects_more_than_sixteen_inputs() {
        let local = parse_local_circuit("INPUTS 17\nOUTPUTS x1\n").unwrap();

        assert_eq!(
            evaluate_local_all(&local, Instant::now() + Duration::from_secs(5)).unwrap_err(),
            "whole-circuit exhaustive evaluation supports at most 16 inputs"
        );
    }

    #[test]
    fn deterministic_rerun_without_budget_preserves_first_solver_diagnostics() {
        let outcome = resynthesize_local_cuts_with_limits(
            "INPUTS 1\nw1 = XOR x1 x1\nOUTPUTS w1\n",
            Instant::now() + Duration::from_secs(5),
            128,
            1,
        )
        .unwrap();

        assert!(matches!(
            outcome.status,
            ResynthesisStatus::Unknown(ref reason)
                if reason == "deterministic rerun requires another solver call"
        ));
        assert_eq!(outcome.solver_calls, 1);
        assert_eq!(outcome.encoded_bound, Some(0));
        assert!(!outcome.dimacs.is_empty());
    }

    #[test]
    fn injected_post_solver_deadline_keeps_resynthesis_evidence() {
        let dimacs = b"p cnf 2 1\n1 2 0\n".to_vec();
        let proof = b"0\n".to_vec();
        let outcome = preserve_resynthesis_deadline_evidence(
            "deadline expired during injected reachability".into(),
            Instant::now() - Duration::from_secs(1),
            6,
            3,
            Some(2),
            Some(4),
            dimacs.clone(),
            proof.clone(),
        )
        .unwrap();

        assert!(matches!(outcome.status, ResynthesisStatus::Timeout));
        assert_eq!(outcome.cuts_considered, 6);
        assert_eq!(outcome.solver_calls, 3);
        assert_eq!(outcome.encoded_bound, Some(2));
        assert_eq!(outcome.requested_bound, Some(4));
        assert_eq!(outcome.dimacs, dimacs);
        assert_eq!(outcome.proof, proof);
    }

    #[test]
    fn timeout_writes_a_censored_report_and_never_success_metrics() {
        let temporary = TempDir::new();
        let input = temporary.0.join("input.txt");
        let output = temporary.0.join("cell");
        fs::write(&input, "INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n").unwrap();

        let error = run_resynthesis_command_at(
            &input,
            &output,
            &output.join("metrics.json"),
            Instant::now() - Duration::from_secs(1),
            Instant::now() + Duration::from_secs(5),
        )
        .unwrap_err();

        assert_eq!(error, "resynthesis timed out");
        assert!(
            fs::read_to_string(output.join("sat-report.json"))
                .unwrap()
                .contains("\"sat_status\":\"timeout\"")
        );
        assert!(!output.join("metrics.json").exists());
        assert!(!output.join("artifact.json").exists());
    }

    #[test]
    fn censored_timeout_preserves_bounds_solver_work_and_diagnostics() {
        let temporary = TempDir::new();
        let output = temporary.0.join("cell");
        let dimacs = b"p cnf 1 1\n1 0\n".to_vec();
        let proof = b"0\n".to_vec();
        let outcome = NetlistResynthesis {
            replacement: None,
            status: ResynthesisStatus::Timeout,
            cuts_considered: 7,
            solver_calls: 3,
            encoded_bound: Some(2),
            requested_bound: Some(3),
            dimacs: dimacs.clone(),
            proof: proof.clone(),
        };

        publish_censored_resynthesis(&output, outcome, Instant::now() + Duration::from_secs(5))
            .unwrap();

        let report = fs::read_to_string(output.join("sat-report.json")).unwrap();
        assert!(report.contains("\"sat_status\":\"timeout\""));
        assert!(report.contains("\"cuts_considered\":7"));
        assert!(report.contains("\"solver_calls\":3"));
        assert!(report.contains("\"encoded_bound\":2"));
        assert!(report.contains("\"requested_bound\":3"));
        assert!(report.contains(&format!("\"dimacs_sha256\":\"{}\"", sha256_hex(&dimacs))));
        assert!(report.contains(&format!("\"proof_sha256\":\"{}\"", sha256_hex(&proof))));
        assert_eq!(fs::read(output.join("sat-instance.cnf")).unwrap(), dimacs);
        assert_eq!(fs::read(output.join("sat-proof.drat")).unwrap(), proof);
        assert!(!output.join("metrics.json").exists());
        assert!(!output.join("artifact.json").exists());
    }

    #[test]
    fn post_solver_deadline_preserves_the_real_solver_outcome() {
        let temporary = TempDir::new();
        let output = temporary.0.join("cell");
        let dimacs = b"p cnf 2 1\n1 2 0\n".to_vec();
        let proof = b"0\n".to_vec();
        let outcome = NetlistResynthesis {
            replacement: None,
            status: ResynthesisStatus::Sat,
            cuts_considered: 9,
            solver_calls: 5,
            encoded_bound: Some(3),
            requested_bound: Some(4),
            dimacs: dimacs.clone(),
            proof: proof.clone(),
        };

        let error = finish_post_solver_with_operation(
            &output,
            outcome,
            Instant::now() + Duration::from_secs(5),
            Instant::now() + Duration::from_secs(10),
            |_outcome| Err("deadline expired during injected post-solver phase".into()),
        )
        .unwrap_err();

        assert_eq!(error, "resynthesis timed out");
        let report = fs::read_to_string(output.join("sat-report.json")).unwrap();
        assert!(report.contains("\"sat_status\":\"timeout\""));
        assert!(report.contains("\"cuts_considered\":9"));
        assert!(report.contains("\"solver_calls\":5"));
        assert!(report.contains("\"encoded_bound\":3"));
        assert!(report.contains("\"requested_bound\":4"));
        assert_eq!(fs::read(output.join("sat-instance.cnf")).unwrap(), dimacs);
        assert_eq!(fs::read(output.join("sat-proof.drat")).unwrap(), proof);
    }

    #[test]
    fn frozen_unknown_uses_cleanup_deadline_and_is_not_reclassified() {
        let temporary = TempDir::new();
        let output = temporary.0.join("cell");
        let reason = "injected lower-bound indeterminate result";
        let outcome = NetlistResynthesis {
            replacement: None,
            status: ResynthesisStatus::Unknown(reason.into()),
            cuts_considered: 4,
            solver_calls: 2,
            encoded_bound: Some(1),
            requested_bound: Some(2),
            dimacs: Vec::new(),
            proof: Vec::new(),
        };

        publish_censored_resynthesis(&output, outcome, Instant::now() + Duration::from_secs(5))
            .unwrap();

        let report = fs::read_to_string(output.join("sat-report.json")).unwrap();
        assert!(report.contains("\"sat_status\":\"unknown\""));
        assert!(report.contains(&format!(
            "\"unknown_reason_sha256\":\"{}\"",
            sha256_hex(reason.as_bytes())
        )));
        assert!(!classify_command_failure_as_timeout(
            "resynthesis solver result is unknown",
            Instant::now() - Duration::from_secs(1),
        ));
    }

    #[test]
    fn atomic_publication_rolls_back_staged_and_installed_files() {
        let temporary = TempDir::new();
        let expired_output = temporary.0.join("expired");
        let mut checks = 0usize;
        let deadline_error = publish_artifacts_atomically_with_expiry(
            &expired_output,
            vec![("sat-report.json", b"complete report".to_vec())],
            || {
                checks += 1;
                checks >= 4
            },
        )
        .unwrap_err();
        assert_eq!(
            deadline_error,
            "deadline expired during artifact publication"
        );
        assert!(!expired_output.exists());

        let collision_output = temporary.0.join("collision");
        fs::create_dir(&collision_output).unwrap();
        fs::write(collision_output.join("sat-report.json"), b"runner-owned").unwrap();
        let collision_error = publish_artifacts_atomically_with_expiry(
            &collision_output,
            vec![
                ("sat-instance.cnf", b"diagnostic".to_vec()),
                ("sat-report.json", b"new report".to_vec()),
            ],
            || false,
        )
        .unwrap_err();
        assert!(collision_error.contains("OUTPUT_DIR already exists"));
        assert_eq!(
            fs::read(collision_output.join("sat-report.json")).unwrap(),
            b"runner-owned"
        );
        assert!(!collision_output.join("sat-instance.cnf").exists());
        assert_eq!(fs::read_dir(&collision_output).unwrap().count(), 1);
    }

    #[test]
    fn atomic_publication_rolls_back_a_staged_write_or_sync_failure() {
        let temporary = TempDir::new();
        let output = temporary.0.join("write-failure");

        let error = publish_artifacts_atomically_with_controls(
            &output,
            vec![("sat-report.json", b"complete report".to_vec())],
            || false,
            |_file, _bytes| Err(io::Error::other("injected write/sync failure")),
        )
        .unwrap_err();

        assert!(error.contains("injected write/sync failure"));
        assert!(!output.exists());
    }

    #[test]
    fn atomic_publication_rolls_back_when_deadline_expires_after_parent_sync() {
        let temporary = TempDir::new();
        let output = temporary.0.join("post-parent-sync-expiry");
        let mut checks = 0usize;

        let error = publish_artifacts_atomically_with_expiry(
            &output,
            vec![("sat-report.json", b"complete report".to_vec())],
            || {
                checks += 1;
                checks >= 6
            },
        )
        .unwrap_err();

        assert_eq!(error, "deadline expired after parent directory sync");
        assert!(!output.exists());
    }
}
