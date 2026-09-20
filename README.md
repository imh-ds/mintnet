# MINT

**MINT — Model-based Information Network Toolkit**

MINT is a Python research toolkit for exploratory information networks. Its
new algorithmic engine is being developed as **CIN — Conditional
Predictive-Information Network** under the `mintnet.cin` namespace.

## Current status

The CIN methodology and build plan are specified, but the engine has not yet
been implemented or statistically validated. The active design documents are:

- [CIN methodology](docs/design/cin/methodology/methodology_outline_2026-09-19.md)
- [Technical implementation roadmap](docs/design/cin/methodology/technical_implementation_roadmap_2026-09-19.md)
- [Task-level build plan](docs/design/cin/build-plan/00_README_build_plan_index.md)

CIN measures the held-out logarithmic-score improvement contributed by one
variable after conditioning on all other included variables. The resulting
weights are model-based conditional predictive-information quantities measured
in nats per observation. With correct conditional models, their population
target equals conditional mutual information; finite fitted values are not
presented as universally model-free CMI estimates.

## Repository layout

```text
src/mintnet/cin/                  forthcoming CIN numerical core
src/mintnet/experiments/cin_*    forthcoming evidence runners
src/mintnet/simulation/          reusable fixtures and forthcoming CIN generators
docs/design/cin/                 controlling methodology and build plan
archive/                         retired implementations and their research record
```

The previous screening, conditioning-search, DPI, confidence-curve, and
bootstrap-rescue implementation is preserved under
[`archive/mi_native_search/`](archive/mi_native_search/README.md). It is not on
the active import or test path.

## Project boundaries

MINT/CIN is intended as an exploratory, undirected information-network tool.
Its outputs are not causal directions, significance tests, confidence
intervals, or guarantees of detecting every possible form of dependence.

Python support remains pinned to Python 3.11 while the CIN baseline is built.
