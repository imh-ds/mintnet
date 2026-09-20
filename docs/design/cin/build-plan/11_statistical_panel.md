# Task 11 — Bounded statistical panel

Roadmap: §11, M4. Files: `src/mintnet/experiments/cin_baseline.py`, `cin_baseline_reporting.py`, `configs/cin_baseline.yaml`, `configs/cin_baseline_smoke.yaml`, `docs/cin_baseline_charter.md`, gate script `scripts/cin_gate_check.py` **[added]**. Depends on 06, 07, 08, 09, 10 (cost pilot passed or scoped).

## 1. Purpose

Produce one bounded, frozen evidence set answering: does the exploratory conditional predictive-information network recover useful whole-network structure in moderate-N cases, add nonlinear value over a matched linear scorer, behave on exactly known categorical/mixed truth, and behave sensibly at low-N null — without turning this into a large Cartesian benchmark or tuning against validation seeds.

## 2. Scale

9 cases × (10 development + 20 validation) = **270 core datasets**, before comparator runs on the same draws, plus one historical-fixture regression smoke, plus optional stability on **three** validation datasets (one each from A, B, F; replicate index fixed in the charter, e.g. the first validation replicate), plus non-gated demonstrations (variance-only, XOR). Cap: **12 aggregate runner-hours** across pilot + development + validation + comparators + repeats (ledger, task 09 §7).

## 3. Cases, generators, truth

Exactly as task 08 §4 (A–I). Each dataset has `truth_edges` (all cases except I, which has none) and optional `population_cmi` (Gaussian and exact categorical cases; A, B, D, F, G, H available).

## 4. Methods per dataset (paired on the identical draw)

| Method | Cases | Definition |
|---|---|---|
| `cin` | all | Task 05 `fit_network`, default config |
| `cin_linear` | A–E | Same code path, `max_curvature_rank=0` (matched linear scorer) |
| `ebicglasso` | A–E | Repository `fit_ebicglasso` on identical continuous data. **Before use, audit its failure/convergence reporting** (roadmap M4): a fit that fails or does not converge must be a failure row, not an empty graph; do not describe it as reference-verified against qgraph unless an actual reference comparison exists. Do not apply to categorical integer codes (F, G, H, I). |

Bayesian-network comparison optional, off by default.

## 5. Metrics (per dataset; stored in `raw_metrics.csv`, pair tables in sidecars)

Definitions:

