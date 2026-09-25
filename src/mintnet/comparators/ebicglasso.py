"""Native Python re-implementation of `qgraph::EBICglasso`'s own
selection procedure -- graphical lasso fit across a log-spaced
regularization path, with the path's penalty selected by minimizing the
extended BIC (Foygel & Drton, 2010). See docs/stage5a_charter.md.

This is a from-specification re-implementation, not a call into the R
package, and is not asserted to reproduce its numerical output
bit-for-bit -- an implementation choice disclosed in the charter.

Implementation-time correction, made before any evidence exists: the
charter's own prose described `lambda_max` as "the smallest penalty
producing a fully dense fit." That is backwards. In the standard glasso
parameterization, `lambda_max` (the largest off-diagonal magnitude of
the empirical covariance) is the smallest penalty at which the fit is
fully *sparse* (empty graph); the path grows denser as `lambda` shrinks
toward `lambda_max * lambda_min_ratio`. The code below uses the correct
direction; only the charter's descriptive sentence was wrong, not the
grid density, `gamma`, or selection rule it specifies.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from sklearn.covariance import graphical_lasso
from sklearn.exceptions import ConvergenceWarning


class EBICglassoFailure(RuntimeError):
    """Raised when no point on the EBICglasso path converges."""

    def __init__(self, message: str, *, attempted_points: int, successful_points: int) -> None:
        super().__init__(message)
        self.attempted_points = attempted_points
        self.successful_points = successful_points


@dataclass(frozen=True)
class EBICglassoResult:
    adjacency: np.ndarray
    precision: np.ndarray
    selected_lambda: float
    selected_index: int
    ebic_by_lambda: tuple[float, ...]
    lambda_grid: tuple[float, ...]
    n_edges: int
    converged: bool
    successful_path_points: int


def _lambda_max(empirical_covariance: np.ndarray) -> float:
    p = empirical_covariance.shape[0]
    off_diagonal = np.abs(empirical_covariance[~np.eye(p, dtype=bool)])
    return float(off_diagonal.max()) if off_diagonal.size else 1.0


def _lambda_grid(empirical_covariance: np.ndarray, n_lambda: int, lambda_min_ratio: float) -> np.ndarray:
    lambda_max = _lambda_max(empirical_covariance)
    lambda_min = lambda_max * lambda_min_ratio
    return np.geomspace(lambda_max, lambda_min, n_lambda)


def _extended_bic(precision: np.ndarray, empirical_covariance: np.ndarray, n: int, gamma: float) -> float:
    p = precision.shape[0]
    sign, log_det = np.linalg.slogdet(precision)
    if sign <= 0:
        return float("inf")
    log_likelihood = 0.5 * n * (log_det - np.trace(empirical_covariance @ precision))
    off_diagonal = precision[np.triu_indices(p, k=1)]
    n_edges = int(np.sum(np.abs(off_diagonal) > 1e-8))
    return -2.0 * log_likelihood + n_edges * np.log(n) + 4.0 * gamma * n_edges * np.log(p)


def fit_ebicglasso(
    data: np.ndarray,
    *,
    gamma: float = 0.5,
    n_lambda: int = 100,
    lambda_min_ratio: float = 0.01,
    edge_tolerance: float = 1e-6,
    max_iter: int = 500,
) -> EBICglassoResult:
    """Fit EBICglasso: graphical lasso over a log-spaced `lambda` path,
    penalty chosen by minimizing the extended BIC. `gamma=0.5` is
    `qgraph`'s own package default, used here as a fixed literature
    convention, not searched (docs/stage5a_charter.md's own
    fair-comparison rule)."""
    n, p = data.shape
    empirical_covariance = np.cov(data, rowvar=False)
    grid = _lambda_grid(empirical_covariance, n_lambda, lambda_min_ratio)

    best_ebic = float("inf")
    best_index = -1
    best_precision: np.ndarray | None = None
    ebic_values: list[float] = []
    successful_path_points = 0
    for index, lam in enumerate(grid):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                _, precision = graphical_lasso(empirical_covariance, alpha=float(lam), max_iter=max_iter)
        except (ConvergenceWarning, Exception):
            ebic_values.append(float("inf"))
            continue
        successful_path_points += 1
        ebic = _extended_bic(precision, empirical_covariance, n, gamma)
        ebic_values.append(ebic)
        if ebic < best_ebic:
            best_ebic = ebic
            best_index = index
            best_precision = precision

    if best_precision is None:
        raise EBICglassoFailure(
            "no lambda point converged on the EBICglasso path",
            attempted_points=len(grid),
            successful_points=successful_path_points,
        )

    adjacency = np.abs(best_precision) > edge_tolerance
    np.fill_diagonal(adjacency, False)
    n_edges = int(adjacency[np.triu_indices(p, k=1)].sum())

    return EBICglassoResult(
        adjacency=adjacency,
        precision=best_precision,
        selected_lambda=float(grid[best_index]),
        selected_index=best_index,
        ebic_by_lambda=tuple(ebic_values),
        lambda_grid=tuple(float(v) for v in grid),
        n_edges=n_edges,
        converged=True,
        successful_path_points=successful_path_points,
    )
