use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};

use crate::netlist::serialized_challenge_gate_count;
use crate::order::seed_orders;
use crate::reblind::visible_folds;
use crate::robdd::{BddEdge, SharedRobdd};
use crate::table::{CompleteTable, PartialTable};
use crate::xag::Circuit;

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub enum EmptyCarePolicy {
    ReuseSibling,
    Zero,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CrossValidationScore {
    pub validation_exact_rows: usize,
    pub validation_rows: usize,
    pub validation_bit_correct: usize,
    pub validation_bits: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BlindScore {
    pub order: Vec<usize>,
    pub policy: EmptyCarePolicy,
    pub validation_exact_rows: usize,
    pub validation_rows: usize,
    pub validation_bit_correct: usize,
    pub validation_bits: usize,
    pub refit_xag_gates: usize,
    pub refit_bdd_nodes: usize,
}

impl Ord for BlindScore {
    fn cmp(&self, other: &Self) -> Ordering {
        match compare_ratio(
            self.validation_exact_rows,
            self.validation_rows,
            other.validation_exact_rows,
            other.validation_rows,
        ) {
            Ordering::Greater => return Ordering::Less,
            Ordering::Less => return Ordering::Greater,
            Ordering::Equal => {}
        }
        match self.refit_xag_gates.cmp(&other.refit_xag_gates) {
            Ordering::Equal => {}
            ordering => return ordering,
        }
        match compare_ratio(
            self.validation_bit_correct,
            self.validation_bits,
            other.validation_bit_correct,
            other.validation_bits,
        ) {
            Ordering::Greater => return Ordering::Less,
            Ordering::Less => return Ordering::Greater,
            Ordering::Equal => {}
        }
        self.refit_bdd_nodes
            .cmp(&other.refit_bdd_nodes)
            .then_with(|| self.policy.cmp(&other.policy))
            .then_with(|| self.order.cmp(&other.order))
            .then_with(|| self.validation_rows.cmp(&other.validation_rows))
            .then_with(|| self.validation_exact_rows.cmp(&other.validation_exact_rows))
            .then_with(|| self.validation_bits.cmp(&other.validation_bits))
            .then_with(|| {
                self.validation_bit_correct
                    .cmp(&other.validation_bit_correct)
            })
    }
}

impl PartialOrd for BlindScore {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Debug)]
pub struct BlindOrderScorer<'table> {
    table: &'table PartialTable,
    folds: usize,
    seed_hex: String,
    cv_cache: HashMap<(Vec<usize>, EmptyCarePolicy), CrossValidationScore>,
    retained_cache: HashMap<(Vec<usize>, EmptyCarePolicy), BlindScore>,
    unique_cv_evaluations: usize,
    unique_retained_evaluations: usize,
}

impl<'table> BlindOrderScorer<'table> {
    pub fn new(table: &'table PartialTable, folds: usize, seed_hex: &str) -> Result<Self, String> {
        validate_partial_table(table)?;
        validate_cross_validation_shape(table, folds)?;
        visible_folds(table, seed_hex, folds)?;
        Ok(Self {
            table,
            folds,
            seed_hex: seed_hex.to_owned(),
            cv_cache: HashMap::new(),
            retained_cache: HashMap::new(),
            unique_cv_evaluations: 0,
            unique_retained_evaluations: 0,
        })
    }

    pub fn cross_validation_score(
        &mut self,
        order: &[usize],
        policy: EmptyCarePolicy,
    ) -> Result<CrossValidationScore, String> {
        let key = (order.to_vec(), policy);
        if let Some(score) = self.cv_cache.get(&key) {
            return Ok(score.clone());
        }
        let score = cross_validate_care_set(self.table, order, policy, self.folds, &self.seed_hex)?;
        self.cv_cache.insert(key, score.clone());
        self.unique_cv_evaluations = self
            .unique_cv_evaluations
            .checked_add(1)
            .ok_or_else(|| "cross-validation evaluation counter overflow".to_string())?;
        Ok(score)
    }

