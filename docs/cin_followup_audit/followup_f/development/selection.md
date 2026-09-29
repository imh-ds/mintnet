# F Follow-Up Development Selection

Evidence refreshed: 2026-09-29 against source commit `d006f7f46a9011125f923de540dce6ac90d3ab11`. All five runs used fresh output folders and the final frozen charter.

## Environment and identity handling

Runs used Python 3.11.9 with the repository `.venv` pinned packages, NumPy 2.4.6, pandas 3.0.5, SciPy 1.17.1, scikit-learn 1.9.0, PyYAML 6.0.3, threadpoolctl 3.6.0, and matplotlib 3.11.1. BLAS/OpenMP thread counts were set to one. The matching dependency pins are in `requirements-cin-followup-v1.txt`. Development IDs were exactly 2000–2019 with master seed 20260928. The five seed streams matched between fit arms and were preflighted against the D-106 development, validation, and diagnostic inventories.

The baseline and support-aware fit arms were both rerun under the same source tree and cap after the candidate implementation was added. The baseline arm uses `--support-aware-inner-splits false`; the candidate arm uses the versioned config's `true` setting. Their generated datasets, structure/sample/fit seeds, and generator-attempt counts match identity by identity.

## Generator attempt-cap selection

Separate 20-identity runs at caps 500, 1,000, and 2,500 each generated all 20 datasets. Every identity was accepted within 292 attempts, with a median of 86.5 attempts. The attempt sequence was:

```text
55, 107, 20, 125, 274, 72, 239, 10, 40, 121,
6, 9, 28, 151, 50, 292, 193, 21, 243, 101
```

All three caps produced the same attempt counts, so the smallest predeclared qualifying cap, 500, was selected. These observations are about this development set only; they do not establish a future acceptance rate.

## Support-aware split selection

The candidate leaves outer folds unchanged. Within an outer-training partition, it retains the ordinary seeded split when all categorical targets have support in every inner-training partition. If support is missing, it evaluates 255 additional seeded balanced partitions and chooses the one with the fewest unsupported categorical target/fold combinations, breaking ties by normalized marginal category-count imbalance. It only reads category codes from that outer-training partition; outer evaluation rows do not influence the split. The downstream support guard remains active.

| Outcome across 20 paired identities | Existing split | Support-aware candidate |
| --- | ---: | ---: |
| Complete fits | 19 | 20 |
| Complete pair rows | 553 / 560 | 560 / 560 |
| Unsupported pair rows | 7 | 0 |
| Previously complete identities made incomplete | — | 0 |
| Incomplete identities improved to complete | — | 1 (`F/development/2009`) |

The candidate meets the charter's development-only selection rule on this sample. That result is not a validation result and is not a claim that the 97 fresh validation identities will all complete.

## Runtime and hosted estimate

In the paired local runs, total runner-reported elapsed time was 4.10 seconds baseline and 3.28 seconds candidate; fit-time medians were 0.125 seconds per identity in both arms. These Windows measurements are correctness and scale diagnostics, not estimates of hosted setup time.

The hosted estimate uses the ledger's Task 10 average of 44 seconds per job (0.22 runner-hours / 18 jobs), Task 11 development average of 125 seconds per job (0.4175 hours / 12 jobs), and Task 11 validation average of 216 seconds per job (1.319722 hours / 22 jobs). The planned workflow grid has 23 jobs: 5 development shards, 4 validation shards, and 14 plan/aggregation jobs. This gives approximately 0.585 runner-hours for one pass. A second complete pass doubles that to 1.17 hours; the frozen ceiling is rounded to 1.25 runner-hours.

Seven manual workflow runs are expected to take roughly 15–30 minutes wall time when submitted sequentially; allow up to an hour for one full operational replay or queue delay. This is an estimate based on prior hosted runs, not hosted timing for this campaign. The 1.25-hour ceiling includes one full replay and covers only this F-only scope.

## Evidence files

Each run folder contains its raw result rows, runtime metadata, resolved config, sidecar manifest, and pair sidecars:

- `cap-500/`, `cap-1000/`, `cap-2500/`
- `baseline-500/`, `candidate-500/`

`checksums.sha256` records the SHA-256 digest for each preserved evidence file. The baseline/candidate folders are approximately 131 KB together and let reviewers inspect the seven baseline unsupported pairs and their candidate resolution directly.
