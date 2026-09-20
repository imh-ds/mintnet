# Task 07 — Optional repeated-refit stability

Roadmap: §8, M3. Files: `src/mintnet/cin/stability.py`, `tests/unit/cin/test_stability.py`.

## 1. Purpose

Provide an explicit, budgeted repeat-subsampling capability (`estimate_stability`) whose stored per-repeat directional gains let any later effect/agreement filter recompute stability **without refitting**. It is never invoked by `fit_network` (invariant I8). Its output is *reproducibility under a stated subsampling procedure*, never an edge-existence probability, p-value, confidence interval, or FDR.

## 2. API

```python
estimate_stability(fit, frame, *, repeats=10, fraction=0.8, max_seconds=600.0,
                   resume=None) -> StabilityResult
stability_for_rule(result, *, min_effect, require_both_positive) -> pd.DataFrame
# columns: node_i, node_j, passes, n_complete, n_requested, stability (NaN if unavailable)
```

`make_view(..., stability=result, min_stability=s)` (task 06) calls `stability_for_rule` with the view's own effect/agreement settings.

## 3. Procedure

1. **Identity check before any work**: recompute `prepare_data(frame, fit.schema, fit.config)` digests; require equality with `fit.metadata.data_digest` and `row_identity_digest`; otherwise raise `ValueError` (data changed since the fit). The same config (hash) is reused for every repeat; changing settings requires a new fit.
2. **Preflight**:
   - `floor(fraction × retained_N) >= 30` (the fitting minimum is **not** lowered; the fraction is **not** silently changed). Otherwise return a `StabilityResult` with status `unsupported_repeat_request` and no repeats; the point fit stays valid.
   - Estimated cost `1.5 × repeats × fit.metadata.point_fit_elapsed_seconds`. If it exceeds `max_seconds`: status `budget_not_started` with the estimate returned; never silently reduce `repeats`.
3. **Sampling**: child seeds from `np.random.SeedSequence(entropy=fit_seed, spawn_key=(STABILITY_TAG, r))` for repeat `r ∈ [0, B)`. Each repeat draws `floor(fraction·N)` rows **without replacement** (`Generator.choice(N, size, replace=False)`, then sorted for deterministic ordering). Group/cluster sampling is out of scope.
4. **Refit**: for each repeat call the same internal fit function used by `fit_network` on the subsampled `PreparedData` (preprocessing, tuning, scoring all independent per repeat; the inner split seed for the repeat derives from the repeat seed, not the original fit's splits). Pass a `deadline` derived from the overall repeat budget so deadline checks fire **inside** a repeat's fit as well as between repeats.
5. **Store per repeat and per pair**: `fit_id, repeat_id, repeat_seed, node_i, node_j, gain_i_to_j, gain_j_to_i, weight_nats_raw, status`. p=100 ⇒ 4,950 pairs × 10 repeats ≈ 49.5k rows; write as `stability_records.csv` (plus `.csv.gz` in evidence runs).
6. **Interrupted work**: completed repeat records are exported; the `StabilityResult` states `repeats_completed` and its overall status (`complete`, `interrupted`, `budget_not_started`, `unsupported_repeat_request`). The point fit remains usable.
7. **Resume**: `resume=` accepts a previous result/dir; validate `fit_id`, config hash, data digests, `fraction`, requested `B`, seeds, and existing `(repeat_id)` keys before appending; already completed repeats are skipped; duplicate keys are errors.

## 4. Stability computation

For a rule `(δ, agree)`:

- A repeat **passes** a pair iff `status == complete`, `weight > 0`, `weight >= δ`, and if `agree` both directional gains `> 0`.
- `stability = passes / B_requested`, reported **only if the pair has `B_requested` complete repeat estimates**; otherwise `NaN` with `n_complete` shown. Failed or missing repeats are **not** counted as "not passing" and the denominator never silently changes.
- Resolution note in docs: with B=10, values are multiples of 0.1.
- Missing stability never passes a stable-subset filter (task 06).

## 5. Deterministic details

- The sorted-subsample choice makes row order in each repeat canonical; identical seeds give identical records across shards.
- `STABILITY_TAG` constant documented in the module and in the charter (like `_STAGE_TAG` in `stage5a`).
- Wall-clock preflight uses the recorded point-fit elapsed time (`metadata`); a fit loaded from disk without it must pass an explicit `elapsed_estimate` or preflight fails loudly.

## 6. Tests (`test_stability.py`)

Small problems with a fast fit (p ≤ 5, N ≈ 80; repeats B=4):

1. **Recomputation without refit**: after producing records, change `δ` and `agree` in `stability_for_rule`; monkeypatched `fit_network` raises if called; results match a hand calculation from the stored gains.
2. **Failed repeats aren't stability**: inject a failing repeat for one pair; that pair's stability is NaN with `n_complete = B−1`, other pairs unaffected; the view's `min_stability` excludes the unavailable pair.
3. **Sampling**: subsamples contain no duplicate rows; each has the requested size; seeds and resume keys are deterministic (two invocations equal); different fit seeds differ.
4. **Preflight**: `floor(0.8·N) < 30` ⇒ `unsupported_repeat_request` and no fitting; a tiny budget ⇒ `budget_not_started` with an estimate and B unchanged; the input fit is unchanged.
5. **Interruption**: deadline hit mid-repeat ⇒ completed repeats exported, incomplete flagged, result status `interrupted`, no partial-repeat pair rows treated as complete.
6. **Identity guard**: modified frame or reordered index ⇒ `ValueError` before fitting.
7. **Resume**: interrupted run resumed to completion equals an uninterrupted run (records identical except timing); mismatched config/seed rejected; duplicate repeat ids rejected.
8. **Rule change**: stricter δ can only lower `passes` (monotonicity property test on random gains).
9. **Ordinary fit never resamples**: `fit_network` source path contains no call to stability code (import-graph test or mock).
10. **View integration**: `make_view(min_stability=0.8)` uses the exact rule of the same view; requesting agreement changes the underlying counts accordingly.

## 7. Acceptance

`python -m pytest tests/unit/cin/test_stability.py` green. The example script in the user guide (task 12) runs stability on the continuous example with B=10 under the stated budget and shows an unavailable-stability case.

## 8. Pitfalls

- The repeats reuse the same config; do not let `max_seconds` of the point fit shorten repeats — pass the repeat-level deadline explicitly.
- `estimate_stability` must not mutate `fit`. Any attribute added to the fit (like `stability`) belongs on the returned result.
- Evidence runs (task 11) use stability on only three prespecified validation datasets (A, B, F); do not multiply the panel by resampling.
