# CIN runner guide

Task 09 provides two deterministic shardable runners. Local smoke runs are correctness checks only; they are not timing evidence and do not dispatch expensive Actions work.

## Local smoke

Run the cost and panel smoke configurations with one worker:

```text
python -m mintnet.experiments.cin_cost --config configs/cin_cost_smoke.yaml --output results/generated/cin_cost_smoke --workers 1
python -m mintnet.experiments.cin_baseline --config configs/cin_baseline_smoke.yaml --output results/generated/cin_baseline_smoke --workers 1
```

Each output contains `raw_metrics.csv`, `resolved_config.yaml`, `metadata.json`, a `sidecars/` directory, and runner-specific reports. Raw rows are flushed after each cell/repeat or method/dataset, including explicit error rows. CIN pair tables are never folded into metadata.

## Verified Actions dispatch shape

The following command was checked against `.github/workflows/sharded_benchmark.yml` inputs. It is documented, not dispatched by local correctness work:

```text
gh workflow run sharded_benchmark.yml \
  -f runner_module=mintnet.experiments.cin_baseline \
  -f config=configs/cin_baseline.yaml \
  -f dim1_flag=--cases -f dim1_values=A,B,C,D,E,F,G,H,I,regression \
  -f dim2_flag=--replicate-batches -f dim2_values=dev0,val0,val1
```

The cost-pilot form uses the same workflow and these verified inputs:

```text
gh workflow run sharded_benchmark.yml \
  -f runner_module=mintnet.experiments.cin_cost \
  -f config=configs/cin_cost.yaml \
  -f dim1_flag=--cells -f dim1_values=c_p8_n100,c_p30_n100,c_p100_n100,c_p100_n300,c_p100_n1000,k5_p30_n150,k10_p100_n200,mix_p100_n200 \
  -f dim2_flag=--repeat -f dim2_values=1,2
```

The runner modules force `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` to `1` before importing numerical libraries, and every fit is wrapped in `threadpool_limits(1)`. The generic workflow remains unchanged for other runners; the CIN runner contract is the one-thread policy.

## Aggregation

After downloading shard artifacts, run the unchanged generic raw aggregator and the CIN sidecar validator:

```text
python scripts/aggregate_shards.py --module mintnet.experiments.cin_baseline --config configs/cin_baseline.yaml --shards-dir shards --output results/generated/cin_baseline_aggregated
python scripts/aggregate_cin_sidecars.py --shards-dir shards --output results/generated/cin_baseline_aggregated
```

The generic aggregator checks expected raw coverage and duplicate identities. The sidecar aggregator separately checks every promised file, byte hash, declared row count, pair cardinality, stability cardinality, duplicate identity, and orphan file before writing `pairs_all.csv.gz` and `stability_all.csv.gz` when applicable. Reports must preserve counts behind means and must retain incomplete or failed rows.

## Task 11 development and validation sequence

Run the full development matrix first. The report writes `development_selection.json`; its display delta is selected from development CIN A/B rows only and must be treated as frozen before validation:

```text
python scripts/aggregate_shards.py --module mintnet.experiments.cin_baseline --config configs/cin_baseline.yaml --shards-dir development-shards --output results/generated/cin_baseline_development
python scripts/aggregate_cin_sidecars.py --shards-dir development-shards --output results/generated/cin_baseline_development
```

Run validation once on the new validation seeds after the development selection is frozen, aggregate its raw rows and sidecars, and then evaluate the named gates without retuning:

```text
python scripts/aggregate_shards.py --module mintnet.experiments.cin_baseline --config configs/cin_baseline.yaml --shards-dir validation-shards --output results/generated/cin_baseline_validation
python scripts/aggregate_cin_sidecars.py --shards-dir validation-shards --output results/generated/cin_baseline_validation
python scripts/cin_gate_check.py --raw results/generated/cin_baseline_validation/raw_metrics.csv --config configs/cin_baseline.yaml --selection results/generated/cin_baseline_development/development_selection.json --output results/generated/cin_baseline_validation/gate_results.json
```

The gate checker refuses development contamination, duplicate or missing validation identities, count mismatch, missing provenance, and charter mismatch. D/I, regression, null, variance-only/XOR, stability, and high-p categorical outputs are descriptive or unsupported where no gate applies. Counts and Monte Carlo standard errors remain visible; the panel does not claim causal effects, precise tail probabilities, FDR control, or broad recovery beyond the named scopes.

## Reproducibility contract

Every dataset derives a `CINSeedBundle` from `SeedSequence([master_seed, 9009, case_index, phase_index, replicate])`. Its fields are `structure`, `sample`, `cin_fit`, `comparator_fit`, and `stability`. Case indices come from the full order `A` through `I`, then `regression`; phase index `0` is development and `1` is validation. Development ids are `[0, 10)` and validation ids are `[1000, 1020)`, with `val0` and `val1` splitting validation at the midpoint.

Each shard writes the full resolved configuration, config and code hashes, package/platform details, BLAS thread settings, CPU information, runtime, and platform-specific RSS. Windows RSS is explicitly `null` because the Linux `resource` measurement is unavailable. A failed comparator is `status=error` with an error type and message; it is never a successful empty graph. A valid fit with unsupported or incomplete pairs remains visible as `status=incomplete`.

The compute ceiling for the statistical panel is 12 aggregate runner-hours. Task 10's accepted hosted cost envelope is the preflight budget baseline; local smoke is correctness-only and must not add timing claims to `docs/cin_compute_ledger.csv`. Any replicate reduction required to remain within the ceiling must be disclosed before validation is frozen.
