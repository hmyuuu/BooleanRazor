use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};

use crate::robdd::SharedRobdd;
use crate::table::CompleteTable;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OrderScore {
    pub order: Vec<usize>,
    pub bdd_nodes: usize,
    pub xag_gates: usize,
}

impl OrderScore {
    pub fn ranking_key(&self) -> (usize, usize, &[usize]) {
        (self.xag_gates, self.bdd_nodes, &self.order)
    }
}

impl Ord for OrderScore {
    fn cmp(&self, other: &Self) -> Ordering {
        self.ranking_key().cmp(&other.ranking_key())
    }
}

impl PartialOrd for OrderScore {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Debug)]
pub struct OrderScorer<'table> {
    table: &'table CompleteTable,
    cache: HashMap<Vec<usize>, (usize, usize)>,
    unique_evaluations: usize,
}

impl<'table> OrderScorer<'table> {
    pub fn new(table: &'table CompleteTable) -> Result<Self, String> {
        validate_table(table)?;
        Ok(Self {
            table,
            cache: HashMap::new(),
            unique_evaluations: 0,
        })
    }

    pub fn score(&mut self, order: &[usize]) -> Result<OrderScore, String> {
        validate_order(self.table.ninputs, order)?;
        if let Some(&(bdd_nodes, xag_gates)) = self.cache.get(order) {
            return Ok(OrderScore {
                order: order.to_vec(),
                bdd_nodes,
                xag_gates,
            });
        }

        let forest = SharedRobdd::build(self.table, order.to_vec())?;
        let bdd_nodes = forest.shared_node_count();
        let circuit = forest.extract_xag()?;
        let xag_gates = circuit.reachable_gate_count()?;
        self.cache.insert(order.to_vec(), (bdd_nodes, xag_gates));
        self.unique_evaluations = self
            .unique_evaluations
            .checked_add(1)
            .ok_or_else(|| "order evaluation counter overflow".to_string())?;
        Ok(OrderScore {
            order: order.to_vec(),
            bdd_nodes,
            xag_gates,
        })
    }

