# CIN statistical panel

Rows emitted: 100; pair sidecar rows audited: 2744.
Development-selected display delta: None
Counts are preserved behind every aggregate; incomplete and failed methods remain visible.
Monte Carlo standard errors are descriptive and do not establish tail probabilities or FDR control.
Oracle CMI, regression, null, stability, and variance-only/XOR sections are descriptive or unsupported where no gate applies.
This panel does not establish causal effects or broad recovery claims beyond named validation scopes.

## Metric summaries

Mean, Monte Carlo standard error (MCSE), and contributing row count are shown. An unavailable value has no contributing finite observations; it is not zero.

| Case | Phase | Method | Metric | Mean | MCSE | n | Availability |
|---|---|---|---|---:|---:|---:|---|
| F | development | cin | ap | 0.621319 | 0.00937173 | 98 | available |
| F | development | cin | prevalence | 0.357143 | 5.6363e-18 | 98 | available |
| F | development | cin | ap_minus_prevalence | 0.264176 | 0.00937173 | 98 | available |
| F | development | cin | strong_edge_recall | 0.739184 | 0.0280986 | 94 | available |
| F | development | cin | categorical_excess_loss | -0.00166914 | 0.000848706 | 98 | available |
| F | development | cin | n_failed_pairs | 0 | 0 | 98 | available |
| F | development | cin | elapsed_seconds | 0.670475 | 0.0269239 | 98 | available |
| F | development | cin | orientation_gap_q95 | 0.0180997 | 0.00103327 | 98 | available |
| F | development | cin | generator_attempts | 138.98 | 12.3849 | 100 | available |
| F | development | cin | point_fit_seconds | 0.599582 | 0.026824 | 98 | available |
| F | development | cin | n_pairs_complete | 28 | 0 | 98 | available |
| F | development | cin | n_pairs_total | 27.44 | 0.393975 | 100 | available |
| F | development | cin | n_true_edges | 10 | 0 | 98 | available |
| F | development | cin | n_strong_edges | 2.63265 | 0.13005 | 98 | available |
| F | development | cin | n_nonempty_delta_views | 3.30612 | 0.0716611 | 98 | available |
| F | development | cin | n_nonempty_agreement_views | 3.30612 | 0.0716611 | 98 | available |
| F | development | cin | delta_0_strong_recall | 0.739184 | 0.0280986 | 94 | available |
| F | development | cin | delta_005_strong_recall | 0.393972 | 0.033617 | 94 | available |
| F | development | cin | delta_01_strong_recall | 0.236525 | 0.028558 | 94 | available |
| F | development | cin | delta_02_strong_recall | 0.101241 | 0.0201976 | 94 | available |
| F | development | cin | oracle_cmi_mae | 0.00930326 | 0.00027491 | 98 | available |
| F | development | cin | oracle_cmi_bias | -0.00590195 | 0.000321076 | 98 | available |
| F | development | cin | oracle_cmi_mae_true | 0.00930326 | 0.00027491 | 98 | available |
| F | development | cin | oracle_cmi_bias_true | -0.00590195 | 0.000321076 | 98 | available |
| F | development | cin | oracle_cmi_mae_all | 0.00558947 | 0.000189582 | 98 | available |
| F | development | cin | oracle_cmi_bias_all | -0.00305734 | 0.000160725 | 98 | available |
| F | development | cin | n_categorical_targets | 8 | 0 | 98 | available |
| F | development | cin | positive_weight_q50 | 0.00293064 | 0.000219717 | 98 | available |
| F | development | cin | positive_weight_q90 | 0.0115046 | 0.000619506 | 98 | available |
| F | development | cin | positive_weight_q95 | 0.0164715 | 0.000894606 | 98 | available |
| F | development | cin | positive_weight_q99 | 0.0215765 | 0.00143134 | 98 | available |
| F | development | cin | positive_weight_max | 0.0228527 | 0.00158041 | 98 | available |
| F | development | cin | tie_fraction | 0 | 0 | 98 | available |
| F | development | cin | orientation_gap_q50 | 0.00223935 | 0.000150597 | 98 | available |
| F | development | cin | orientation_gap_q90 | 0.0131145 | 0.000751515 | 98 | available |
| F | development | cin | orientation_gap_q99 | 0.0258571 | 0.00153546 | 98 | available |
| F | development | cin | orientation_gap_max | 0.0282033 | 0.00177373 | 98 | available |
| F | development | cin | variance_floor_hits | 0 | 0 | 98 | available |
| F | development | cin | variance_floor_observations | 8 | 0 | 98 | available |
| F | development | cin | variance_floor_hit_rate | 0 | 0 | 98 | available |
| F | development | cin | probability_clipped_fraction | 0.00392007 | 0.000427734 | 98 | available |
| F | development | cin | zero_sum_fallbacks | 0 | 0 | 98 | available |
| F | development | cin | minimum_probability | 0.00590669 | 0.00139663 | 98 | available |
| F | development | cin | delta_0_displayed_count | 12.2143 | 0.269905 | 98 | available |
| F | development | cin | delta_0_displayed_fraction | 0.436224 | 0.00963947 | 98 | available |
| F | development | cin | delta_0_precision | 0.496922 | 0.00867406 | 98 | available |
| F | development | cin | delta_0_recall | 0.60102 | 0.0148274 | 98 | available |
| F | development | cin | delta_005_displayed_count | 3.68367 | 0.203378 | 98 | available |
| F | development | cin | delta_005_displayed_fraction | 0.13156 | 0.00726351 | 98 | available |
| F | development | cin | delta_005_precision | 0.762277 | 0.0224602 | 98 | available |
| F | development | cin | delta_005_recall | 0.265306 | 0.0138446 | 98 | available |
| F | development | cin | delta_01_displayed_count | 1.91837 | 0.149107 | 98 | available |
| F | development | cin | delta_01_displayed_fraction | 0.0685131 | 0.00532526 | 98 | available |
| F | development | cin | delta_01_precision | 0.82123 | 0.0298505 | 84 | available |
| F | development | cin | delta_01_recall | 0.15 | 0.011165 | 98 | available |
| F | development | cin | delta_02_displayed_count | 0.612245 | 0.0828595 | 98 | available |
| F | development | cin | delta_02_displayed_fraction | 0.0218659 | 0.00295927 | 98 | available |
| F | development | cin | delta_02_precision | 0.882576 | 0.0407599 | 44 | available |
| F | development | cin | delta_02_recall | 0.0510204 | 0.00684118 | 98 | available |
| F | development | cin | agreement_delta_0_displayed_count | 9.92857 | 0.254251 | 98 | available |
| F | development | cin | agreement_delta_0_displayed_fraction | 0.354592 | 0.00908038 | 98 | available |
| F | development | cin | agreement_delta_0_precision | 0.526781 | 0.010073 | 98 | available |
| F | development | cin | agreement_delta_0_recall | 0.518367 | 0.0150283 | 98 | available |
| F | development | cin | agreement_delta_005_displayed_count | 3.46939 | 0.190895 | 98 | available |
| F | development | cin | agreement_delta_005_displayed_fraction | 0.123907 | 0.00681769 | 98 | available |
| F | development | cin | agreement_delta_005_precision | 0.773846 | 0.0227055 | 98 | available |
| F | development | cin | agreement_delta_005_recall | 0.254082 | 0.013228 | 98 | available |
| F | development | cin | agreement_delta_01_displayed_count | 1.87755 | 0.143786 | 98 | available |
| F | development | cin | agreement_delta_01_displayed_fraction | 0.0670554 | 0.00513521 | 98 | available |
| F | development | cin | agreement_delta_01_precision | 0.819643 | 0.0299222 | 84 | available |
| F | development | cin | agreement_delta_01_recall | 0.146939 | 0.0108743 | 98 | available |
| F | development | cin | agreement_delta_02_displayed_count | 0.612245 | 0.0828595 | 98 | available |
| F | development | cin | agreement_delta_02_displayed_fraction | 0.0218659 | 0.00295927 | 98 | available |
| F | development | cin | agreement_delta_02_precision | 0.882576 | 0.0407599 | 44 | available |
| F | development | cin | agreement_delta_02_recall | 0.0510204 | 0.00684118 | 98 | available |

