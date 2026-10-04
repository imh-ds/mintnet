# CIN statistical panel

Rows emitted: 97; pair sidecar rows audited: 2716.
Development-selected display delta: None
Counts are preserved behind every aggregate; incomplete and failed methods remain visible.
Monte Carlo standard errors are descriptive and do not establish tail probabilities or FDR control.
Oracle CMI, regression, null, stability, and variance-only/XOR sections are descriptive or unsupported where no gate applies.
This panel does not establish causal effects or broad recovery claims beyond named validation scopes.

## Metric summaries

Mean, Monte Carlo standard error (MCSE), and contributing row count are shown. An unavailable value has no contributing finite observations; it is not zero.

| Case | Phase | Method | Metric | Mean | MCSE | n | Availability |
|---|---|---|---|---:|---:|---:|---|
| F | validation | cin | ap | 0.619521 | 0.0144491 | 97 | available |
| F | validation | cin | prevalence | 0.357143 | 0 | 97 | available |
| F | validation | cin | ap_minus_prevalence | 0.262378 | 0.0144491 | 97 | available |
| F | validation | cin | strong_edge_recall | 0.680824 | 0.0342584 | 93 | available |
| F | validation | cin | categorical_excess_loss | -0.00115086 | 0.000963943 | 97 | available |
| F | validation | cin | n_failed_pairs | 0 | 0 | 97 | available |
| F | validation | cin | elapsed_seconds | 0.252025 | 0.00202179 | 97 | available |
| F | validation | cin | orientation_gap_q95 | 0.016183 | 0.000926775 | 97 | available |
| F | validation | cin | generator_attempts | 157.082 | 16.6436 | 97 | available |
| F | validation | cin | point_fit_seconds | 0.238636 | 0.00191988 | 97 | available |
| F | validation | cin | peak_rss_mb | 159.418 | 0.027606 | 97 | available |
| F | validation | cin | n_pairs_complete | 28 | 0 | 97 | available |
| F | validation | cin | n_pairs_total | 28 | 0 | 97 | available |
| F | validation | cin | n_true_edges | 10 | 0 | 97 | available |
| F | validation | cin | n_strong_edges | 2.73196 | 0.126508 | 97 | available |
| F | validation | cin | strong_edge_set_available | 1 | 0 | 97 | available |
| F | validation | cin | n_nonempty_delta_views | 3.01031 | 0.0860737 | 97 | available |
| F | validation | cin | n_nonempty_agreement_views | 2.97938 | 0.0891196 | 97 | available |
| F | validation | cin | delta_0_strong_recall | 0.680824 | 0.0342584 | 93 | available |
| F | validation | cin | delta_005_strong_recall | 0.362724 | 0.0327798 | 93 | available |
| F | validation | cin | delta_01_strong_recall | 0.168638 | 0.0245536 | 93 | available |
| F | validation | cin | delta_02_strong_recall | 0.0587814 | 0.0149206 | 93 | available |
| F | validation | cin | oracle_cmi_mae | 0.00891608 | 0.000275625 | 97 | available |
| F | validation | cin | oracle_cmi_bias | -0.00661754 | 0.000319706 | 97 | available |
| F | validation | cin | oracle_cmi_mae_true | 0.00891608 | 0.000275625 | 97 | available |
| F | validation | cin | oracle_cmi_bias_true | -0.00661754 | 0.000319706 | 97 | available |
| F | validation | cin | oracle_cmi_mae_all | 0.00519144 | 0.000191201 | 97 | available |
| F | validation | cin | oracle_cmi_bias_all | -0.00308681 | 0.000146405 | 97 | available |
| F | validation | cin | n_categorical_targets | 8 | 0 | 97 | available |
| F | validation | cin | positive_weight_q50 | 0.00272891 | 0.000199974 | 97 | available |
| F | validation | cin | positive_weight_q90 | 0.0105761 | 0.000591253 | 97 | available |
| F | validation | cin | positive_weight_q95 | 0.0141309 | 0.00084004 | 97 | available |
| F | validation | cin | positive_weight_q99 | 0.0175195 | 0.00114585 | 97 | available |
| F | validation | cin | positive_weight_max | 0.0183667 | 0.00123348 | 97 | available |
| F | validation | cin | tie_fraction | 0 | 0 | 97 | available |
| F | validation | cin | orientation_gap_q50 | 0.00218917 | 0.000192737 | 97 | available |
| F | validation | cin | orientation_gap_q90 | 0.0116567 | 0.000702106 | 97 | available |
| F | validation | cin | orientation_gap_q99 | 0.0227431 | 0.00125907 | 97 | available |
| F | validation | cin | orientation_gap_max | 0.0246799 | 0.00138947 | 97 | available |
| F | validation | cin | variance_floor_hits | 0 | 0 | 97 | available |
| F | validation | cin | variance_floor_observations | 8 | 0 | 97 | available |
| F | validation | cin | variance_floor_hit_rate | 0 | 0 | 97 | available |
| F | validation | cin | probability_clipped_fraction | 0.00358677 | 0.000513499 | 97 | available |
| F | validation | cin | zero_sum_fallbacks | 0 | 0 | 97 | available |
| F | validation | cin | minimum_probability | 0.00819051 | 0.00171133 | 97 | available |
| F | validation | cin | delta_0_displayed_count | 12.4021 | 0.274824 | 97 | available |
| F | validation | cin | delta_0_displayed_fraction | 0.442931 | 0.00981515 | 97 | available |
| F | validation | cin | delta_0_precision | 0.482854 | 0.0121817 | 97 | available |
| F | validation | cin | delta_0_recall | 0.598969 | 0.0192478 | 97 | available |
| F | validation | cin | delta_0_empty | 0 | 0 | 97 | available |
| F | validation | cin | delta_005_displayed_count | 3.62887 | 0.1844 | 97 | available |
| F | validation | cin | delta_005_displayed_fraction | 0.129602 | 0.00658571 | 97 | available |
| F | validation | cin | delta_005_precision | 0.748654 | 0.0276635 | 92 | available |
| F | validation | cin | delta_005_recall | 0.26701 | 0.0147809 | 97 | available |
| F | validation | cin | delta_005_empty | 0.0515464 | 0.0225669 | 97 | available |
| F | validation | cin | delta_01_displayed_count | 1.57732 | 0.148615 | 97 | available |
| F | validation | cin | delta_01_displayed_fraction | 0.0563328 | 0.0053077 | 97 | available |
| F | validation | cin | delta_01_precision | 0.769635 | 0.0392263 | 73 | available |
| F | validation | cin | delta_01_recall | 0.116495 | 0.0115098 | 97 | available |
| F | validation | cin | delta_01_empty | 0.247423 | 0.0440413 | 97 | available |
| F | validation | cin | delta_02_displayed_count | 0.381443 | 0.0694284 | 97 | available |
| F | validation | cin | delta_02_displayed_fraction | 0.013623 | 0.00247958 | 97 | available |
| F | validation | cin | delta_02_precision | 0.811111 | 0.0709061 | 30 | available |
| F | validation | cin | delta_02_recall | 0.0309278 | 0.00627971 | 97 | available |
| F | validation | cin | delta_02_empty | 0.690722 | 0.0471727 | 97 | available |
| F | validation | cin | agreement_delta_0_displayed_count | 10.0722 | 0.271912 | 97 | available |
| F | validation | cin | agreement_delta_0_displayed_fraction | 0.35972 | 0.00971115 | 97 | available |
| F | validation | cin | agreement_delta_0_precision | 0.503679 | 0.0149973 | 97 | available |
| F | validation | cin | agreement_delta_0_recall | 0.509278 | 0.0197211 | 97 | available |
| F | validation | cin | agreement_delta_0_empty | 0 | 0 | 97 | available |
| F | validation | cin | agreement_delta_005_displayed_count | 3.35052 | 0.178314 | 97 | available |
| F | validation | cin | agreement_delta_005_displayed_fraction | 0.119661 | 0.00636835 | 97 | available |
| F | validation | cin | agreement_delta_005_precision | 0.763475 | 0.0278587 | 91 | available |
| F | validation | cin | agreement_delta_005_recall | 0.250515 | 0.0143684 | 97 | available |
| F | validation | cin | agreement_delta_005_empty | 0.0618557 | 0.0245861 | 97 | available |
| F | validation | cin | agreement_delta_01_displayed_count | 1.48454 | 0.142927 | 97 | available |
| F | validation | cin | agreement_delta_01_displayed_fraction | 0.0530191 | 0.00510454 | 97 | available |
| F | validation | cin | agreement_delta_01_precision | 0.770188 | 0.0398843 | 71 | available |
| F | validation | cin | agreement_delta_01_recall | 0.110309 | 0.0110143 | 97 | available |
| F | validation | cin | agreement_delta_01_empty | 0.268041 | 0.0452073 | 97 | available |
| F | validation | cin | agreement_delta_02_displayed_count | 0.381443 | 0.0694284 | 97 | available |
| F | validation | cin | agreement_delta_02_displayed_fraction | 0.013623 | 0.00247958 | 97 | available |
| F | validation | cin | agreement_delta_02_precision | 0.811111 | 0.0709061 | 30 | available |
| F | validation | cin | agreement_delta_02_recall | 0.0309278 | 0.00627971 | 97 | available |
| F | validation | cin | agreement_delta_02_empty | 0.690722 | 0.0471727 | 97 | available |
| F | validation | cin | stability_repeats_requested | unavailable | unavailable | 0 | unavailable |
| F | validation | cin | stability_repeat_seeds_json | unavailable | unavailable | 0 | unavailable |
| F | validation | cin | stability_completed_repeat_ids_json | unavailable | unavailable | 0 | unavailable |
| F | validation | cin | stability_node_order_json | unavailable | unavailable | 0 | unavailable |
| F | validation | cin | stability_status | unavailable | unavailable | 0 | unavailable |

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
| complete | 97 |
| stability: not_requested | 97 |
