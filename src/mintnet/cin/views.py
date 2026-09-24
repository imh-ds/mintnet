"""Pure, named views over persisted CIN fit results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .result import NetworkFit

__all__ = ["NetworkView", "make_view"]


def _plain(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _plain(value.item())
    if isinstance(value, np.ndarray):
        return [_plain(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _fit_nodes(fit: NetworkFit) -> tuple[str, ...]:
    schema = fit.metadata.get("schema")
    if not isinstance(schema, Mapping):
        raise ValueError("fit metadata must contain schema variable order")
    names = tuple(str(name) for name in schema)
    if len(names) < 2 or len(set(names)) != len(names):
        raise ValueError("fit schema must contain at least two unique nodes")
    return names


def _stability_fit_id(stability: Any) -> str | None:
    if isinstance(stability, Mapping):
        value = stability.get("fit_id")
    else:
        value = getattr(stability, "fit_id", None)
    return str(value) if value is not None else None


def _stability_metadata(stability: Any) -> dict[str, Any] | None:
    if isinstance(stability, Mapping):
        value = stability.get("metadata")
    else:
        value = getattr(stability, "metadata", None)
    if value is None:
        return None
    return _plain(value)


def _stability_for_rule(
    stability: Any,
    *,
    min_effect: float,
    require_both_positive: bool,
) -> Any:
    """Resolve the Task 7 protocol only when a stability filter is requested."""

    for_rule = getattr(stability, "for_rule", None)
    if callable(for_rule):
        return for_rule(
            min_effect=min_effect,
            require_both_positive=require_both_positive,
        )
    if isinstance(stability, Mapping):
        for_rule = stability.get("for_rule")
        if callable(for_rule):
            return for_rule(
                min_effect=min_effect,
                require_both_positive=require_both_positive,
            )
    try:
        from .stability import stability_for_rule
    except ModuleNotFoundError as exc:
        raise ValueError("stability support is not available") from exc
    return stability_for_rule(
        stability,
        min_effect=min_effect,
        require_both_positive=require_both_positive,
    )


def _stability_table(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        table = value.copy(deep=True)
    elif isinstance(value, Mapping):
        records = value.get("records", value.get("pairs"))
        table = pd.DataFrame(records)
    else:
        records = getattr(value, "records", getattr(value, "pairs", None))
        table = pd.DataFrame(records)
    if "stability" not in table.columns:
        for candidate in ("fraction_stable", "stability_fraction", "value"):
            if candidate in table.columns:
                table = table.rename(columns={candidate: "stability"})
                break
    required = {"node_i", "node_j", "stability"}
    missing = required - set(table.columns)
    if missing:
        raise ValueError(f"stability table is missing columns: {sorted(missing)!r}")
    return table.loc[:, ["node_i", "node_j", "stability"]].copy()


def _canonical_stability(
    table: pd.DataFrame,
    node_order: tuple[str, ...],
) -> pd.DataFrame:
    positions = {name: index for index, name in enumerate(node_order)}
    rows: list[dict[str, Any]] = []
    for record in table.to_dict(orient="records"):
        left = str(record["node_i"])
        right = str(record["node_j"])
        if left not in positions or right not in positions or left == right:
            continue
        if positions[left] > positions[right]:
            left, right = right, left
        rows.append({"node_i": left, "node_j": right, "stability": record["stability"]})
    return pd.DataFrame(rows, columns=["node_i", "node_j", "stability"])


@dataclass(frozen=True)
class NetworkView:
    """A non-refitting, immutable description of a filtered network view."""

    edges: pd.DataFrame
    settings: dict[str, Any]
    fit_id: str
    stability_meta: dict[str, Any] | None
    node_order: tuple[str, ...]
    label: str
    description: str
    all_pairs: pd.DataFrame = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edges", self.edges.copy(deep=True))
        object.__setattr__(self, "all_pairs", self.all_pairs.copy(deep=True))
        object.__setattr__(self, "settings", _plain(dict(self.settings)))
        object.__setattr__(self, "node_order", tuple(self.node_order))
        if self.stability_meta is not None:
            object.__setattr__(self, "stability_meta", _plain(self.stability_meta))

    def to_edge_list(self) -> pd.DataFrame:
        """Return the interoperable edge list using display magnitudes."""

        result = self.edges.loc[:, ["node_i", "node_j"]].copy()
        result["weight"] = self.edges["display_magnitude_nats"].to_numpy()
        if "stability" in self.edges.columns:
            result["stability"] = self.edges["stability"].to_numpy()
        return result

    def to_matrix(self, *, fill: float | None = np.nan) -> pd.DataFrame:
        """Return a labelled symmetric display matrix.

        Complete but non-displayed pairs are zero; incomplete pairs remain NaN
        unless a caller explicitly supplies a plotting fill value.
        """

        positions = {name: index for index, name in enumerate(self.node_order)}
        default = np.nan if fill is None else float(fill)
        values = np.full((len(self.node_order), len(self.node_order)), default, dtype=np.float64)
        np.fill_diagonal(values, 0.0)
        for record in self.all_pairs.to_dict(orient="records"):
            if record["status"] != "complete":
                continue
            left = positions[str(record["node_i"])]
            right = positions[str(record["node_j"])]
            values[left, right] = values[right, left] = 0.0
        for record in self.edges.to_dict(orient="records"):
            if record["status"] != "complete" or pd.isna(record["display_magnitude_nats"]):
                continue
            left = positions[str(record["node_i"])]
            right = positions[str(record["node_j"])]
            value = float(record["display_magnitude_nats"])
            values[left, right] = values[right, left] = value
        matrix = pd.DataFrame(values, index=self.node_order, columns=self.node_order)
        matrix.index.name = "node"
        return matrix

    def plot(
        self,
        kind: str = "network",
        *,
        ax: Any = None,
        order: list[str] | tuple[str, ...] | None = None,
        fill: float | None = np.nan,
    ) -> Any:
        """Build and return a matplotlib figure without displaying it."""

        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection

        if kind not in {"network", "matrix"}:
            raise ValueError("kind must be 'network' or 'matrix'")
        if ax is None:
            _, ax = plt.subplots()
        figure = ax.figure
        if kind == "matrix":
            matrix = self.to_matrix(fill=fill)
            cmap = plt.get_cmap("viridis").copy()
            cmap.set_bad("#d9d9d9")
            image = ax.imshow(np.ma.masked_invalid(matrix.to_numpy()), cmap=cmap)
            ax.set_xticks(range(len(self.node_order)), self.node_order, rotation=90)
            ax.set_yticks(range(len(self.node_order)), self.node_order)
            figure.colorbar(image, ax=ax, label="display magnitude (nats)")
            return figure

        requested_order = tuple(order) if order is not None else self.node_order
        if set(requested_order) != set(self.node_order) or len(requested_order) != len(self.node_order):
            raise ValueError("plot order must contain each fit node exactly once")
        angles = np.linspace(0.0, 2.0 * np.pi, len(requested_order), endpoint=False)
        coordinates = {
            name: np.asarray([np.cos(angle), np.sin(angle)])
            for name, angle in zip(requested_order, angles)
        }
        complete = self.all_pairs.loc[self.all_pairs["status"] == "complete"]
        maximum = pd.to_numeric(complete["display_magnitude_nats"], errors="coerce").max()
        maximum = float(maximum) if pd.notna(maximum) and maximum > 0 else 1.0
        for record in self.edges.to_dict(orient="records"):
            start = coordinates[str(record["node_i"])]
            end = coordinates[str(record["node_j"])]
            magnitude = float(record["display_magnitude_nats"])
            width = 0.5 + 6.0 * magnitude / maximum
            alpha = 1.0
            if "stability" in record and pd.notna(record["stability"]):
                alpha = 0.25 + 0.75 * float(record["stability"])
            ax.add_collection(
                LineCollection(
                    [[start, end]],
                    linewidths=[width],
                    colors=["black"],
                    alpha=alpha,
                )
            )
        points = np.asarray([coordinates[name] for name in requested_order])
        ax.scatter(points[:, 0], points[:, 1], s=40, color="white", edgecolor="black", zorder=3)
        for name, point in coordinates.items():
            angle = np.degrees(np.arctan2(point[1], point[0]))
            ax.text(
                point[0] * 1.12,
                point[1] * 1.12,
                name,
                rotation=angle,
                ha="center",
                va="center",
            )
        ax.set_aspect("equal")
        ax.set_axis_off()
        return figure

    def methods_text(self) -> str:
        """Return the deterministic Task 6 methods and limitations text."""

        metadata = self.settings.get("metadata", {})
        return (
            "CIN views summarize all-other-variable conditional predictive information "
            "from the fitted model in nats per observation. The model uses linear and "
            "at most two curvature terms for continuous variables and an LSPC-type "
            "probability model for categorical variables, conditioning on all other "
            "included variables. Pair weights are the undirected average of the two "
            "prediction orientations. This view applies the recorded complete-pair, "
            "positive-weight, threshold, agreement, stability, and presentation filters. "
            f"Fit ID: {self.fit_id}."
            f" Metadata: {_plain(metadata)}."
        )

    def save(self, directory: str | Path, *, plots: bool = True) -> None:
        """Write the filtered edge table, matrix, metadata, methods, and plots."""

        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        self.edges.to_csv(output / "edges.csv", index=False, float_format="%.17g")
        self.to_edge_list().to_csv(output / "edge_list.csv", index=False, float_format="%.17g")
        self.to_matrix().to_csv(output / "matrix.csv", float_format="%.17g")
        view_metadata = {
            "fit_id": self.fit_id,
            "label": self.label,
            "description": self.description,
            "settings": self.settings,
            "stability_meta": self.stability_meta,
            "node_order": list(self.node_order),
        }
        with (output / "view.json").open("w", encoding="utf-8") as handle:
            json.dump(_plain(view_metadata), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        (output / "methods.txt").write_text(self.methods_text() + "\n", encoding="utf-8")
        if plots:
            import matplotlib.pyplot as plt

            for kind, filename in (("network", "network.png"), ("matrix", "matrix.png")):
                figure = self.plot(kind)
                figure.savefig(output / filename, dpi=150, bbox_inches="tight")
                plt.close(figure)


def _validate_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def make_view(
    fit: NetworkFit | None = None,
    *,
    min_effect: float = 0.0,
    require_both_positive: bool = False,
    stability: Any = None,
    min_stability: float | None = None,
    max_edges: int | None = None,
    top_fraction: float | None = None,
    name: str | None = None,
) -> NetworkView:
    """Create a pure filtered view without refitting or changing ``fit``."""

    if fit is None:
        raise NotImplementedError("make_view requires a NetworkFit")
    if not isinstance(fit, NetworkFit):
        raise ValueError("fit must be a NetworkFit")
    min_effect = _validate_number(min_effect, "min_effect")
    if min_effect < 0:
        raise ValueError("min_effect must be >= 0")
    if not isinstance(require_both_positive, bool):
        raise ValueError("require_both_positive must be a boolean")
    if min_stability is not None:
        min_stability = _validate_number(min_stability, "min_stability")
        if not 0 <= min_stability <= 1:
            raise ValueError("min_stability must be in [0, 1]")
        if stability is None:
            raise ValueError("min_stability requires a stability result")
    if max_edges is not None:
        if isinstance(max_edges, bool) or not isinstance(max_edges, int) or max_edges < 1:
            raise ValueError("max_edges must be a positive integer")
    if top_fraction is not None:
        top_fraction = _validate_number(top_fraction, "top_fraction")
        if not 0 < top_fraction <= 1:
            raise ValueError("top_fraction must be in (0, 1]")
    if max_edges is not None and top_fraction is not None:
        raise ValueError("max_edges and top_fraction are mutually exclusive")

    node_order = _fit_nodes(fit)
    fit_id = fit.metadata.get("fit_id")
    if not isinstance(fit_id, str) or not fit_id:
        raise ValueError("fit metadata must contain fit_id")
    all_pairs = fit.pairs.copy(deep=True)
    numeric_weight = pd.to_numeric(all_pairs["weight_nats_raw"], errors="coerce")
    mask = (
        all_pairs["status"].eq("complete")
        & numeric_weight.gt(0)
        & numeric_weight.ge(min_effect)
    )
    edges = all_pairs.loc[mask].copy()

    if require_both_positive:
        edges = edges.loc[
            edges["gain_i_to_j"].gt(0) & edges["gain_j_to_i"].gt(0)
        ].copy()

    stability_meta = None
    stability_fit = _stability_fit_id(stability) if stability is not None else None
    if min_stability is not None:
        if stability_fit != fit_id:
            raise ValueError("stability result belongs to another fit")
        result = _stability_for_rule(
            stability,
            min_effect=min_effect,
            require_both_positive=require_both_positive,
        )
        table = _canonical_stability(_stability_table(result), node_order)
        edges = edges.merge(table, on=["node_i", "node_j"], how="left", sort=False)
        edges = edges.loc[pd.to_numeric(edges["stability"], errors="coerce").ge(min_stability)].copy()
        stability_meta = _stability_metadata(stability)

    edges = edges.sort_values(
        ["weight_nats_raw", "node_i", "node_j"],
        ascending=[False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    passing_count = len(edges)
    limit = None
    if max_edges is not None:
        limit = max_edges
    elif top_fraction is not None:
        limit = ceil(top_fraction * passing_count)
    if limit is not None:
        edges = edges.iloc[:limit].copy()
    edges_cut = passing_count - len(edges)

    settings = {
        "min_effect": min_effect,
        "require_both_positive": require_both_positive,
        "min_stability": min_stability,
        "stability_fit_id": stability_fit,
        "max_edges": max_edges,
        "top_fraction": top_fraction,
        "presentation_limit": limit is not None,
        "edges_passing": passing_count,
        "edges_cut": edges_cut,
        "metadata": _plain(fit.metadata),
    }
    labels: list[str] = []
    if min_effect > 0:
        labels.append("Effect-filtered")
    if require_both_positive:
        labels.append("Agreement-filtered")
    if min_stability is not None:
        labels.append("Stable subset")
    label = name or " + ".join(labels) or "Landscape"
    if limit is not None and "+ Presentation limit" not in label:
        label = f"{label} + Presentation limit"
    description_parts = ["complete pairs with positive raw weight"]
    if min_effect > 0:
        description_parts.append(f"raw weight at least {min_effect:g} nats")
    if require_both_positive:
        description_parts.append("both directional gains positive")
    if min_stability is not None:
        description_parts.append(f"stability at least {min_stability:g}")
    if limit is not None:
        description_parts.append(f"the top {len(edges)} of {passing_count} passing edges")
    description = "This view contains " + ", ".join(description_parts) + "."
    if stability_meta is not None:
        description += " Stability denotes reproducibility under the recorded resampling rule."
    return NetworkView(
        edges=edges,
        settings=settings,
        fit_id=fit_id,
        stability_meta=stability_meta,
        node_order=node_order,
        label=label,
        description=description,
        all_pairs=all_pairs,
    )
