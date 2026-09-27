from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path

import pandas as pd

import mintnet.cin as cin
from mintnet.cin.result import PAIR_COLUMNS, NetworkFit, compute_fit_id


ROOT = Path(__file__).resolve().parents[2]


def test_python_examples_in_researcher_guide_execute(tmp_path, monkeypatch) -> None:
    guide = (ROOT / "docs" / "cin_user_guide.md").read_text(encoding="utf-8")
    examples = re.findall(r"```python\s*\n(.*?)\n```", guide, flags=re.DOTALL)
    assert len(examples) == 3

    monkeypatch.chdir(tmp_path)

    # Keep this documentation wiring check fast; the real estimator and
    # repeated-refit behavior have dedicated numerical/unit tests.

    def fast_fit(frame, schema, config):
        names = list(schema)
        pair_rows = [
            {
                "node_i": left,
                "node_j": right,
                "gain_i_to_j": 0.2,
                "gain_j_to_i": 0.2,
                "weight_nats_raw": 0.2,
                "display_magnitude_nats": 0.2,
                "gaussian_equivalent_magnitude": 0.5,
                "orientation_gap": 0.0,
                "n_scored": len(frame),
                "folds_complete": config.outer_folds,
                "status": "complete",
                "diagnostic_flags": "",
            }
            for left, right in combinations(names, 2)
        ]
        schema_copy = {name: dict(spec) for name, spec in schema.items()}
        metadata = {
            "config_hash": "guide-test-config",
            "config": {
                "outer_folds": config.outer_folds,
                "inner_folds": config.inner_folds,
                "lambda_grid": list(config.lambda_grid),
                "missing": config.missing,
                "seed": config.seed,
                "max_curvature_rank": config.max_curvature_rank,
            },
            "schema": schema_copy,
            "digests": {"data_digest": "guide-test-data", "row_identity_digest": "guide-test-rows"},
            "git_revision": "guide-test-revision",
            "fit_id": compute_fit_id("guide-test-config", schema_copy, "guide-test-data", "guide-test-revision"),
            "complete": True,
            "runtime": {"status": "complete", "elapsed_seconds": 0.01},
            "retained_count": len(frame),
            "excluded_count": 0,
            "data_diagnostics": {"few_unique_continuous": [], "rare_levels": [], "p_ge_n": False},
        }
        return NetworkFit(
            pairs=pd.DataFrame(pair_rows, columns=PAIR_COLUMNS),
            nodes=pd.DataFrame([{"node": name} for name in names]),
            folds=pd.DataFrame([{"fold": 0, "status": "complete"}]),
            metadata=metadata,
        )

    class FastStability:
        def __init__(self, fit, repeats, fraction):
            self.fit_id = fit.metadata["fit_id"]
            self.metadata = {"B": repeats, "fraction": fraction, "repeats_completed": repeats}
            self.records = pd.DataFrame(
                [
                    {"node_i": row.node_i, "node_j": row.node_j, "stability": 1.0}
                    for row in fit.pairs.itertuples(index=False)
                ]
            )

        def for_rule(self, *, min_effect, require_both_positive):
            return self.records.copy()

        def save(self, directory, *, compressed=False):
            Path(directory).mkdir(parents=True, exist_ok=True)
            (Path(directory) / "stability_stub.txt").write_text("test double\n", encoding="utf-8")

    monkeypatch.setattr(cin, "fit_network", fast_fit)
    monkeypatch.setattr(
        cin,
        "estimate_stability",
        lambda fit, frame, *, repeats, fraction, max_seconds: FastStability(fit, repeats, fraction),
    )
    namespace: dict[str, object] = {"__name__": "__cin_user_guide_example__"}
    for example in examples:
        exec(compile(example, "docs/cin_user_guide.md", "exec"), namespace)
