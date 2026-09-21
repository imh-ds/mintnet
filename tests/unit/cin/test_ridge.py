from __future__ import annotations

import numpy as np
import pytest
from scipy import linalg
from sklearn.linear_model import Ridge

import mintnet.cin.ridge as ridge
from mintnet.cin import CINConfig


def _config() -> CINConfig:
    return CINConfig(seed=23)


def _data(*, m: int = 24, q: int = 8, t: int = 3) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20260920 + m + q + t)
    B = rng.normal(size=(m, q))
    T = rng.normal(size=(m, t))
    B -= np.mean(B, axis=0)
    T -= np.mean(T, axis=0)
    return np.ascontiguousarray(B), np.ascontiguousarray(T)


def _columns(start_stop: tuple[int, int]) -> np.ndarray:
    start, stop = start_stop
    return np.arange(start, stop, dtype=np.intp)


def _expected_full_coefficients(
    B: np.ndarray,
    T: np.ndarray,
    lam: float,
    omit_cols: np.ndarray,
) -> np.ndarray:
    keep = np.setdiff1d(np.arange(B.shape[1]), omit_cols)
    expected = np.zeros((B.shape[1], T.shape[1]), dtype=np.float64)
    if keep.size:
        expected[keep] = ridge.direct_restricted_ridge(B, T, lam, keep, B.shape[0])
    return expected


def test_ridge_solution_matches_sklearn_including_q_greater_than_m() -> None:
    B, T = _data(m=7, q=12, t=4)
    lam = 0.17

    solution = ridge.RidgeSolution(B, T, lam, _config())
    expected = Ridge(alpha=B.shape[0] * lam, fit_intercept=False).fit(B, T).coef_.T

    np.testing.assert_allclose(solution.beta, expected, rtol=1e-8, atol=1e-10)
    assert solution.m == 7
    assert solution.q == 12
    assert solution.t == 4


def test_omission_coefficients_match_direct_restricted_ridge_for_many_sets() -> None:
    B, T = _data(m=28, q=20, t=4)
    lam = 0.03
    solution = ridge.RidgeSolution(B, T, lam, _config())
    workspace = ridge.OmissionWorkspace(solution, {"train": B})
    response_cols = np.array([0, 2], dtype=np.intp)

    omission_sets = [
        np.array([0]),
        np.array([0, 3, 7]),
        np.arange(6, dtype=np.intp),
        np.arange(19, dtype=np.intp),
        np.arange(20, dtype=np.intp),
    ]
    for omit_cols in omission_sets:
        expected = _expected_full_coefficients(B, T, lam, omit_cols)[:, response_cols]
        actual = workspace.omitted_coefficients(omit_cols, response_cols)
        np.testing.assert_allclose(actual, expected, rtol=1e-8, atol=1e-10)


def test_full_and_omitted_predictions_match_direct_fits_on_train_and_eval() -> None:
    B, T = _data(m=26, q=9, t=3)
    eval_matrix, _ = _data(m=11, q=9, t=3)
    lam = 0.11
    solution = ridge.RidgeSolution(B, T, lam, _config())
    workspace = ridge.OmissionWorkspace(solution, {"train": B, "eval": eval_matrix})
    response_cols = np.array([1, 2], dtype=np.intp)

    np.testing.assert_allclose(
        workspace.predict_full("train", response_cols),
        B @ solution.beta[:, response_cols],
        rtol=1e-10,
        atol=1e-12,
    )
    for omit_cols in [np.array([0]), np.array([2, 4, 6]), np.arange(9)]:
        keep = np.setdiff1d(np.arange(B.shape[1]), omit_cols)
        expected_train = np.zeros((B.shape[0], response_cols.size))
        expected_eval = np.zeros((eval_matrix.shape[0], response_cols.size))
        if keep.size:
            beta_keep = ridge.direct_restricted_ridge(B, T, lam, keep, B.shape[0])
            expected_train = B[:, keep] @ beta_keep[:, response_cols]
            expected_eval = eval_matrix[:, keep] @ beta_keep[:, response_cols]

        actual_train, train_status = workspace.predict_omit("train", omit_cols, response_cols)
        actual_eval, eval_status = workspace.predict_omit("eval", omit_cols, response_cols)
        assert train_status == "ok"
        assert eval_status == "ok"
        np.testing.assert_allclose(actual_train, expected_train, rtol=1e-8, atol=1e-10)
        np.testing.assert_allclose(actual_eval, expected_eval, rtol=1e-8, atol=1e-10)


def test_intercept_only_and_zero_width_omissions_are_degenerate_but_finite() -> None:
    B, T = _data(m=12, q=4, t=2)
    solution = ridge.RidgeSolution(B, T, 0.2, _config())
    workspace = ridge.OmissionWorkspace(solution, {"train": B})
    response_cols = np.array([0, 1], dtype=np.intp)

    full = workspace.predict_full("train", response_cols)
    unchanged, status = workspace.predict_omit("train", np.empty(0, dtype=np.intp), response_cols)
    assert status == "degenerate"
    np.testing.assert_array_equal(unchanged, full)
    zero, status = workspace.predict_omit("train", np.arange(4), response_cols)
    assert status == "ok"
    np.testing.assert_allclose(zero, 0.0, atol=1e-12)

    empty_solution = ridge.RidgeSolution(np.empty((12, 0)), T, 0.2, _config())
    empty_workspace = ridge.OmissionWorkspace(empty_solution, {"train": np.empty((12, 0))})
    empty_prediction, empty_status = empty_workspace.predict_omit(
        "train", np.empty(0, dtype=np.intp), response_cols
    )
    assert empty_status == "degenerate"
    assert empty_prediction.shape == (12, 2)
    np.testing.assert_allclose(empty_prediction, 0.0, atol=1e-12)