    pub fn score_retained(
        &mut self,
        order: &[usize],
        policy: EmptyCarePolicy,
    ) -> Result<BlindScore, String> {
        let key = (order.to_vec(), policy);
        if let Some(score) = self.retained_cache.get(&key) {
            return Ok(score.clone());
        }
        let validation = self.cross_validation_score(order, policy)?;
        let forest = fit_care_forest(self.table, order, policy)?;
        for (input, expected) in &self.table.rows {
            if forest.evaluate(input)? != *expected {
                return Err("care-set refit does not reproduce an observed row".into());
            }
        }
        let refit_bdd_nodes = forest.shared_node_count();
        let refit_xag_gates = serialized_challenge_gate_count(&forest.extract_xag()?)?;
        let score = BlindScore {
            order: order.to_vec(),
            policy,
            validation_exact_rows: validation.validation_exact_rows,
            validation_rows: validation.validation_rows,
            validation_bit_correct: validation.validation_bit_correct,
            validation_bits: validation.validation_bits,
            refit_xag_gates,
            refit_bdd_nodes,
        };
        self.retained_cache.insert(key, score.clone());
        self.unique_retained_evaluations = self
            .unique_retained_evaluations
            .checked_add(1)
            .ok_or_else(|| "retained-order evaluation counter overflow".to_string())?;
        Ok(score)
    }

    pub fn unique_cv_evaluations(&self) -> usize {
        self.unique_cv_evaluations
    }

    pub fn unique_retained_evaluations(&self) -> usize {
        self.unique_retained_evaluations
    }

