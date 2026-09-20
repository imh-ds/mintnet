import pytest

from mintnet.experiments.stage1j_fit import FittedForm, fit_candidate_forms, select_form


def test_fit_candidate_forms_returns_all_four_named_forms():
    forms = fit_candidate_forms()

    names = {form.name for form in forms}
    assert names == {"linear_n", "linear_log_n", "power_law", "inverse_sqrt"}
    for form in forms:
        assert 0.0 <= form.r_squared <= 1.0


def test_linear_log_n_fits_the_known_points_best():
    """On the six frozen D-008/D-009/D-010 points, log(N) fits far better than linear N."""
    forms = {form.name: form for form in fit_candidate_forms()}

    assert forms["linear_log_n"].r_squared > forms["linear_n"].r_squared
    assert forms["linear_log_n"].r_squared > 0.99


def test_select_form_picks_the_outright_best_when_not_near_tied():
    forms = fit_candidate_forms()
    selected = select_form(forms)
    assert selected.name == "linear_log_n"


def test_select_form_prefers_inverse_sqrt_when_near_tied():
    tied_forms = (
        FittedForm("linear_n", (0.0, 0.0), 0.990, 2),
        FittedForm("linear_log_n", (0.0, 0.0), 0.993, 2),
        FittedForm("power_law", (0.0, 0.0), 0.991, 2),
        FittedForm("inverse_sqrt", (0.0, 0.0), 0.989, 2),
    )
    selected = select_form(tied_forms)
    assert selected.name == "inverse_sqrt"


def test_select_form_falls_back_to_simplest_when_no_inverse_sqrt_present():
    tied_forms = (
        FittedForm("linear_n", (0.0, 0.0), 0.993, 2),
        FittedForm("power_law", (0.0, 0.0), 0.991, 3),
    )
    selected = select_form(tied_forms)
    assert selected.name == "linear_n"


@pytest.mark.parametrize(
    ("name", "parameters", "n", "expected"),
    [
        ("linear_n", (0.1, -0.0001), 1000, 0.1 - 0.0001 * 1000),
        ("power_law", (5.0, -0.5), 2500, 5.0 * 2500**-0.5),
    ],
)
def test_predict_matches_the_named_functional_form(name, parameters, n, expected):
    form = FittedForm(name, parameters, r_squared=1.0, n_parameters=2)
    assert form.predict(n) == pytest.approx(expected)