## Stability descriptives

Stability is repeatability under the configured subsampling procedure, not an edge probability. Pair fractions use complete requested repeats only; incomplete repeats are kept unavailable.

| Metric | Mean | n pairs | Availability |
|---|---:|---:|---|
| stability_precision_at_0.1 | unavailable | 0 | unavailable |
| stability_recall_at_0.1 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.1 | unavailable | 0 | unavailable |
| stability_precision_at_0.2 | unavailable | 0 | unavailable |
| stability_recall_at_0.2 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.2 | unavailable | 0 | unavailable |
| stability_precision_at_0.3 | unavailable | 0 | unavailable |
| stability_recall_at_0.3 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.3 | unavailable | 0 | unavailable |
| stability_precision_at_0.4 | unavailable | 0 | unavailable |
| stability_recall_at_0.4 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.4 | unavailable | 0 | unavailable |
| stability_precision_at_0.5 | unavailable | 0 | unavailable |
| stability_recall_at_0.5 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.5 | unavailable | 0 | unavailable |
| stability_precision_at_0.6 | unavailable | 0 | unavailable |
| stability_recall_at_0.6 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.6 | unavailable | 0 | unavailable |
| stability_precision_at_0.7 | unavailable | 0 | unavailable |
| stability_recall_at_0.7 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.7 | unavailable | 0 | unavailable |
| stability_precision_at_0.8 | unavailable | 0 | unavailable |
| stability_recall_at_0.8 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.8 | unavailable | 0 | unavailable |
| stability_precision_at_0.9 | unavailable | 0 | unavailable |
| stability_recall_at_0.9 | unavailable | 0 | unavailable |
| stability_selected_count_at_0.9 | unavailable | 0 | unavailable |
| stability_precision_at_1.0 | unavailable | 0 | unavailable |
| stability_recall_at_1.0 | unavailable | 0 | unavailable |
| stability_selected_count_at_1.0 | unavailable | 0 | unavailable |

## Row and stability statuses

| Status | Rows |
|---|---:|
| complete | 98 |
| error | 2 |
| stability: not_requested | 100 |
