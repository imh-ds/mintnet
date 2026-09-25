# CIN Task 10 Cost Pilot Charter

Status: frozen before dispatch.

## Purpose and nonclaims

This charter defines the early end-to-end compute and completion gate for the
shared-ridge CIN implementation. This is a cost pilot; timings are single-dataset measurements on shared hosted runners. It does not claim statistical precision,
recovery performance, a general runtime law, causal validity, or substantive
network interpretation. Cost inputs carry no graph truth and receive no recovery
score.

## Frozen matrix and seeds

The full configuration is `configs/cin_cost.yaml`, with `master_seed: 20260924`,
repeats `1` and `2`, default CIN settings (`K=3`, `J=2`, five penalties), and
these exact cells:

| Cell | Kind | p | N |
|---|---|---:|---:|
| `c_p8_n100` | `dense_continuous` | 8 | 100 |
| `c_p30_n100` | `dense_continuous` | 30 | 100 |
| `c_p100_n100` | `dense_continuous` | 100 | 100 |
| `c_p100_n300` | `dense_continuous` | 100 | 300 |
| `c_p100_n1000` | `dense_continuous` | 100 | 1000 |
| `k5_p30_n150` | `categorical5` | 30 | 150 |
| `k10_p100_n200` | `categorical10` | 100 | 200 |
| `mix_p100_n200` | `mixed` | 100 | 200 |

Seeds derive from `SeedSequence([20260924, 9009, cell_index, 0, repeat])`.
The table records the `structure`, `sample`, and `cin_fit` children used by the
runner; cell indices are the table order above.

| Cell | Repeat | structure | sample | cin_fit |
|---|---:|---:|---:|---:|
| `c_p8_n100` | 1 | 1229596112 | 93902024 | 1033667905 |
| `c_p8_n100` | 2 | 1186252868 | 2690772135 | 3012641772 |
| `c_p30_n100` | 1 | 3530567784 | 2203185407 | 1181141077 |
| `c_p30_n100` | 2 | 645976065 | 2601747000 | 4277728612 |
| `c_p100_n100` | 1 | 2149240790 | 1482442489 | 369268147 |
| `c_p100_n100` | 2 | 2258089888 | 2972228489 | 1975509115 |
| `c_p100_n300` | 1 | 1654990446 | 985181893 | 280882573 |
| `c_p100_n300` | 2 | 3660972612 | 1905026528 | 459626466 |
| `c_p100_n1000` | 1 | 1183026508 | 3411918116 | 2068885650 |
| `c_p100_n1000` | 2 | 3747385851 | 4040563719 | 852650374 |
| `k5_p30_n150` | 1 | 206790195 | 2883806042 | 2910708632 |
| `k5_p30_n150` | 2 | 3701349812 | 2340026297 | 2242839344 |
| `k10_p100_n200` | 1 | 2517223189 | 2707734806 | 3062796871 |
| `k10_p100_n200` | 2 | 106586968 | 1665305562 | 1926077832 |
| `mix_p100_n200` | 1 | 316203142 | 4063663286 | 582428076 |
| `mix_p100_n200` | 2 | 340727956 | 1680981052 | 1882662359 |

The smoke configuration retains these eight IDs and seed rules while replacing
dimensions with p≤12 and N≤60. Smoke is correctness-only.

## Runner and measurements

Dispatch through the manually triggered `sharded_benchmark.yml` workflow on
`ubuntu-latest`, one process per shard, `--workers 1`, and one each for
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and
`NUMEXPR_NUM_THREADS`. Each shard records the CPU model, Python, NumPy, SciPy,
scikit-learn, pandas, BLAS/threadpool details, config hash, charter SHA-256,
and code revision.

Each row records total elapsed time; `prepare`, `features`, `gram_factor`, `H`,
`omission`, `score`, `aggregate`, and `outputs` seconds; q, t, large
factorizations, fallbacks, requested directional outer fits, fallback fraction,
peak RSS, pair completion and status histogram, variance/probability floor
diagnostics, tuned-penalty grid-extreme fractions, and the first scaled
normal-equation residual.

## Gates

| Gate | Pass condition |
|---|---|
| G-time-small | p≤30 fit elapsed time ≤30 seconds |
| G-time-100 | p=100 fit elapsed time ≤180 seconds |
| G-mem | peak RSS <1 GB |
| G-complete | no failed pairs; all ordinary pairs are `complete` |
| G-factor | `n_large_factorizations` ≤45 |
| G-fallback | fallback fraction ≤1% |

Any cell measured between 0.8× and 1.25× its applicable timing gate requires
repeat 2 in a separate job. Both timings are reported and the slower timing
controls the timing gate.

## Failure and profiling rule

If a gate fails, profile the failing cell on the declared runner with cProfile
and phase timers. Make one profiling-driven, algebra-preserving optimization
pass only: vectorized pair corrections, cached BH/EH products, reused Cholesky
factors, or a dual solver only when q>m factorization is the measured dominant
term. Re-dispatch failed cells and any cell whose code path changed, recording
the new revision. Do not screen, coerce categories, cap neighbors, drop edges,
lower penalties, change tuning, or lower folds. If a gate still fails, record
unsupported p=100 operation and stop broadening claims.

## Reproducibility and decision

The resolved configuration, this charter, and the code revision are hashed in
each shard's metadata. Hosted runner-hours are recorded in
`docs/cin_compute_ledger.csv`; local smoke hours are not. A passing matrix
permits Task 11. A failure after the single profiling pass narrows the
supported operating scope and does not authorize a broad statistical campaign.