def test_self_block_omission_prevents_target_leakage() -> None:
    rng = np.random.default_rng(2026)
    train_self = rng.normal(size=30)
    eval_self = rng.normal(size=12)
    B = np.column_stack((train_self, rng.normal(size=(30, 2))))
    E = np.column_stack((eval_self, rng.normal(size=(12, 2))))
    T = train_self[:, None]
    lam = 0.001
    solution = ridge.RidgeSolution(B, T, lam, _config())
    workspace = ridge.OmissionWorkspace(solution, {"eval": E})

    full = workspace.predict_full("eval", np.array([0]))
    reduced, status = workspace.predict_omit("eval", np.array([0]), np.array([0]))
    expected_beta = ridge.direct_restricted_ridge(B, T, lam, np.array([1, 2]), B.shape[0])
    expected = E[:, 1:] @ expected_beta

    assert np.sqrt(np.mean((full[:, 0] - eval_self) ** 2)) < 0.05
    assert status == "ok"
    np.testing.assert_allclose(reduced, expected, rtol=1e-8, atol=1e-10)
    assert np.sqrt(np.mean((reduced[:, 0] - eval_self) ** 2)) > 0.5


def test_collinear_and_all_level_blocks_remain_finite() -> None:
    rng = np.random.default_rng(2027)
    base = rng.normal(size=18)
    B = np.column_stack((base, base, np.ones(18), np.zeros(18)))
    T = np.column_stack((base + 0.1 * rng.normal(size=18), np.sin(base)))
    T -= np.mean(T, axis=0)
    solution = ridge.RidgeSolution(B, T, 0.5, _config())
    workspace = ridge.OmissionWorkspace(solution, {"train": B})
    prediction, status = workspace.predict_omit("train", np.array([0, 1]), np.array([0, 1]))

    assert status == "ok"
    assert np.isfinite(solution.beta).all()
    assert np.isfinite(prediction).all()


def test_fallback_is_logged_and_excessive_fallbacks_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    B, T = _data(m=16, q=5, t=2)
    solution = ridge.RidgeSolution(B, T, 0.2, _config())
    workspace = ridge.OmissionWorkspace(solution, {"train": B})
    original_cho_factor = ridge.cho_factor

    def fail_small(matrix: np.ndarray, *args: object, **kwargs: object):
        if matrix.shape[0] < B.shape[1]:
            raise linalg.LinAlgError("forced small-block failure")
        return original_cho_factor(matrix, *args, **kwargs)

    monkeypatch.setattr(ridge, "cho_factor", fail_small)
    prediction, status = workspace.predict_omit("train", np.array([0]), np.array([0]))
    expected_beta = ridge.direct_restricted_ridge(B, T, 0.2, np.arange(1, 5), B.shape[0])
    np.testing.assert_allclose(prediction[:, 0], B[:, 1:] @ expected_beta[:, 0], rtol=1e-8, atol=1e-10)
    assert status == "fallback"
    assert workspace.fallback_count == 1
    assert workspace.fallback_events == [("train", (0,), (0,))]
    with pytest.raises(ridge.RidgeNumericalFailure, match="fallback"):
        workspace.check_fallback_rate()


def test_large_factorization_is_shared_across_many_omissions(monkeypatch: pytest.MonkeyPatch) -> None:
    B, T = _data(m=30, q=10, t=4)
    E, _ = _data(m=9, q=10, t=4)
    original_cho_factor = ridge.cho_factor
    large_calls: list[tuple[int, ...]] = []

    def count_factor(matrix: np.ndarray, *args: object, **kwargs: object):
        if matrix.shape == (10, 10):
            large_calls.append(matrix.shape)
        return original_cho_factor(matrix, *args, **kwargs)

    monkeypatch.setattr(ridge, "cho_factor", count_factor)
    solution = ridge.RidgeSolution(B, T, 0.07, _config())
    workspace = ridge.OmissionWorkspace(solution, {"train": B, "eval": E})
    for name in ["train", "eval"]:
        for omit in [np.array([0]), np.array([1, 2]), np.array([4, 5, 6])]:
            prediction, status = workspace.predict_omit(name, omit, np.array([0, 2]))
            assert status == "ok"
            assert prediction.shape[1] == 2

    assert large_calls == [(10, 10)]


def test_h_is_symmetric_and_normal_residual_is_small() -> None:
    B, T = _data(m=25, q=7, t=3)
    solution = ridge.RidgeSolution(B, T, 0.13, _config())

    H_first = solution.H()
    H_second = solution.H()
    np.testing.assert_array_equal(H_first, H_second)
    np.testing.assert_allclose(H_first, H_first.T, rtol=0.0, atol=1e-12)
    assert solution.scaled_normal_residual() < 1e-10
