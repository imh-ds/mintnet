# Task 06 — Results, views, exports, and methods text

Roadmap: §7, methodology §7, M3. Files: `src/mintnet/cin/views.py`, `src/mintnet/cin/result.py` (I/O parts), `tests/unit/cin/test_views.py`.

## 1. Purpose

Everything the researcher touches after fitting: pure filtering into named views, a deterministic basic plot, matrix/table/edge-list/JSON exports, and an auto-generated methods paragraph. **No function in this task calls the estimator** (invariant I7); changing view arguments never changes fitted weights.

## 2. Persisted fit format

`NetworkFit.save(dir)` / `load_fit(dir)`:

```text
pairs.csv        # one row per unordered pair, schema in §3
nodes.csv        # node diagnostics (task 05 §6)
folds.csv        # per-fold diagnostics and cost counters
matrix_weight.csv, matrix_display.csv   # p×p symmetric matrices (NaN for incomplete)
metadata.json    # provenance (config, schema, digests, versions, seeds, code rev, fit_id, status)
```

Full pair tables are always preserved, even when a filtered edge list is exported. CSV floats written with `repr`-precision (`float_format=None`/17 significant digits) so reload is exact. Reload validates that `pairs.csv` has `p(p−1)/2` unique rows and the metadata `fit_id` recomputes. Raw data is never written.

## 3. Pair table schema (roadmap §7, in this column order)

```text
node_i, node_j, gain_i_to_j, gain_j_to_i, weight_nats_raw,
display_magnitude_nats, gaussian_equivalent_magnitude,
orientation_gap, n_scored, folds_complete, status, diagnostic_flags
```

- `node_i` precedes `node_j` in schema order. No sign field.
- `gaussian_equivalent_magnitude = sqrt(-expm1(-2*display_magnitude_nats))`; unavailable for incomplete pairs (NaN, status explains). Docstring: an unsigned analogy to `|partial r|` under Gaussianity, never a signed partial correlation, never multiplied by an unknown sign.

## 4. `make_view` (pure function; roadmap §7 ordering)

```python
make_view(fit, *, min_effect=0.0, require_both_positive=False,
          stability=None, min_stability=None,
          max_edges=None, top_fraction=None, name=None) -> NetworkView
```

Filters applied in this order:

1. `status == "complete"`, `weight_nats_raw > 0`, and `weight_nats_raw >= min_effect` (`min_effect >= 0`).
2. If `require_both_positive`: both directional gains `> 0`.
3. If `min_stability is not None`: requires a `stability` object whose `fit_id` equals the fit's; use the stability computed for the **exact** (`min_effect`, `require_both_positive`) rule (task 07 recomputes from saved directional records); pairs with unavailable stability **never pass**.
4. Presentation limit (labelled as such): `max_edges` or `top_fraction`, mutually exclusive (`ValueError` otherwise). `top_fraction` in `(0,1]` ⇒ `ceil(fraction × n_passing)`. Rank by `weight_nats_raw` descending; ties broken by `(node_i, node_j)` names ascending under canonical orientation. The view records `presentation_limit=True` and how many edges were cut.

Named-view labels from methodology §7 are produced automatically in `view.label` from the arguments used: "Landscape" (all defaults), "Effect-filtered", "Agreement-filtered", "Stable subset", plus "+ Presentation limit". Wording in `view.description` states literal meanings only (no significance/confidence language; `0.01` is only ever described as an illustrative relevance threshold).

`NetworkView` holds `edges` (DataFrame subset), `settings` (all arguments), `fit_id`, `stability_meta` (B, fraction, completion counts, or `None`), and methods `to_edge_list()`, `to_matrix()`, `plot(...)`, `save(dir)`, `methods_text()`.

Validation errors (`ValueError`): negative `min_effect`, `min_stability` outside `[0,1]`, stability from another fit, both limit arguments, `top_fraction` out of range, `min_stability` without `stability`.

## 5. Exports

