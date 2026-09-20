import pytest

from mintnet.experiments.stage6c import resolve_k_perm
from mintnet.experiments.stage6c_reporting import wilson_ci


def test_resolve_k_perm_fixed_labels() -> None:
    assert resolve_k_perm("kperm3", 750) == 3
    assert resolve_k_perm("kperm5", 750) == 5
    assert resolve_k_perm("kperm10", 750) == 10
    assert resolve_k_perm("kperm20", 750) == 20


def test_resolve_k_perm_adaptive_scales_with_n_and_is_clipped() -> None:
    assert resolve_k_perm("adaptive", 150) == 8  # round(0.05*150)=8, clip[3,20]
    assert resolve_k_perm("adaptive", 300) == 15  # round(0.05*300)=15
    assert resolve_k_perm("adaptive", 750) == 20  # round(0.05*750)=38, clipped to 20
    assert resolve_k_perm("adaptive", 20) == 3  # round(0.05*20)=1, clipped up to 3


def test_resolve_k_perm_unknown_label_raises() -> None:
    with pytest.raises(ValueError):
        resolve_k_perm("bogus", 300)


def test_wilson_ci_symmetric_around_half_at_n_large() -> None:
    low, high = wilson_ci(500, 1000)
    assert low < 0.5 < high
    assert high - 0.5 == pytest.approx(0.5 - low, abs=1e-9)


def test_wilson_ci_zero_successes_has_nonzero_upper_bound() -> None:
    low, high = wilson_ci(0, 50)
    assert low == pytest.approx(0.0, abs=1e-9)
    assert high > 0.0


def test_wilson_ci_all_successes_has_upper_bound_at_one() -> None:
    low, high = wilson_ci(50, 50)
    assert high == 1.0
    assert low < 1.0


def test_wilson_ci_empty_total_is_nan() -> None:
    low, high = wilson_ci(0, 0)
    assert low != low  # NaN
    assert high != high
