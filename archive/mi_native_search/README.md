# Archive: MI-native search pipeline (pre-CIN pivot)

This snapshot preserves the active implementation that followed the original
partial-correlation work and culminated in the Stage 10a dense-network scaling
failure recorded as D-091 in `docs/decision_log.md`.

The archived method combined marginal screening, conditioning-subset search,
DPI-style pruning, fitted confidence curves, and bootstrap-rescue mechanisms.
Those components remain useful as a transparent research record, but they are
not part of MINT's new Conditional Predictive-Information Network (CIN)
methodology. In particular, CIN's build contract prohibits conditioning-subset
enumeration, marginal/Pearson screening, neighbor caps, and reuse of the
historical confidence curves.

This directory mirrors the former active repository layout:

- `.github/workflows/` — dedicated Stage 9d and Stage 10a workflows;
- `configs/` — frozen experiment configurations;
- `docs/` — stage charters, reports, operating-range guidance, and old plans;
- `scripts/` — stage-specific diagnostics and shard helpers;
- `src/mintnet/` — the retired estimator, pipeline, and experiment modules;
- `tests/` — the corresponding historical tests.

Files intentionally retained in the active tree include the generic sharded
benchmark workflow and aggregators, the EBICglasso comparator, the Gaussian and
motif simulation helpers (including `sample_organic_network`), and their focused
tests. New CIN implementation belongs under `src/mintnet/cin/`,
`src/mintnet/experiments/cin_*`, and `src/mintnet/simulation/cin_networks.py`.

Nothing in this snapshot should be imported by the active package. To reproduce
historical work, use the Git revision cited by the corresponding charter rather
than adding `archive/` to Python's import path.