- **Score for ranking**: `weight_nats_raw` for CIN methods (negatives rank below positives); `|partial correlation|` from the EBICglasso precision matrix for that comparator. Complete-pair requirement: a dataset with any incomplete pair is a failure row for AP purposes (reported, not dropped).
- **Average precision (AP)** over all `p(p−1)/2` pairs against truth edges (`sklearn.metrics.average_precision_score`, ties handled by sklearn's threshold semantics; record the tie fraction for EBICglasso where many scores are exactly 0), plus **prevalence** = fraction of true edges (the random-ranking AP baseline). `AP − prevalence` is the gate quantity.
- **Displayed-graph precision/recall/count/empty flag** at each `δ ∈ {0, 0.005, 0.01, 0.02}` nats using view rule Effect-filtered (`w ≥ δ`, `w>0`); also report the Agreement-filtered variant separately. For EBICglasso: nonzero partial correlations (no δ; report as single row). Precision on an empty view is **unavailable**, never 1; store `NaN` plus `empty_view=True`. Aggregations report the number of nonempty views.
- **Strong-edge recall**: recall over truth edges with population CMI ≥ 0.01 (only where `population_cmi` is available: A, B, D, F, G, H). All-edge precision counts weak true edges as true positives.
- **Oracle CMI error**: for cases with `population_cmi`: mean absolute error and mean signed error over true edges (and over all pairs) of `weight_nats_raw` vs population CMI, with the caveat that the estimator's target is model-based (report as descriptive).
- **Categorical node loss** (F, G, and optionally H): per node `full_score − intercept_score` mean held-out gain; excess loss = `−(full − intercept)` averaged over nodes.
- **Null case I**: quantiles (50/90/95/99/max) of positive complete weights and displayed fraction of pairs at each δ; AP not computed.
- **Cost/diagnostic columns**: completion counts, failures by type, elapsed seconds, peak RSS, directional-disagreement summary (`orientation_gap` quantiles), floor/probability diagnostics.
- Report **counts behind every mean** (number of replicates contributing, number failed, number empty). Include Monte Carlo standard errors of means; do not present 20 validation replicates as precise tail-error estimation or FDR control.

## 6. Development, correction, validation protocol

1. **Freeze** (before any panel dispatch): charter, case definitions (task 08 parameters + population-property report), metrics, defaults, gates, δ-selection rule below, comparator audit outcome, seed ranges (development `[0,10)`, validation `[1000,1020)`), method availability matrix, exact sharding, runtime budget/ledger plan.
2. **Development run**: 9×10 datasets. Sharded via Actions.
3. **δ selection (using development data only)** **[added — roadmap leaves the rule open]**: among `δ ∈ {0.005,0.01,0.02}`, keep those with development mean all-edge precision ≥ 0.70 over nonempty views **and** nonempty-view fraction ≥ 0.80 in both A and B; among them choose the one with the largest mean strong-edge recall (average over A and B); ties → smaller δ. If none qualifies, choose the δ with the largest development mean of `min(precision_A, precision_B)` and mark the eventual gate outcome as "expected fail on development"; do not continue tuning.
4. **At most one global methodological correction** after development (e.g., a fixed default that is wrong for every case). It must be documented as a version change (`decision_log`), applied to the code and charter, and cannot be case-specific or δ-driven. Rerun development if the code changed; then freeze again.
5. **Validation run**: 9×20 **new** datasets; no reuse of smoke/development seeds; run once. Acceptance reads only these results.
6. **Report** (task 12 aggregates the docs): distributions, runtime, failures, scope outcomes, no unsupported confidence claims.
7. **Stop rule**: no repeated tuning against validation seeds; a gate failure means the related scope is reported unsupported/unfinished. No third large campaign is part of the baseline.

## 7. Prespecified release gates (validation data; roadmap §11.3, with the interpretations flagged in the README)

1. **Completion**: all ordinary validation datasets complete within the point-fit budget with valid probabilities/scores; report all failures (no dropping difficult draws).
2. **A and B**: mean `AP − prevalence ≥ 0.20`. At the development-selected δ: in each of A and B, mean all-edge precision ≥ 0.70 over nonempty views, mean strong-edge recall ≥ 0.50 over **all** replicates (empty views count as recall 0), nonempty views in ≥ 80% of replicates. The declared strong-edge set must exist in every replicate (population check, task 08).
3. **E**: mean AP(`cin`) − mean AP(`cin_linear`) ≥ 0.10.
4. **F, G, H**: mean `AP − prevalence ≥ 0.15`; for F and G, mean categorical full-model excess loss vs intercept ≤ 0.10 nats per node.
5. **C** must pass runtime/completion; its recovery quality determines the low-N/p=100 claim (reported, gated only on completion). **D and I** are mandatory descriptive boundaries: reported regardless of outcome, not omitted if disappointing.

Interpretation of outcomes (from the roadmap): failure of basic Gaussian utility (gate 2) or nonlinear gain (gate 3) means the method has not earned release as the intended solution; a continuous preview may pass while item support fails; a failed scope is reported unsupported, not repaired.

## 8. Compute ceiling and reduced-evidence rule

Estimate panel cost from the pilot before dispatch: `Σ_cases datasets × (fit_time_cin + fit_time_linear + fit_time_ebic)` plus stability (3 datasets × B=10 × fit time) plus regression smoke. If the estimate exceeds the remaining ledger budget of 12 runner-hours, lower replicate counts **openly** (e.g. validation 20 → fewer) *before* freezing, and label the report "reduced feasibility evidence"; never silently drop hard cases (C, D, I). Record actual counts in the report.

## 9. Runner behavior (see task 09)

Shard axes `--cases` × `--replicate-batches`; comparators run inside the shard; raw rows flushed per method; pair sidecars for every dataset (audit) and stability sidecars for the three stability datasets; the stability runs use B=10, fraction 0.8, `max_seconds` from the charter and report unavailable-stability fractions honestly.

## 10. Gate script (`scripts/cin_gate_check.py`) **[added]**

Reads the aggregated `raw_metrics.csv` of the **validation** phase (and the development-selected δ from the frozen charter/config, not recomputed), evaluates every gate, prints a table (gate, threshold, observed, n contributing, pass/fail/unavailable), and writes `gate_results.json`. It refuses to run if the raw file contains any development replicate index inside the validation phase, if counts don't match `expected_row_count`, or if the charter hash differs.

## 11. Non-gated deliverables inside the report

- Historical `organic_network` regression (rank quality on the 14+4 fixture at N=300; descriptive).
- Variance-only and XOR demonstrations (expected failures stated).
- Stability descriptive table for A, B, F stability datasets (precision/recall among edges with stability ≥ threshold at B=10; resolution 0.1; explicit unavailable counts).
- Directional disagreement descriptive distributions by case.
- High-p categorical recovery listed as an **unevidenced gap** (only the cost pilot covers wide categorical inputs).

## 12. Local testing before dispatch

`tests/integration/test_cin_runners.py` with `configs/cin_baseline_smoke.yaml` (p ≤ 8, N ≤ 60, 2 replicates, 2 cases): verifies expected combinations, edge counts (truth edge counts equal what generators promised), deterministic seeds, sharded == unsharded, duplicates, incremental rows, sidecars, gate script on a fabricated raw file (each gate can pass or fail as constructed), and comparator failure rows. Command: `python -m pytest tests/integration/test_cin_runners.py`. Material evidence is **not** a local run.

## 13. Acceptance

Frozen charter with hash; development complete and correction (if any) documented; validation run complete with counts matching the plan; gate table produced; ledger ≤ 12 runner-hours; per-scope verdicts (continuous preview, categorical branch, p=100 runtime, low-N claim) recorded individually.

## 14. Pitfalls

- Never choose δ, or edit any parameter, after looking at validation outcomes.
- Population-based strong-edge sets for B/D differ only if the transform changes CMI; it must not (invariance); assert equality.
- Comparator failure is a failure row; empty EBICglasso graphs are legitimate only when the fit succeeded.
- Case D's gate role is descriptive: it shows the finite-sample transform-sensitivity of a Gaussian-response method and must be reported even if AP drops.
