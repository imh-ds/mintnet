"""Deterministic, shardable CIN statistical-panel runner."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import os
from pathlib import Path
import time
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

from mintnet.cin import CINConfig, estimate_stability, fit_network  # noqa: E402
from mintnet.comparators.ebicglasso import fit_ebicglasso  # noqa: E402
from mintnet.simulation import (  # noqa: E402
    ORGANIC_NETWORK_TRUE_EDGES,
    generate_case,
    sample_organic_network,
)

from .cin_common import (  # noqa: E402
    IncrementalCsvWriter,
    canonical_pair_sidecar_name,
    canonical_stability_sidecar_name,
    derive_seed_bundle,
    load_yaml,
    peak_rss_mb,
    sha256_file,
    thread_limits,
    write_gzip_frame,
    write_provenance,
    write_resolved_config,
)


CASE_ORDER = tuple("ABCDEFGHI") + ("regression",)
CONTINUOUS_CASES = frozenset(("A", "B", "C", "D", "E", "regression"))
PANEL_COMBINATION_COLUMNS = ("case", "phase", "method")
COMBINATION_COLUMNS = PANEL_COMBINATION_COLUMNS
METHODS = ("cin", "cin_linear", "ebicglasso")
DELTA_TOKENS = ("0", "005", "01", "02")


@dataclass(frozen=True)
class PanelConfig:
    cases: tuple[str, ...]
    master_seed: int
    development_replicates: tuple[int, ...]
    validation_replicates: tuple[int, ...]
    n_overrides: dict[str, int]
    stability_cases: tuple[str, ...]
    stability_repeats: int
    stability_fraction: float
    source_path: Path


PANEL_RAW_COLUMNS = (
    "case", "phase", "replicate", "method", "structure_seed", "sample_seed",
    "cin_fit_seed", "comparator_fit_seed", "stability_seed", "n", "p", "status",
    "error_type", "error", "elapsed_seconds", "peak_rss_mb", "ap", "prevalence",
    "ap_minus_prevalence", "n_pairs_complete", "n_pairs_total", "n_failed_pairs",
    "strong_edge_recall", "oracle_cmi_mae", "oracle_cmi_bias", "categorical_excess_loss",
    "positive_weight_q50", "positive_weight_q90", "positive_weight_q95", "positive_weight_q99",
    "positive_weight_max", "tie_fraction",
    *tuple(
        field
        for prefix in ("delta", "agreement_delta")
        for token in DELTA_TOKENS
        for field in (
            f"{prefix}_{token}_displayed_count",
            f"{prefix}_{token}_displayed_fraction",
            f"{prefix}_{token}_precision",
            f"{prefix}_{token}_recall",
            f"{prefix}_{token}_empty",
        )
    ),
    "pair_sidecar_file", "stability_sidecar_file",
)
MANIFEST_COLUMNS = ("file", "case", "phase", "replicate", "method", "kind", "n_rows", "sha256")


def _replicate_range(values: object, name: str) -> tuple[int, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a non-empty list")
    result = tuple(int(value) for value in values)
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def load_config(path: Path) -> PanelConfig:
    source = Path(path)
    payload = load_yaml(source)
    cases_value = payload.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        raise ValueError("panel configuration requires non-empty cases")
    cases = tuple(str(value) for value in cases_value)
    unknown = sorted(set(cases) - set(CASE_ORDER))
    if unknown:
        raise ValueError(f"unknown case: {unknown[0]}")
    if len(set(cases)) != len(cases):
        raise ValueError("panel cases must not contain duplicates")
    development = _replicate_range(payload.get("development_replicates"), "development_replicates")
    validation = _replicate_range(payload.get("validation_replicates"), "validation_replicates")
    if set(development) & set(validation):
        raise ValueError("development and validation replicate ranges must be disjoint")
    overrides_value = payload.get("n_overrides", {})
    if not isinstance(overrides_value, dict):
        raise ValueError("n_overrides must be a mapping")
    overrides = {str(key): int(value) for key, value in overrides_value.items()}
    if set(overrides) - set(cases):
        raise ValueError("n_overrides may only name configured cases")
    if any(value < 1 for value in overrides.values()):
        raise ValueError("n_overrides values must be positive")
    master_seed = int(payload.get("master_seed", -1))
    if master_seed < 0:
        raise ValueError("master_seed must be nonnegative")
    stability_cases = tuple(str(value) for value in payload.get("stability_cases", ()))
    if set(stability_cases) - set(cases):
        raise ValueError("stability_cases must be configured cases")
    stability_repeats = int(payload.get("stability_repeats", 0))
    stability_fraction = float(payload.get("stability_fraction", 0.0))
    if stability_repeats < 0 or not 0.0 < stability_fraction <= 1.0:
        raise ValueError("invalid stability settings")
    return PanelConfig(
        cases=cases,
        master_seed=master_seed,
        development_replicates=development,
        validation_replicates=validation,
        n_overrides=overrides,
        stability_cases=stability_cases,
        stability_repeats=stability_repeats,
        stability_fraction=stability_fraction,
        source_path=source.resolve(),
    )


def methods_for_case(case: str) -> tuple[str, ...]:
    if case not in CASE_ORDER:
        raise ValueError(f"unknown case: {case}")
    return METHODS if case in CONTINUOUS_CASES else ("cin",)


def expected_row_count(config: PanelConfig) -> int:
    n_phases = len(config.development_replicates) + len(config.validation_replicates)
    return sum(len(methods_for_case(case)) for case in config.cases) * n_phases


def expected_combinations(config: PanelConfig) -> set[tuple[str, str, str]]:
    return {
        (case, phase, method)
        for case in config.cases
        for phase in ("development", "validation")
        for method in methods_for_case(case)
    }


def _config_payload(config: PanelConfig) -> dict[str, Any]:
    return {
        "master_seed": config.master_seed,
        "cases": list(config.cases),
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "n_overrides": dict(config.n_overrides),
        "stability_cases": list(config.stability_cases),
        "stability_repeats": config.stability_repeats,
        "stability_fraction": config.stability_fraction,
    }


def _phase_batches(config: PanelConfig, batches: tuple[str, ...] | None) -> list[tuple[str, tuple[int, ...], int]]:
    selected = set(batches or ("dev0", "val0", "val1"))
    known = {"dev0", "val0", "val1"}
    if selected - known:
        raise ValueError(f"unknown replicate batches: {sorted(selected - known)}")
    validation_midpoint = len(config.validation_replicates) // 2
    choices = {
        "dev0": ("development", config.development_replicates, 0),
        "val0": ("validation", config.validation_replicates[:validation_midpoint], 1),
        "val1": ("validation", config.validation_replicates[validation_midpoint:], 1),
    }
    return [choices[name] for name in ("dev0", "val0", "val1") if name in selected]


def _regression_dataset(seed: int, n: int = 300) -> tuple[pd.DataFrame, dict[str, dict[str, Any]], frozenset[tuple[str, str]], None, dict[str, Any]]:
    frame = pd.DataFrame(
        sample_organic_network(n, np.random.default_rng(seed)),
        columns=[f"V{index:02d}" for index in range(14)],
    )
    names = tuple(frame.columns)
    truth = frozenset((names[left], names[right]) for left, right in ORGANIC_NETWORK_TRUE_EDGES)
    return frame, {name: {"kind": "continuous"} for name in names}, truth, None, {"case": "regression", "n": n, "p": 14}


def _dataset(case: str, structure_seed: int, sample_seed: int, n_override: int | None) -> Any:
    if case == "regression":
        return _regression_dataset(sample_seed, n_override or 300)
    generated = generate_case(case, structure_seed=structure_seed, sample_seed=sample_seed, n=n_override)
    return generated.frame, generated.schema, generated.truth_edges, generated.population_cmi, generated.meta


def _write_manifest_row(output_dir: Path, row: dict[str, Any]) -> None:
    path = output_dir / "sidecar_manifest.csv"
    prior = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=MANIFEST_COLUMNS)
    pd.concat([prior, pd.DataFrame([row])], ignore_index=True).to_csv(path, index=False, lineterminator="\n")


def _empty_row(case: str, phase: str, replicate: int, method: str, seeds: Any, n: int, p: int) -> dict[str, Any]:
    row = {column: None for column in PANEL_RAW_COLUMNS}
    row.update({
        "case": case, "phase": phase, "replicate": replicate, "method": method,
        "structure_seed": seeds.structure, "sample_seed": seeds.sample, "cin_fit_seed": seeds.cin_fit,
        "comparator_fit_seed": seeds.comparator_fit, "stability_seed": seeds.stability,
        "n": n, "p": p, "n_pairs_total": p * (p - 1) // 2,
    })
    return row


def _pair_frame_from_ebic(names: tuple[str, ...], result: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    diagonal = np.sqrt(np.diag(result.precision))
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            partial = -float(result.precision[left, right]) / float(diagonal[left] * diagonal[right])
            score = abs(partial) if np.isfinite(partial) else np.nan
            rows.append({
                "node_i": names[left], "node_j": names[right], "gain_i_to_j": partial,
                "gain_j_to_i": partial, "weight_nats_raw": score,
                "display_magnitude_nats": score, "gaussian_equivalent_magnitude": score,
                "orientation_gap": 0.0, "n_scored": 0, "folds_complete": 1,
                "status": "complete", "diagnostic_flags": "",
            })
    return pd.DataFrame(rows)


def _quantile(row: dict[str, Any], prefix: str, values: np.ndarray) -> None:
    positive = values[np.isfinite(values) & (values > 0)]
    if positive.size:
        for token, quantile in (("q50", .50), ("q90", .90), ("q95", .95), ("q99", .99)):
            row[f"positive_weight_{token}"] = float(np.quantile(positive, quantile))
        row["positive_weight_max"] = float(np.max(positive))


def _display_metrics(row: dict[str, Any], pair_frame: pd.DataFrame, truth: frozenset[tuple[str, str]], prefix: str, agreement: bool) -> None:
    weights = pd.to_numeric(pair_frame["weight_nats_raw"], errors="coerce")
    complete = pair_frame["status"].eq("complete") & weights.notna()
    if agreement:
        complete &= pair_frame["gain_i_to_j"].gt(0) & pair_frame["gain_j_to_i"].gt(0)
    for token, delta in zip(DELTA_TOKENS, (0.0, .005, .01, .02)):
        passing = complete & weights.gt(0) & weights.ge(delta)
        count = int(passing.sum())
        predicted = set(zip(pair_frame.loc[passing, "node_i"], pair_frame.loc[passing, "node_j"]))
        tp = len(predicted & truth)
        row[f"{prefix}_{token}_displayed_count"] = count
        row[f"{prefix}_{token}_displayed_fraction"] = float(count / len(pair_frame)) if len(pair_frame) else np.nan
        row[f"{prefix}_{token}_precision"] = float(tp / count) if count else np.nan
        row[f"{prefix}_{token}_recall"] = float(tp / len(truth)) if truth else np.nan
        row[f"{prefix}_{token}_empty"] = count == 0


def _metrics(row: dict[str, Any], pair_frame: pd.DataFrame, truth: frozenset[tuple[str, str]], population_cmi: dict[tuple[str, str], float] | None) -> None:
    weights = pd.to_numeric(pair_frame["weight_nats_raw"], errors="coerce").to_numpy(dtype=float)
    complete = pair_frame["status"].eq("complete").to_numpy() & np.isfinite(weights)
    row["n_pairs_complete"] = int(complete.sum())
    row["n_failed_pairs"] = int(len(pair_frame) - int(complete.sum()))
    _quantile(row, "positive_weight", weights)
    finite = weights[complete]
    if finite.size:
        row["tie_fraction"] = float(1.0 - pd.Series(finite).nunique() / finite.size)
    if truth and complete.all():
        labels = np.asarray([(
            str(left), str(right)
        ) in truth for left, right in zip(pair_frame["node_i"], pair_frame["node_j"])], dtype=int)
        row["ap"] = float(average_precision_score(labels, weights))
        row["prevalence"] = float(labels.mean())
        row["ap_minus_prevalence"] = row["ap"] - row["prevalence"]
    _display_metrics(row, pair_frame, truth, "delta", False)
    _display_metrics(row, pair_frame, truth, "agreement_delta", True)
    if population_cmi is not None and truth:
        differences = [float(pair_frame.loc[(pair_frame["node_i"] == left) & (pair_frame["node_j"] == right), "weight_nats_raw"].iloc[0]) - float(value) for (left, right), value in population_cmi.items() if (left, right) in truth]
        if differences:
            row["oracle_cmi_mae"] = float(np.mean(np.abs(differences)))
            row["oracle_cmi_bias"] = float(np.mean(differences))
        strong = {edge for edge, value in population_cmi.items() if edge in truth and value >= .01}
        if strong:
            selected = set(zip(pair_frame.loc[complete & (pair_frame["weight_nats_raw"] > 0), "node_i"], pair_frame.loc[complete & (pair_frame["weight_nats_raw"] > 0), "node_j"]))
            row["strong_edge_recall"] = float(len(selected & strong) / len(strong))


def _fit_method(method: str, frame: pd.DataFrame, schema: dict[str, dict[str, Any]], seeds: Any) -> tuple[pd.DataFrame, Any, float | None]:
    if method == "ebicglasso":
        result = fit_ebicglasso(frame.to_numpy(dtype=float))
        if not any(np.isfinite(result.ebic_by_lambda)):
            raise RuntimeError("EBICglasso path did not converge at any lambda")
        return _pair_frame_from_ebic(tuple(frame.columns), result), result, None
    config = CINConfig(seed=seeds.cin_fit)
    if method == "cin_linear":
        config = replace(config, max_curvature_rank=0)
    with thread_limits():
        fit = fit_network(frame, schema, config)
    pairs = fit.pairs.copy()
    return pairs, fit, float(fit.metadata.get("runtime", {}).get("elapsed_seconds", 0.0))


def _run_method(config: PanelConfig, output_dir: Path, case: str, phase: str, replicate: int, method: str, seeds: Any, frame: pd.DataFrame, schema: dict[str, dict[str, Any]], truth: frozenset[tuple[str, str]], population_cmi: dict[tuple[str, str], float] | None) -> dict[str, Any]:
    row = _empty_row(case, phase, replicate, method, seeds, len(frame), len(frame.columns))
    started = time.perf_counter()
    try:
        with thread_limits():
            pair_frame, fit_result, elapsed_estimate = _fit_method(method, frame, schema, seeds)
        sidecar_name = canonical_pair_sidecar_name(case, phase, replicate, method)
        sidecar_path = output_dir / "sidecars" / sidecar_name
        n_rows = write_gzip_frame(pair_frame, sidecar_path)
        _write_manifest_row(output_dir, {"file": sidecar_name, "case": case, "phase": phase, "replicate": replicate, "method": method, "kind": "pairs", "n_rows": n_rows, "sha256": sha256_file(sidecar_path)})
        row["status"] = "complete" if pair_frame["status"].eq("complete").all() else "incomplete"
        row["elapsed_seconds"] = time.perf_counter() - started
        row["peak_rss_mb"] = peak_rss_mb()
        _metrics(row, pair_frame, truth, population_cmi)
        if method == "cin" and hasattr(fit_result, "nodes"):
            node_gain = pd.to_numeric(fit_result.nodes.get("full_minus_intercept"), errors="coerce")
            if node_gain.notna().any() and any(schema[name].get("kind") == "categorical" for name in schema):
                row["categorical_excess_loss"] = float(-node_gain.mean())
        if case in config.stability_cases and phase == "validation" and method in {"cin", "cin_linear"} and hasattr(fit_result, "metadata"):
            stability = estimate_stability(
                fit_result,
                frame,
                repeats=config.stability_repeats,
                fraction=config.stability_fraction,
                max_seconds=600.0,
                elapsed_estimate=elapsed_estimate,
            )
            stability_name = canonical_stability_sidecar_name(case, phase, replicate, method)
            stability_path = output_dir / "sidecars" / stability_name
            stability_rows = write_gzip_frame(stability.records, stability_path)
            _write_manifest_row(output_dir, {"file": stability_name, "case": case, "phase": phase, "replicate": replicate, "method": method, "kind": "stability", "n_rows": stability_rows, "sha256": sha256_file(stability_path)})
            row["stability_sidecar_file"] = stability_name
        row["pair_sidecar_file"] = sidecar_name
    except Exception as exc:  # noqa: BLE001 - durable failure rows are required.
        row.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc), "elapsed_seconds": time.perf_counter() - started, "peak_rss_mb": peak_rss_mb()})
    return row


def run_baseline(
    config: PanelConfig,
    output_dir: Path,
    *,
    cases: tuple[str, ...] | None = None,
    replicate_batches: tuple[str, ...] | None = None,
    workers: int = 1,
    write_report: bool = True,
) -> pd.DataFrame:
    """Run selected panel shards using full-grid case and phase coordinates."""

    if workers != 1:
        raise ValueError("CIN runners currently require --workers 1")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "sidecars").mkdir(parents=True, exist_ok=True)
    payload = load_yaml(config.source_path)
    write_resolved_config(target, payload)
    selected_cases = set(cases or config.cases)
    unknown = selected_cases - set(config.cases)
    if unknown:
        raise ValueError(f"unknown configured cases: {sorted(unknown)}")
    batches = _phase_batches(config, replicate_batches)
    rows: list[dict[str, Any]] = []
    writer = IncrementalCsvWriter(target / "raw_metrics.csv", PANEL_RAW_COLUMNS)
    started = time.perf_counter()
    try:
        for case in config.cases:
            if case not in selected_cases:
                continue
            case_index = CASE_ORDER.index(case)
            for phase, replicates, phase_index in batches:
                for replicate in replicates:
                    seeds = derive_seed_bundle(config.master_seed, case_index, phase_index, replicate)
                    n_override = config.n_overrides.get(case)
                    try:
                        frame, schema, truth, population_cmi, _ = _dataset(case, seeds.structure, seeds.sample, n_override)
                    except Exception as exc:  # keep every method identity durable after a dataset failure.
                        for method in methods_for_case(case):
                            failure = _empty_row(case, phase, replicate, method, seeds, n_override or 300, 0)
                            failure.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)})
                            writer.append(failure)
                            rows.append(failure)
                        continue
                    for method in methods_for_case(case):
                        row = _run_method(config, target, case, phase, replicate, method, seeds, frame, schema, truth, population_cmi)
                        writer.append(row)
                        rows.append(row)
    finally:
        writer.close()
    write_provenance(
        target, config_payload=payload, source_path=config.source_path, charter_path=None,
        runtime_seconds=time.perf_counter() - started, peak_rss_mb=peak_rss_mb(),
    )
    raw = pd.DataFrame(rows, columns=PANEL_RAW_COLUMNS)
    if write_report:
        try:
            from . import cin_baseline_reporting

            cin_baseline_reporting.write_report(raw, config, target)
        except ImportError:
            pass
    return raw


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cases", type=_parse_csv)
    parser.add_argument("--replicate-batches", type=_parse_csv)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    run_baseline(
        load_config(args.config), args.output, cases=args.cases,
        replicate_batches=args.replicate_batches, workers=args.workers,
        write_report=not args.no_report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CASE_ORDER", "COMBINATION_COLUMNS", "PANEL_RAW_COLUMNS", "PanelConfig",
    "expected_combinations", "expected_row_count", "load_config", "methods_for_case", "run_baseline",
]
