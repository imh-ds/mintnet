# F Follow-Up v2 Local Correctness Smoke

This is a correctness-only diagnostic, not a development-selection result or validation observation. It used the reserved diagnostic identity `F/development/6300`, separate from v2 development IDs 6400–6419 and validation IDs 6500–6596. Its complete five-stream seed bundle is recorded in `diagnostic_seed_inventory.csv`, which is part of the v2 preflight hash inventory.

The repository runner completed all 28 CIN pair fits with status `complete`, using attempt cap 1,000 and support-aware inner splits. Runtime was approximately 0.340 seconds on Python 3.11.9, NumPy 2.4.6, pandas 3.0.5, SciPy 1.17.1, scikit-learn 1.9.0, PyYAML 6.0.3, and threadpoolctl 3.6.0 on Windows 10. The sidecar manifest records 28 rows and SHA-256 `f50886b599576526bdcc7a03c000b2d9a2e71b5c55758194b4e173e6c655bd1c`; the raw metrics SHA-256 is `d1939bd8af161e33719b2e0ded6c312c801d1e7702ba25d681ba161dc7d6c723`.

Reproduction command (using the one-identity diagnostic config with the v2 candidate settings):

```powershell
.\.venv\Scripts\python.exe -m mintnet.experiments.cin_baseline `
  --config docs/cin_followup_audit/followup_f_v2/diagnostic-smoke-config.yaml `
  --output docs/cin_followup_audit/followup_f_v2/diagnostic-smoke `
  --cases F --replicate-batches dev0 --no-report
```

The diagnostic config and resolved form are retained with the outputs. This smoke only verifies local runner and sidecar behavior. It does not validate hosted performance, completion probability, recovery accuracy, or any statistical gate.