- `edge_list.csv`: `node_i,node_j,weight` columns (weight = display magnitude nats) plus optionally `stability`; header documented so it loads into networkx/igraph/R without our package.
- `to_matrix()`: symmetric numpy/pandas p×p of display magnitude with zeros for non-displayed but complete pairs **and NaN for incomplete pairs** (never conflate). Provide a `fill` argument only for plotting, defaulting to NaN.
- `view.save(dir)`: `edges.csv`, `edge_list.csv`, `matrix.csv`, `view.json` (settings, fit_id, thresholds, agreement flag, repeat metadata, presentation limits), `methods.txt`, optional `network.png`, `matrix.png`.

## 6. Plots (matplotlib only; no networkx, no layout library)

- **Network drawing**: deterministic circular layout in schema order (or a caller-supplied order); edge line width `0.5 + 6·magnitude/max_magnitude_in_fit` (scale from the *fit*, so widths are comparable across thresholds — **[added]**); optional opacity mapped from stability when available (`alpha = 0.25 + 0.75·stability`); node labels rotated for readability; no arrowheads, no red/blue, no centrality sizing.
- **Matrix heatmap**: p×p display magnitude, incomplete pairs hatched or grey, colorbar in nats. For p near 100 this is the primary display.
- **Sortable edge table** = the pair table/DataFrame itself; the user guide shows `sort_values`.
- Figures return `matplotlib.figure.Figure`; nothing calls `plt.show()`; use `Agg` in tests.

## 7. Methods text (`methods_text()`)

Template filled from metadata, no free-form claims. Must state: the model actually used (all-other-variable conditional predictive information, linear+≤2 curvature terms for continuous, LSPC-type probability model for categorical), conditioning set (all other included variables), outcome (nats per observation, undirected average of two prediction orientations), `K`/`J`/grid and per-node tuned penalties summary, missing-data policy and retained/excluded N, standardization/basis training-only, exact omission at fixed λ, view filters applied (thresholds, agreement, stability meaning as reproducibility under B subsamples of fraction f, presentation limit), and limitations (model-based not true CMI; cannot capture variance-only or XOR dependence; Gaussian response approximation; independent rows; no causal or confidence interpretation; unvalidated δ). Also emits any warnings triggered by diagnostics (low N, p ≥ N, rare levels, floor hits, incomplete pairs).

## 8. Tests (`test_views.py`)

1. Filter order: construct a synthetic pair table with mixed statuses/gains/weights/stability; expected edge sets for each rule combination match a hand calculation, including `weight == min_effect` inclusion and `weight == 0` exclusion.
2. **Views don't refit**: monkeypatch `fit_network` and the estimator to raise; `make_view` with many argument combinations never calls them; the fit's pair table is unchanged (frame equality) after viewing.
3. Nonexistent sign cannot erase magnitude: a large-`weight`, symmetric-but-U-shaped example (no sign column) stays in the Landscape and effect-filtered views.
4. Presentation limits: deterministic tie-breaking with equal weights; count and fraction mutually exclusive; `top_fraction` rounding; the underlying fit is unchanged; view records that it was a limit.
5. Unavailable stability never passes; stability from another `fit_id` rejected; changing the effect threshold changes the required stability column (task 07 integration).
6. Incomplete pairs: not displayed, matrix shows NaN, edge list omits them, methods text lists the count of incomplete pairs.
7. Save/load round trip: exact float equality on all columns; metadata `fit_id` recomputes; corrupted `pairs.csv` (missing rows) is rejected.
8. Plot smoke: figures build for p=2, p=8, p=100 without error, deterministic pixel-independent structure test (number of line collections equals number of edges).
9. Methods text contains required phrases (`nats`, `not a significance`, retained N) and no forbidden phrases (`significant`, `confidence interval`, `causal`, `p-value`) except in negated/limitation sentences — check with an explicit whitelist of sentences.
10. Edge list re-imported by pandas has exactly the documented header.

## 9. Acceptance

`python -m pytest tests/unit/cin/test_views.py` green; the example workflow in task 12 (fit → view → save → reload) runs on the continuous and mixed examples.

## 10. Pitfalls

- Never mutate `fit.pairs` in place; `make_view` returns copies.
- CSV round trips of empty-string vs NaN for unavailable fields must be tested.
- Keep matplotlib import inside plotting functions.