    pub fn unique_evaluations(&self) -> usize {
        self.unique_evaluations
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SearchProgress {
    pub round: usize,
    pub best: OrderScore,
    pub unique_evaluations: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SearchResult {
    pub finalists: Vec<OrderScore>,
    pub history: Vec<SearchProgress>,
    pub rounds_completed: usize,
}

pub fn seed_orders(operand_bits: usize) -> Result<Vec<Vec<usize>>, String> {
    let nvars = operand_bits
        .checked_mul(2)
        .ok_or_else(|| "variable order dimensions overflow".to_string())?;
    let grouped_lsb = (0..nvars).collect::<Vec<_>>();
    let grouped_msb = (0..operand_bits)
        .rev()
        .chain((operand_bits..nvars).rev())
        .collect::<Vec<_>>();
    let interleaved_lsb = (0..operand_bits)
        .flat_map(|bit| [bit, operand_bits + bit])
        .collect::<Vec<_>>();
    let interleaved_msb = (0..operand_bits)
        .rev()
        .flat_map(|bit| [bit, operand_bits + bit])
        .collect::<Vec<_>>();
    let forward = [grouped_lsb, grouped_msb, interleaved_lsb, interleaved_msb];

    let mut orders = Vec::with_capacity(8);
    let mut seen = HashSet::with_capacity(8);
    for order in forward.iter().cloned().chain(
        forward
            .iter()
            .map(|order| order.iter().rev().copied().collect()),
    ) {
        if seen.insert(order.clone()) {
            orders.push(order);
        }
    }
    Ok(orders)
}

pub fn adjacent_hill_climb(
    scorer: &mut OrderScorer<'_>,
    start: &[usize],
    max_rounds: usize,
) -> Result<SearchResult, String> {
    adjacent_hill_climb_with_callback(scorer, start, max_rounds, |_| Ok(()))
}

pub fn adjacent_hill_climb_with_callback<F>(
    scorer: &mut OrderScorer<'_>,
    start: &[usize],
    max_rounds: usize,
    mut callback: F,
) -> Result<SearchResult, String>
where
    F: FnMut(&SearchProgress) -> Result<(), String>,
{
    let mut current = scorer.score(start)?;
    let mut history = Vec::new();
    record_progress(&mut history, 0, &current, scorer, &mut callback)?;
    let mut rounds_completed = 0;

    for round in 1..=max_rounds {
        rounds_completed = round;
        let mut best_neighbor: Option<OrderScore> = None;
        for index in 0..current.order.len().saturating_sub(1) {
            let mut neighbor = current.order.clone();
            neighbor.swap(index, index + 1);
            let score = scorer.score(&neighbor)?;
            if best_neighbor.as_ref().is_none_or(|best| score < *best) {
                best_neighbor = Some(score);
            }
        }
        let Some(best_neighbor) = best_neighbor else {
            break;
        };
        if best_neighbor >= current {
            break;
        }
        current = best_neighbor;
        record_progress(&mut history, round, &current, scorer, &mut callback)?;
    }

    Ok(SearchResult {
        finalists: vec![current],
        history,
        rounds_completed,
    })
}

pub fn beam_search(
    scorer: &mut OrderScorer<'_>,
    seeds: &[Vec<usize>],
    beam_width: usize,
    max_rounds: usize,
) -> Result<SearchResult, String> {
    beam_search_with_callback(scorer, seeds, beam_width, max_rounds, |_| Ok(()))
}

pub fn beam_search_with_callback<F>(
    scorer: &mut OrderScorer<'_>,
    seeds: &[Vec<usize>],
    beam_width: usize,
    max_rounds: usize,
    mut callback: F,
) -> Result<SearchResult, String>
where
    F: FnMut(&SearchProgress) -> Result<(), String>,
{
    if seeds.is_empty() {
        return Err("beam search requires at least one seed".into());
    }
    if beam_width == 0 {
        return Err("beam width must be positive".into());
    }

    let mut seen = HashSet::with_capacity(seeds.len());
    let mut beam = Vec::with_capacity(seeds.len());
    for seed in seeds {
        if seen.insert(seed.clone()) {
            beam.push(scorer.score(seed)?);
        }
    }
    beam.sort();
    beam.truncate(beam_width);

    let mut global_best = beam[0].clone();
    let mut history = Vec::new();
    record_progress(&mut history, 0, &global_best, scorer, &mut callback)?;
    let mut rounds_completed = 0;

    for round in 1..=max_rounds {
        rounds_completed = round;
        let candidate_capacity = beam
            .len()
            .checked_mul(scorer.table.ninputs)
            .ok_or_else(|| "beam candidate dimensions overflow".to_string())?;
        let mut orders = Vec::with_capacity(candidate_capacity);
        let mut seen = HashSet::with_capacity(candidate_capacity);
        for score in &beam {
            if seen.insert(score.order.clone()) {
                orders.push(score.order.clone());
            }
            for index in 0..score.order.len().saturating_sub(1) {
                let mut neighbor = score.order.clone();
                neighbor.swap(index, index + 1);
                if seen.insert(neighbor.clone()) {
                    orders.push(neighbor);
                }
            }
        }

        let mut next = Vec::with_capacity(orders.len());
        for order in orders {
            next.push(scorer.score(&order)?);
        }
        next.sort();
        next.truncate(beam_width);
        if next == beam {
            break;
        }
        beam = next;
        if beam[0] < global_best {
            global_best = beam[0].clone();
            record_progress(&mut history, round, &global_best, scorer, &mut callback)?;
        }
    }

    Ok(SearchResult {
        finalists: beam,
        history,
        rounds_completed,
    })
}

pub fn search_csv_bytes(instance: &str, finalists: &[OrderScore]) -> Result<Vec<u8>, String> {
    if instance.is_empty()
        || instance
            .bytes()
            .any(|byte| matches!(byte, b',' | b'\r' | b'\n'))
    {
        return Err("instance is not valid for search CSV".into());
    }
    let mut csv = String::from("instance,rank,xag_gates,bdd_nodes,order\n");
    for (rank, score) in finalists.iter().enumerate() {
        let order = score
            .order
            .iter()
            .map(usize::to_string)
            .collect::<Vec<_>>()
            .join(":");
        csv.push_str(&format!(
            "{instance},{rank},{},{},{order}\n",
            score.xag_gates, score.bdd_nodes
        ));
    }
    Ok(csv.into_bytes())
}

fn record_progress<F>(
    history: &mut Vec<SearchProgress>,
    round: usize,
    best: &OrderScore,
    scorer: &OrderScorer<'_>,
    callback: &mut F,
) -> Result<(), String>
where
    F: FnMut(&SearchProgress) -> Result<(), String>,
{
    let progress = SearchProgress {
        round,
        best: best.clone(),
        unique_evaluations: scorer.unique_evaluations(),
    };
    history.push(progress);
    callback(history.last().expect("progress was just appended"))
}

fn validate_table(table: &CompleteTable) -> Result<(), String> {
    let shift = u32::try_from(table.ninputs)
        .map_err(|_| "complete table dimensions overflow".to_string())?;
    let row_count = 1usize
        .checked_shl(shift)
        .ok_or_else(|| "complete table dimensions overflow".to_string())?;
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
