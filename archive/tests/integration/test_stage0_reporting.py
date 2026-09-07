from pathlib import Path

import pandas as pd

from mintnet.experiments.reporting import evaluate_stage0_gate, write_stage0_report
from mintnet.experiments.stage0 import load_stage0_config
from mintnet.simulation.gaussian import gaussian_mi


def _raw_rows(error: bool = False) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for n in (100, 300):
        for rho in (0.0, 0.7):
            for k in (3, 5):
                for replicate in range(3):
                    estimate = gaussian_mi(rho) if not error else 1.0
                    rows.append(
                        {
                            "n": n,
                            "rho": rho,
                            "k": k,
                            "replicate": replicate,
                            "true_mi": gaussian_mi(rho),
                            "estimated_mi": estimate,
                            "elapsed_seconds": 0.001,
                            "status": "error" if error else "ok",
                            "error": "forced" if error else "",
                        }
                    )
    return pd.DataFrame(rows)


def test_gate_proceeds_for_passing_validation_and_writes_evidence(tmp_path: Path) -> None:
    """Changing partition/gate logic would misclassify a known passing fixture."""
    config = load_stage0_config(Path("configs/stage0_gaussian_smoke.yaml"))

    decision = write_stage0_report(_raw_rows(), config, tmp_path)

    assert decision.status == "PROCEED"
    assert decision.selected_k == 3
    assert not decision.failures
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage0_report.md",
        "bias_vs_n.png",
        "rmse_vs_n.png",
        "runtime_vs_n.png",
    ):
        assert (tmp_path / filename).is_file()


def test_gate_reassesses_when_an_estimator_error_is_recorded() -> None:
    """Ignoring a recorded estimator exception would wrongly permit progression."""
    config = load_stage0_config(Path("configs/stage0_gaussian_smoke.yaml"))

    decision = evaluate_stage0_gate(_raw_rows(error=True), config)

    assert decision.status == "REASSESS"
    assert "estimator errors" in decision.failures
