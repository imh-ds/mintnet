# CIN researcher guide

This guide describes the implemented CIN fit API and the evidence boundary recorded in [decision D-106](decision_log.md#d-106-execute-cin-task-11-hosted-development-and-validation-evidence). CIN is an exploratory, undirected weighted map of conditional predictive information under a fitted model. Weights are measured in nats per observation. They are not causal directions, significance tests, p-values, confidence intervals, or universally model-free estimates of conditional mutual information. Rows are treated as independent participants; repeated measures and clustered or time-series data are not modeled.

## Install and environment

The package supports Python 3.11 (`>=3.11,<3.12`). From the repository root, install the project and its test extra with `python -m pip install -e ".[test]"`. Numerical dependencies are declared in `pyproject.toml`; CIN does not require R or NetworkX. Matplotlib is only imported when plotting is requested.

## Continuous quick start and worked example

The following self-contained example creates a small synthetic continuous dataset with a U-shaped relationship between `exposure` and `response`, fits the default CIN model, makes landscape/effect/agreement views, exports the fit and a view, and compares against a linear-only fit. Synthetic output is an API demonstration, not evidence that the method recovers U-shaped effects in general.

```python
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.cin import CINConfig, fit_network, make_view

rng = np.random.default_rng(20260927)
n = 120
exposure = rng.uniform(-2.0, 2.0, n)
frame = pd.DataFrame({
    "exposure": exposure,
    "response": exposure**2 + rng.normal(0, 0.45, n),
    "age_score": rng.normal(size=n),
    "mood_score": rng.normal(size=n),
    "sleep_score": rng.normal(size=n),
})
schema = {name: {"kind": "continuous"} for name in frame.columns}

fit = fit_network(frame, schema, CINConfig(seed=41))
landscape = make_view(fit)
effect_view = make_view(fit, min_effect=0.01)
agreement_view = make_view(fit, min_effect=0.01, require_both_positive=True)

fit.save(Path("cin-continuous-fit"))
effect_view.save(Path("cin-continuous-effect-view"), plots=False)
print(f"fit status: {fit.metadata['runtime']['status']}")
print(f"complete pairs: {(fit.pairs['status'] == 'complete').sum()} / {len(fit.pairs)}")
print(f"effect-filtered edges: {len(effect_view.edges)}")
print(agreement_view.methods_text())

linear_fit = fit_network(
    frame,
    schema,
    CINConfig(seed=41, max_curvature_rank=0),
)
pair = fit.pairs.loc[
    fit.pairs["node_i"].eq("exposure") & fit.pairs["node_j"].eq("response"),
    ["weight_nats_raw", "status"],
]
linear_pair = linear_fit.pairs.loc[
    linear_fit.pairs["node_i"].eq("exposure") & linear_fit.pairs["node_j"].eq("response"),
    ["weight_nats_raw", "status"],
]
print("curved fit:", pair.to_dict(orient="records"))
print("linear-only fit:", linear_pair.to_dict(orient="records"))
```

The example intentionally does not assert that the curved fit must assign a particular weight: the fitted, cross-validated result depends on finite data and regularization. Compare the two records as an illustration of the `max_curvature_rank=0` sensitivity check, not as a validated nonlinear-performance claim.

## Mixed and categorical worked example

Categorical variables require an explicit list of observed levels. `ordered=True` records metadata only; the current model does not impose an ordinal model. The categorical branch remains experimental because the hosted panel recorded F generation/completion failures even though its named recovery gate passed. High-p categorical recovery was not evaluated.

```python
import numpy as np
import pandas as pd

from mintnet.cin import CINConfig, fit_network, make_view

rng = np.random.default_rng(20260928)
n = 150
symptom = rng.integers(1, 6, n)
frame = pd.DataFrame({
    "symptom_item": symptom,
    "care_group": np.where(symptom >= 4, "enhanced", "usual"),
    "binary_flag": rng.choice([0, 1], size=n),
    "age_score": rng.normal(size=n),
})
schema = {
    "symptom_item": {"kind": "categorical", "levels": [1, 2, 3, 4, 5], "ordered": True},
    "care_group": {"kind": "categorical", "levels": ["usual", "enhanced"]},
    "binary_flag": {"kind": "categorical", "levels": [0, 1]},
    "age_score": {"kind": "continuous"},
}

fit = fit_network(frame, schema, CINConfig(seed=52))
view = make_view(fit, min_effect=0.01, require_both_positive=True)
fit.save("cin-mixed-fit")
view.save("cin-mixed-agreement-view", plots=False)
print(f"retained N: {fit.metadata['retained_count']}")
print(f"diagnostics: {fit.metadata['data_diagnostics']}")
print(f"pair status summary: {fit.pairs['status'].value_counts().to_dict()}")
```

Inspect node diagnostics and pair statuses along with any view. Do not describe this example as logistic regression, a validated ordinal model, or proof of categorical support.

## Declaring data and reading statuses

The schema is authoritative: only named columns are fitted. Declare each variable as `continuous` or `categorical`; for categorical variables, specify 2–10 unique, nonmissing levels. Continuous values must be numeric and finite. Boolean columns must be categorical. Constant columns are rejected. Extra columns outside the schema are ignored. Category order is retained as metadata but is not used to fit an ordinal model.

Missingness defaults to `CINConfig(missing="error")`, which rejects any missing value in the declared columns. `missing="complete_case"` drops rows missing any declared value and records input, retained, and excluded counts. It does not impute values. Check rare-level, few-unique, low-retained-N, p≥N, variance-floor and incomplete-pair diagnostics before interpreting weights.

Fits and individual pairs carry status information. A fit may be incomplete while retaining usable complete pairs; failed pair estimates remain visible as `status=error` rather than being silently replaced by an empty edge. Exceptions from schema validation, invalid inputs, or budgets are not successful fits. Persisted fit metadata records configuration, schema, data digests, diagnostics and runtime; `fit.save(path)` writes `pairs.csv`, `nodes.csv`, `folds.csv`, two matrices and `metadata.json`, but never raw observations. `load_fit(path)` validates and reloads the saved result.

The defaults are initial engineering settings, not empirically optimized universal settings: outer cross-fit K=3, inner tuning folds J=2, lambda grid `[0.001, 0.01, 0.1, 1, 10]`, continuous curvature rank up to 2, and a per-fit time budget. See `CINConfig` for the complete options. There is no general runtime promise; use measured runner evidence only for the tested hardware and scope. The Task 10 cost pilot passed its stated p≤100 runtime checks, which does not guarantee runtime for every dataset or environment.

## Pair table and views

The full pair table is the primary result. It preserves raw signed `weight_nats_raw`, directional gains, fit status, orientation disagreement, and display magnitude. Negative estimates are retained in the raw table; displayed magnitude clips them at zero. The two prediction directions are averaged into an undirected weight. `gaussian_equivalent_magnitude` is an unsigned Gaussian analogy, not an effect direction.

`make_view` filters an already computed fit; changing view options does not refit the model or alter fitted weights.

- **Landscape:** complete pairs with positive raw weight.
- **Effect-filtered:** additionally requires raw weight at least `min_effect` nats.
- **Agreement-filtered:** additionally requires both directional gains to be positive.
- **Stable subset:** joins repeated-fit stability and retains pairs at or above `min_stability`.
- **Presentation limit:** `max_edges` or `top_fraction` limits display after filters; it is not a validation gate.

For example, the continuous quick start shows landscape, effect, and agreement views. A threshold such as 0.01 nats is a researcher-chosen relevance filter, not a significance threshold. Views are sorted deterministically. `view.edges`, `view.to_edge_list()`, and `view.to_matrix()` provide tabular forms; `view.save(path)` writes edge tables, matrix, settings and methods text. Plotting is optional. A displayed zero means the complete pair did not pass the view; an incomplete pair remains unavailable in the matrix when `fill=None`.

## Stability

Stability repeats fits on subsamples with fixed derived seeds. It measures reproducibility under the stated resampling rule, not the probability that an edge is true and not inferential uncertainty. No universal `B` or cutoff is prescribed. Budget preflight can return `budget_not_started`; interrupted work preserves completed repeats and marks missing repeat coverage unavailable. The point fit remains usable. Stability is optional and may be costly.

```python
from mintnet.cin import estimate_stability, make_view

stability = estimate_stability(fit, frame, repeats=2, fraction=0.8, max_seconds=30)
stable_view = make_view(fit, min_effect=0.01, stability=stability, min_stability=0.5)
stability.save("cin-stability", compressed=True)
stable_view.save("cin-stable-view", plots=False)
```

The short stability snippet can be run after either worked example, using that example's `fit` and `frame`. Two repeats illustrate the API only; choose B and `max_seconds` for the analysis budget (the panel plan used B=10). Read `stability.status`, requested/completed repeat counts, and the per-pair `n_complete` denominator; a missing repeat is not a zero pass.

## Dense and low-N use

For dense fits, inspect the full pair table and matrix and use a presentation limit only to make a display manageable. A display limit is not evidence of sparse recovery. At p near 100, inspect measured memory and runtime from a matching environment; Task 10's p=100 timings are bounded pilot results, not a universal rule. No universal N/p adequacy rule is established. Report retained N, p, rare-category counts, fit status, model diagnostics and the selected view settings.

## Reproducing the statistical panel

The repository runner commands and shard workflow inputs are maintained in [Task 09](design/cin/build-plan/09_runner_actions_infrastructure.md). A local smoke run checks code paths only; it is not timing or recovery evidence. For a frozen development and validation artifact, use the phase-specific aggregation and mandatory provenance gate commands in that runner guide, and retain raw rows, sidecars, resolved configuration, metadata and gate results together.

The hosted results in D-106 are frozen: 396/400 validation rows were complete, two incomplete, and two generation errors. The completion gate failed and the E nonlinear-gain gate failed (0.049111 against 0.10); A/B, selected-delta, F/G/H recovery and C runtime gates passed as recorded. D and I were descriptive. Do not retune or rerun validation to alter these outcomes. High-p categorical recovery is unevidenced. The historical organic-network regression is descriptive only. No broad recovery, causal, inferential, FDR or tail-probability claim follows from the panel.

## Limitations and methods text

The current estimator can miss variance-only and XOR dependence. Extreme skew, floor/ceiling behavior, small samples, missingness bias, repeated measures, and multilevel designs require separate scrutiny or methods. The Gaussian EBICglasso comparator is limited to its continuous regime and is not claimed to be externally reference-verified. Categorical support is experimental. The panel had only 20 validation replicates per case; it does not provide precise tail-error or FDR estimation. See the [methodology](design/cin/methodology/methodology_outline_2026-09-19.md) and [frozen baseline charter](cin_baseline_charter.md) for scope and assumptions.

`view.methods_text()` summarizes the actual fit settings, missingness handling, view filters and warnings. It can be included in a methods record, but it is not a substitute for citing the code revision, data scope, fit status, diagnostics and evidence boundary. Do not claim causal directions, significance, p-values, confidence intervals, universal CMI recovery, validated ordinal modeling, or an edge probability from stability.

## Status by scope

- **Continuous preview:** A/B recovery and selected-delta validation gates passed; E's nonlinear-gain gate failed. The intended broad continuous claim is withheld.
- **Categorical item branch:** experimental. The named F/G/H recovery gates passed, but F had generation/completion failures. High-p categorical recovery was not evaluated.
- **p=100 runtime:** the Task 10 cost pilot's measured runtime checks passed for its configured cells and environment; this is a bounded runtime result only.
- **Low-N claim:** unsupported as a recovery claim. Case C passed its completion/runtime gate only; Case I is a descriptive null boundary.
- **Stability:** the plan/charter differ on the number/scope of stability datasets. The hosted D-106 record does not state a final stability outcome; do not claim a panel-wide stability result from that record.
- **Not built:** ordinal-order models, sign-aware outputs, interactions, imputation, clustered/time-series fits, centrality, causal extensions, and the other deferred items listed in the roadmap.