    fn bounded_cross_validation_score(
        &mut self,
        order: &[usize],
        policy: EmptyCarePolicy,
        max_evaluations: usize,
    ) -> Result<Option<CrossValidationScore>, String> {
        let key = (order.to_vec(), policy);
        if let Some(score) = self.cv_cache.get(&key) {
            return Ok(Some(score.clone()));
        }
        if self.unique_cv_evaluations >= max_evaluations {
            return Ok(None);
        }
        self.cross_validation_score(order, policy).map(Some)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BlindSearchProgress {
    pub round: usize,
    pub best: BlindScore,
    pub unique_cv_evaluations: usize,
    pub unique_retained_evaluations: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BlindSearchResult {
    pub finalists: Vec<BlindScore>,
    pub history: Vec<BlindSearchProgress>,
    pub rounds_completed: usize,
    pub budget_exhausted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct CvCandidate {
    order: Vec<usize>,
    score: CrossValidationScore,
}

pub fn blind_seed_orders(ninputs: usize) -> Result<Vec<Vec<usize>>, String> {
    if ninputs % 2 != 0 {
        return Err("blind seed orders require an even input width".into());
    }
    seed_orders(ninputs / 2)
}

pub fn blind_adjacent_hill_climb(
    scorer: &mut BlindOrderScorer<'_>,
    start: &[usize],
    policy: EmptyCarePolicy,
    max_rounds: usize,
    max_evaluations: usize,
) -> Result<BlindSearchResult, String> {
    blind_beam_search(
        scorer,
        &[start.to_vec()],
        policy,
        1,
        max_rounds,
        max_evaluations,
    )
}

pub fn blind_beam_search(
    scorer: &mut BlindOrderScorer<'_>,
    seeds: &[Vec<usize>],
    policy: EmptyCarePolicy,
    beam_width: usize,
    max_rounds: usize,
    max_evaluations: usize,
) -> Result<BlindSearchResult, String> {
    blind_beam_search_with_callback(
        scorer,
        seeds,
        policy,
        beam_width,
        max_rounds,
        max_evaluations,
        |_| Ok(()),
    )
}

pub fn blind_beam_search_with_callback<F>(
    scorer: &mut BlindOrderScorer<'_>,
    seeds: &[Vec<usize>],
    policy: EmptyCarePolicy,
    beam_width: usize,
    max_rounds: usize,
    max_evaluations: usize,
    mut callback: F,
) -> Result<BlindSearchResult, String>
where
    F: FnMut(&BlindSearchProgress) -> Result<(), String>,
{
    if seeds.is_empty() {
        return Err("blind beam search requires at least one seed".into());
    }
    if beam_width == 0 {
        return Err("blind beam width must be positive".into());
    }
    if max_evaluations == 0 {
        return Err("maximum order evaluations must be positive".into());
    }
    for seed in seeds {
        validate_order(scorer.table.ninputs, seed)?;
    }

    let mut seen = HashSet::with_capacity(seeds.len());
    let initial_orders = seeds
        .iter()
        .filter(|order| seen.insert((*order).clone()))
        .cloned()
        .collect::<Vec<_>>();
    let (initial_candidates, mut budget_exhausted) =
        evaluate_orders(scorer, initial_orders, policy, max_evaluations)?;
    let mut beam = rank_retained_candidates(scorer, initial_candidates, policy, beam_width)?;
    let mut history = Vec::new();
    record_blind_progress(&mut history, 0, &beam[0], scorer, &mut callback)?;
    let mut rounds_completed = 0;

    if !budget_exhausted {
        for round in 1..=max_rounds {
            rounds_completed = round;
            let candidate_capacity = beam
                .len()
                .checked_mul(scorer.table.ninputs)
                .ok_or_else(|| "blind beam candidate dimensions overflow".to_string())?;
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
            let (candidates, exhausted) = evaluate_orders(scorer, orders, policy, max_evaluations)?;
            budget_exhausted |= exhausted;
            let next = rank_retained_candidates(scorer, candidates, policy, beam_width)?;
            if next == beam {
                break;
            }
            beam = next;
            if beam[0] < history.last().expect("history is nonempty").best {
                record_blind_progress(&mut history, round, &beam[0], scorer, &mut callback)?;
            }
            if budget_exhausted {
                break;
            }
        }
    }

    Ok(BlindSearchResult {
        finalists: beam,
        history,
        rounds_completed,
        budget_exhausted,
    })
}

pub fn blind_search_csv_bytes(instance: &str, finalists: &[BlindScore]) -> Result<Vec<u8>, String> {
    if instance.is_empty()
        || instance
            .bytes()
            .any(|byte| matches!(byte, b',' | b'\r' | b'\n'))
    {
        return Err("instance is not valid for blind search CSV".into());
    }
    let mut csv = String::from(
        "instance,rank,validation_exact_rows,validation_rows,refit_xag_gates,validation_bit_correct,validation_bits,refit_bdd_nodes,policy,order\n",
    );
    for (rank, score) in finalists.iter().enumerate() {
        let policy = match score.policy {
            EmptyCarePolicy::ReuseSibling => "reuse-sibling",
            EmptyCarePolicy::Zero => "zero",
        };
        let order = score
            .order
            .iter()
            .map(usize::to_string)
            .collect::<Vec<_>>()
            .join(":");
        csv.push_str(&format!(
            "{instance},{rank},{},{},{},{},{},{},{policy},{order}\n",
            score.validation_exact_rows,
            score.validation_rows,
            score.refit_xag_gates,
            score.validation_bit_correct,
            score.validation_bits,
            score.refit_bdd_nodes,
        ));
    }
    Ok(csv.into_bytes())
}

fn evaluate_orders(
    scorer: &mut BlindOrderScorer<'_>,
    orders: Vec<Vec<usize>>,
    policy: EmptyCarePolicy,
    max_evaluations: usize,
) -> Result<(Vec<CvCandidate>, bool), String> {
    let mut candidates = Vec::with_capacity(orders.len());
    for order in orders {
        let Some(score) = scorer.bounded_cross_validation_score(&order, policy, max_evaluations)?
        else {
            return Ok((candidates, true));
        };
        candidates.push(CvCandidate { order, score });
    }
    Ok((candidates, false))
}

fn rank_retained_candidates(
    scorer: &mut BlindOrderScorer<'_>,
    mut candidates: Vec<CvCandidate>,
    policy: EmptyCarePolicy,
    beam_width: usize,
) -> Result<Vec<BlindScore>, String> {
    if candidates.is_empty() {
        return Err("blind search evaluation budget retained no candidate".into());
    }
    candidates.sort_by(|left, right| {
        compare_ratio(
            right.score.validation_exact_rows,
            right.score.validation_rows,
            left.score.validation_exact_rows,
            left.score.validation_rows,
        )
        .then_with(|| left.order.cmp(&right.order))
    });

    let mut retained = Vec::with_capacity(beam_width.min(candidates.len()));
    let mut begin = 0;
    while begin < candidates.len() && retained.len() < beam_width {
        let mut end = begin + 1;
        while end < candidates.len()
            && compare_ratio(
                candidates[begin].score.validation_exact_rows,
                candidates[begin].score.validation_rows,
                candidates[end].score.validation_exact_rows,
                candidates[end].score.validation_rows,
            ) == Ordering::Equal
        {
            end += 1;
        }
        let mut accuracy_ties = Vec::with_capacity(end - begin);
        for candidate in &candidates[begin..end] {
            accuracy_ties.push(scorer.score_retained(&candidate.order, policy)?);
        }
        accuracy_ties.sort();
        let remaining = beam_width - retained.len();
        retained.extend(accuracy_ties.into_iter().take(remaining));
        begin = end;
    }
    retained.sort();
    Ok(retained)
}

fn record_blind_progress<F>(
    history: &mut Vec<BlindSearchProgress>,
    round: usize,
    best: &BlindScore,
    scorer: &BlindOrderScorer<'_>,
    callback: &mut F,
) -> Result<(), String>
where
    F: FnMut(&BlindSearchProgress) -> Result<(), String>,
{
    let progress = BlindSearchProgress {
        round,
        best: best.clone(),
        unique_cv_evaluations: scorer.unique_cv_evaluations(),
        unique_retained_evaluations: scorer.unique_retained_evaluations(),
    };
    history.push(progress);
    callback(history.last().expect("progress was just appended"))
}

pub fn complete_care_set(
    table: &PartialTable,
    order: &[usize],
    policy: EmptyCarePolicy,
) -> Result<(CompleteTable, Circuit), String> {
    validate_partial_table(table)?;
    let forest = fit_care_forest(table, order, policy)?;
    let row_count = table_row_count(table.ninputs)?;
    let mut outputs = Vec::with_capacity(row_count);
    for mask in 0..row_count {
        outputs.push(forest.evaluate_mask(mask)?);
    }
    let completed = CompleteTable {
        ninputs: table.ninputs,
        noutputs: table.noutputs,
        outputs,
    };
    table.validate_against(&completed)?;

    let circuit = forest.extract_xag()?;
    if circuit.evaluate_all()? != completed.outputs {
        return Err("care ROBDD and extracted XAG disagree".into());
    }
    for (input, expected) in &table.rows {
        if circuit.evaluate(input)? != *expected {
            return Err("care-set circuit does not reproduce an observed row".into());
        }
    }
    Ok((completed, circuit))
}

pub fn cross_validate_care_set(
    table: &PartialTable,
    order: &[usize],
    policy: EmptyCarePolicy,
    folds: usize,
    seed_hex: &str,
) -> Result<CrossValidationScore, String> {
    validate_partial_table(table)?;
    validate_cross_validation_shape(table, folds)?;
    let fold_rows = visible_folds(table, seed_hex, folds)?;
    let mut validation_exact_rows = 0usize;
    let mut validation_rows = 0usize;
    let mut validation_bit_correct = 0usize;
    let mut validation_bits = 0usize;

    for held_out in fold_rows {
        if held_out.is_empty() {
            continue;
        }
        let mut is_held_out = vec![false; table.rows.len()];
        for &row in &held_out {
            is_held_out[row] = true;
        }
        let training = PartialTable {
            ninputs: table.ninputs,
            noutputs: table.noutputs,
            rows: table
                .rows
                .iter()
                .enumerate()
                .filter(|(row, _)| !is_held_out[*row])
                .map(|(_, sample)| sample.clone())
                .collect(),
        };
        if training.rows.is_empty() {
            return Err("cross-validation fold leaves no training rows".into());
        }
        let forest = fit_care_forest(&training, order, policy)?;
        for &row in &held_out {
            let (input, expected) = &table.rows[row];
            let predicted = forest.evaluate(input)?;
            validation_rows = checked_add(validation_rows, 1, "validation row count")?;
            validation_bits = checked_add(validation_bits, table.noutputs, "validation bit count")?;
            let bit_correct = predicted
                .iter()
                .zip(expected)
                .filter(|(got, want)| got == want)
                .count();
            validation_bit_correct = checked_add(
                validation_bit_correct,
                bit_correct,
                "validation correct-bit count",
            )?;
            if predicted == *expected {
                validation_exact_rows =
                    checked_add(validation_exact_rows, 1, "validation exact-row count")?;
            }
        }
    }

    if validation_rows != table.rows.len() {
        return Err("cross-validation folds do not cover every visible row exactly once".into());
    }
    Ok(CrossValidationScore {
        validation_exact_rows,
        validation_rows,
        validation_bit_correct,
        validation_bits,
    })
}

fn fit_care_forest(
    table: &PartialTable,
    order: &[usize],
    policy: EmptyCarePolicy,
) -> Result<SharedRobdd, String> {
    let mut forest = SharedRobdd::new_care(table.ninputs, order.to_vec())?;
    let care_rows = (0..table.rows.len()).collect::<Vec<_>>();
    let mut roots = Vec::with_capacity(table.noutputs);
    for output in 0..table.noutputs {
        let root = build_output(&mut forest, table, &care_rows, output, order, 0, policy)?
            .ok_or_else(|| "care-set output root cannot be empty".to_string())?;
        roots.push(root);
    }
    forest.finish_care(roots)
}

fn build_output(
    forest: &mut SharedRobdd,
    table: &PartialTable,
    care_rows: &[usize],
    output: usize,
    order: &[usize],
    depth: usize,
    policy: EmptyCarePolicy,
) -> Result<Option<BddEdge>, String> {
    let Some((&first, rest)) = care_rows.split_first() else {
        return Ok(None);
    };
    let label = table.rows[first].1[output];
    if rest.iter().all(|&row| table.rows[row].1[output] == label) {
        return Ok(Some(SharedRobdd::care_constant(label)));
    }
    let Some(&var) = order.get(depth) else {
        return Err("variable order exhausted with conflicting care labels".into());
    };

    let mut low_rows = Vec::with_capacity(care_rows.len());
    let mut high_rows = Vec::with_capacity(care_rows.len());
    for &row in care_rows {
        if table.rows[row].0[var] {
            high_rows.push(row);
        } else {
            low_rows.push(row);
        }
    }
    let low = build_output(forest, table, &low_rows, output, order, depth + 1, policy)?;
    let high = build_output(forest, table, &high_rows, output, order, depth + 1, policy)?;

    let (low, high) = match (low, high, policy) {
        (Some(low), Some(high), _) => (low, high),
        (Some(sibling), None, EmptyCarePolicy::ReuseSibling)
        | (None, Some(sibling), EmptyCarePolicy::ReuseSibling) => return Ok(Some(sibling)),
        (Some(low), None, EmptyCarePolicy::Zero) => (low, SharedRobdd::care_constant(false)),
        (None, Some(high), EmptyCarePolicy::Zero) => (SharedRobdd::care_constant(false), high),
        (None, None, _) => return Ok(None),
    };
    Ok(Some(forest.mk_care_node(var, low, high)?))
}

fn validate_partial_table(table: &PartialTable) -> Result<(), String> {
    if table.noutputs == 0 {
        return Err("partial table must contain at least one output".into());
    }
    if table.rows.is_empty() {
        return Err("partial table must contain at least one row".into());
    }
    let mut seen: HashMap<&[bool], &[bool]> = HashMap::with_capacity(table.rows.len());
    for (input, output) in &table.rows {
        if input.len() != table.ninputs {
            return Err("partial table input width does not match ninputs".into());
        }
        if output.len() != table.noutputs {
            return Err("partial table output width does not match noutputs".into());
        }
        if let Some(previous) = seen.insert(input, output)
            && previous != output
        {
            return Err("duplicate input has conflicting output".into());
        }
    }
    Ok(())
}

fn validate_order(ninputs: usize, order: &[usize]) -> Result<(), String> {
    if order.len() != ninputs {
        return Err(format!(
            "variable order length {} does not match {ninputs} inputs",
            order.len()
        ));
    }
    let mut seen = vec![false; ninputs];
    for &var in order {
        if var >= ninputs {
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
        u32::try_from(ninputs).map_err(|_| "partial table dimensions overflow".to_string())?;
    1usize
        .checked_shl(shift)
        .ok_or_else(|| "partial table dimensions overflow".to_string())
}

fn validate_cross_validation_shape(table: &PartialTable, folds: usize) -> Result<(), String> {
    if folds < 2 {
        return Err("cross-validation requires at least two folds".into());
    }
    if table.rows.len() < 2 {
        return Err("cross-validation requires at least two visible rows".into());
    }
    Ok(())
}

fn checked_add(left: usize, right: usize, label: &str) -> Result<usize, String> {
    left.checked_add(right)
        .ok_or_else(|| format!("{label} overflow"))
}

fn compare_ratio(
    left_numerator: usize,
    left_denominator: usize,
    right_numerator: usize,
    right_denominator: usize,
) -> Ordering {
    ((left_numerator as u128) * (right_denominator as u128))
        .cmp(&((right_numerator as u128) * (left_denominator as u128)))
}
