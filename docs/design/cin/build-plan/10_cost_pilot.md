# Task 10 — Cost pilot (early p=100 end-to-end gate)

Roadmap: §10, M2 exit. Files: `src/mintnet/experiments/cin_cost.py`, `cin_cost_reporting.py`, `configs/cin_cost.yaml`, `configs/cin_cost_smoke.yaml`, `docs/cin_cost_charter.md`. Depends on tasks 05, 08, 09.

## 1. Purpose

Decide, before any statistical campaign, whether the shared-ridge design fits the compute and memory budget through p = 100, and whether the ridge design meets the completion contract (all pairs complete, no widespread numerical fallback). It is **not** a statistically precise speed comparison and produces no recovery metrics.

## 2. Preconditions

- Tasks 01–05 complete and their unit suites green.
- Task 08 cost-input generators available.
- Task 09 runner skeleton in place (this is its first user).
- Charter frozen (below) **before** dispatch.

## 3. The eight cells

One dataset each, default `CINConfig` (K=3, J=2, five penalties), one BLAS thread, one documented runner (ubuntu-latest GitHub-hosted; record CPU model and BLAS build):

| Cell id | Input | (p, N) | Notes |
|---|---|---|---|
| `c_p8_n100` | dense continuous | (8, 100) | small network |
| `c_p30_n100` | dense continuous | (30, 100) | broad, low N |
| `c_p100_n100` | dense continuous | (100, 100) | p ≥ N, q = 300 > m |
| `c_p100_n300` | dense continuous | (100, 300) | |
| `c_p100_n1000` | dense continuous | (100, 1000) | largest-N matrix cost |
| `k5_p30_n150` | five-level categorical | (30, 150) | q = 150 |
| `k10_p100_n200` | ten-level categorical | (100, 200) | q = t = 1000, maximum declared width |
| `mix_p100_n200` | 50 continuous + 50 five-level | (100, 200) | q = 150 + 250 = 400 |

Cell ids are the `--cells` shard axis (task 09). Inputs from `generate_cost_input` (task 08); no truth is attached and no recovery is scored.

## 4. Measurements (each cell writes one raw row)

- Total elapsed seconds; per-phase seconds: `prepare`, `features`, `gram_factor`, `H`, `omission`, `score`, `aggregate`, `outputs` (use a small `phase_timer` context manager writing into the fit's cost counters).
- `n_large_factorizations`, `q`, `t` (categorical response width), `n_fallbacks`, requested directional outer fits, fallback fraction.
- Peak RSS MB via `resource.getrusage(RUSAGE_SELF).ru_maxrss` (Linux: KiB → MB). Take it at end; single-process shard so it is the fit's peak.
- Pair completion: number of complete pairs / `p(p−1)/2`; statuses histogram.
- Diagnostics: variance-floor hit rate, probability floor stats, tuned-penalty histogram (a guard against always-boundary λ: report fraction of targets choosing the grid extremes).
- Scaled normal-equation residual at the first factorization.
- Environment: python, numpy, scipy, sklearn versions; BLAS library; thread counts.

## 5. Gates (roadmap §10; proposed targets, not results)

| Gate | Threshold |
|---|---|
| G-time-small | p ≤ 30 cells: fit ≤ 30 s |
| G-time-100 | p = 100 cells: fit ≤ 180 s |
| G-mem | peak RSS < 1 GB |
| G-complete | no failed pairs (all `complete`) in ordinary cells |
| G-factor | `n_large_factorizations ≤ 45` |
| G-fallback | fallback fraction ≤ 1% (roadmap §5.2 hard stop) |

**Boundary repeat rule**: any cell within 20% of a timing gate (**[added]** interpretation of "near-boundary": measured time between 0.8× and 1.25× the gate) is run once more in a separate job (`--repeat 2`) to separate gross timing noise; both timings are reported. The gate outcome uses the slower run **[added]** unless the charter says otherwise; report both regardless.

## 6. One profiling-driven implementation pass

If any gate fails:

1. Profile the failing cell on the runner (`cProfile` summary and phase timers, both recorded as artifacts) to identify the dominant term (candidates: `X@H` products for evaluation/training matrices at q=1000, Python loop overhead in per-pair omission, repeated `H` formation, feature construction).
2. Make **one** implementation pass restricted to algebra-preserving optimizations: batching pair corrections per target with vectorized `einsum`, caching `BH`/`EH`, reusing target-block Cholesky factors, or — only if the dominant cost is the primal factorization at q > m — the dual solver (an algebra-preserving optimization that yields identical predictions).
3. Re-dispatch only the failed cells (plus any cell whose code path changed) and record the code revision.

Forbidden as speed fixes: screening, coercing categories to continuous, capping neighbors, dropping edges, lowering penalty count, changing tuning (GCV is a different procedure and is out of scope), or silently reducing folds. If the gates still fail after the one pass, **record unsupported p=100 operation and stop broadening claims**; a smaller-p preview does not complete the 100-variable objective.

## 7. Charter (`docs/cin_cost_charter.md`, frozen before dispatch)

Contents: the eight cells with exact generator parameters and seeds; runner definition (OS, image, CPU cores, Python/BLAS versions, thread settings); gates verbatim; boundary-repeat rule; profiling-pass rules; what is *not* claimed (statistical precision, general runtime law); config and code-revision hashing; ledger entry; the decision rule (pass ⇒ proceed to task 11; fail after profiling ⇒ narrow scope). Record its SHA-256 in each shard's metadata via the runner (task 09).

## 8. Reporting (`cin_cost_reporting.py`)

Writes `cost_report.md` and `cost_summary.csv`: one table with cells × (elapsed, phases, RSS, q, t, factors, fallbacks, completion, gate verdicts), both timings for repeated cells, the runner description, and an explicit paragraph: "This is a cost pilot; timings are single-dataset measurements on shared hosted runners." No verdict language beyond gate pass/fail.

## 9. Local smoke

`configs/cin_cost_smoke.yaml`: the same eight cell *ids* with tiny substituted sizes (p ≤ 12, N ≤ 60) to exercise code paths:

```bash
python -m mintnet.experiments.cin_cost --config configs/cin_cost_smoke.yaml --output results/generated/cin_cost_smoke
```

Correctness only; smoke timings are not published or compared to gates.

## 10. Acceptance / exit

All gates recorded for all eight cells on the declared runner with both boundary timings where applicable; decision logged (pass / pass-after-pass / unsupported p=100). Runner-hours charged to the ledger. Then proceed to task 11.

## 11. Pitfalls

- `q = 1000` factorization plus `H` per penalty: memory ≈ several ×8 MB; the `EH`/`BH` caches scale with rows × q; verify RSS on the p=100, N=1000 cell (`BH` is 1000×300 → trivial for continuous, `k10` has m ≈ 133–200 train rows).
- The `k10_p100_n200` cell is exactly at the q cap (`q = 1000`); an off-by-one in the cap check would reject the mandated input.
- Do not let the categorical cost inputs pass through a graph-truth pipeline; the raw row has no truth columns.
