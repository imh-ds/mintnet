# CIN statistical panel

Rows emitted: 97; pair sidecar rows audited: 2520.
Development-selected display delta: None
Counts are preserved behind every aggregate; incomplete and failed methods remain visible.
Monte Carlo standard errors are descriptive and do not establish tail probabilities or FDR control.
Oracle CMI, regression, null, stability, and variance-only/XOR sections are descriptive or unsupported where no gate applies.
This panel does not establish causal effects or broad recovery claims beyond named validation scopes.

## Metric summaries

Mean, Monte Carlo standard error (MCSE), and contributing row count are shown. An unavailable value has no contributing finite observations; it is not zero.

| Case | Phase | Method | Metric | Mean | MCSE | n | Availability |
|---|---|---|---|---:|---:|---:|---|
| F | validation | cin | ap | 0.629692 | 0.0126033 | 90 | available |
| F | validation | cin | prevalence | 0.357143 | 5.88417e-18 | 90 | available |
| F | validation | cin | ap_minus_prevalence | 0.272549 | 0.0126033 | 90 | available |
| F | validation | cin | strong_edge_recall | 0.765476 | 0.0285759 | 84 | available |
| F | validation | cin | categorical_excess_loss | -0.00205679 | 0.00116308 | 90 | available |
| F | validation | cin | n_failed_pairs | 0 | 0 | 90 | available |
| F | validation | cin | elapsed_seconds | 0.171208 | 0.00785607 | 90 | available |
| F | validation | cin | orientation_gap_q95 | 0.01586 | 0.0011563 | 90 | available |
| F | validation | cin | generator_attempts | 153.639 | 14.8096 | 97 | available |
| F | validation | cin | point_fit_seconds | 0.160436 | 0.00766753 | 90 | available |
| F | validation | cin | peak_rss_mb | 159.636 | 0.0236365 | 90 | available |
| F | validation | cin | n_pairs_complete | 28 | 0 | 90 | available |
| F | validation | cin | n_pairs_total | 25.9794 | 0.739471 | 97 | available |
| F | validation | cin | n_true_edges | 10 | 0 | 90 | available |
| F | validation | cin | n_strong_edges | 2.52222 | 0.129561 | 90 | available |
| F | validation | cin | n_nonempty_delta_views | 3.17778 | 0.0859373 | 90 | available |
| F | validation | cin | n_nonempty_agreement_views | 3.17778 | 0.0859373 | 90 | available |
| F | validation | cin | delta_0_strong_recall | 0.765476 | 0.0285759 | 84 | available |
| F | validation | cin | delta_005_strong_recall | 0.430754 | 0.035234 | 84 | available |
| F | validation | cin | delta_01_strong_recall | 0.266468 | 0.0306424 | 84 | available |
| F | validation | cin | delta_02_strong_recall | 0.0876984 | 0.0199786 | 84 | available |
| F | validation | cin | oracle_cmi_mae | 0.00909514 | 0.000301448 | 90 | available |
| F | validation | cin | oracle_cmi_bias | -0.00591767 | 0.000368332 | 90 | available |
| F | validation | cin | oracle_cmi_mae_true | 0.00909514 | 0.000301448 | 90 | available |
| F | validation | cin | oracle_cmi_bias_true | -0.00591767 | 0.000368332 | 90 | available |
| F | validation | cin | oracle_cmi_mae_all | 0.00542284 | 0.000224018 | 90 | available |
| F | validation | cin | oracle_cmi_bias_all | -0.00300312 | 0.000232063 | 90 | available |
| F | validation | cin | n_categorical_targets | 8 | 0 | 90 | available |
| F | validation | cin | positive_weight_q50 | 0.00308491 | 0.000224428 | 90 | available |
| F | validation | cin | positive_weight_q90 | 0.0113908 | 0.000688462 | 90 | available |
| F | validation | cin | positive_weight_q95 | 0.0152735 | 0.000854714 | 90 | available |
| F | validation | cin | positive_weight_q99 | 0.0193898 | 0.00120684 | 90 | available |
| F | validation | cin | positive_weight_max | 0.0204189 | 0.00131476 | 90 | available |
| F | validation | cin | tie_fraction | 0 | 0 | 90 | available |
| F | validation | cin | orientation_gap_q50 | 0.00234389 | 0.000202912 | 90 | available |
| F | validation | cin | orientation_gap_q90 | 0.0113955 | 0.000865417 | 90 | available |
| F | validation | cin | orientation_gap_q99 | 0.0236385 | 0.00153345 | 90 | available |
| F | validation | cin | orientation_gap_max | 0.0259729 | 0.00171204 | 90 | available |
| F | validation | cin | variance_floor_hits | 0 | 0 | 90 | available |
| F | validation | cin | variance_floor_observations | 8 | 0 | 90 | available |
| F | validation | cin | variance_floor_hit_rate | 0 | 0 | 90 | available |
| F | validation | cin | probability_clipped_fraction | 0.0039213 | 0.000501156 | 90 | available |
| F | validation | cin | zero_sum_fallbacks | 0 | 0 | 90 | available |
| F | validation | cin | minimum_probability | 0.00668074 | 0.00147297 | 90 | available |
| F | validation | cin | delta_0_displayed_count | 12.4222 | 0.25429 | 90 | available |
| F | validation | cin | delta_0_displayed_fraction | 0.443651 | 0.0090818 | 90 | available |
| F | validation | cin | delta_0_precision | 0.49417 | 0.0111056 | 90 | available |
| F | validation | cin | delta_0_recall | 0.607778 | 0.0156609 | 90 | available |
| F | validation | cin | delta_005_displayed_count | 3.83333 | 0.22803 | 90 | available |
| F | validation | cin | delta_005_displayed_fraction | 0.136905 | 0.00814391 | 90 | available |
| F | validation | cin | delta_005_precision | 0.719663 | 0.0288521 | 89 | available |
| F | validation | cin | delta_005_recall | 0.274444 | 0.016464 | 90 | available |
| F | validation | cin | delta_01_displayed_count | 1.82222 | 0.165409 | 90 | available |
| F | validation | cin | delta_01_displayed_fraction | 0.0650794 | 0.00590748 | 90 | available |
| F | validation | cin | delta_01_precision | 0.886025 | 0.0244883 | 69 | available |
| F | validation | cin | delta_01_recall | 0.154444 | 0.0130457 | 90 | available |
| F | validation | cin | delta_02_displayed_count | 0.566667 | 0.0806497 | 90 | available |
| F | validation | cin | delta_02_displayed_fraction | 0.0202381 | 0.00288035 | 90 | available |
| F | validation | cin | delta_02_precision | 0.925439 | 0.0342555 | 38 | available |
| F | validation | cin | delta_02_recall | 0.0511111 | 0.00728319 | 90 | available |
| F | validation | cin | agreement_delta_0_displayed_count | 10.0667 | 0.279468 | 90 | available |
| F | validation | cin | agreement_delta_0_displayed_fraction | 0.359524 | 0.009981 | 90 | available |
| F | validation | cin | agreement_delta_0_precision | 0.513053 | 0.014861 | 90 | available |
| F | validation | cin | agreement_delta_0_recall | 0.517778 | 0.018934 | 90 | available |
| F | validation | cin | agreement_delta_005_displayed_count | 3.7 | 0.217493 | 90 | available |
| F | validation | cin | agreement_delta_005_displayed_fraction | 0.132143 | 0.00776762 | 90 | available |
| F | validation | cin | agreement_delta_005_precision | 0.718923 | 0.0297814 | 89 | available |
| F | validation | cin | agreement_delta_005_recall | 0.265556 | 0.0164337 | 90 | available |
| F | validation | cin | agreement_delta_01_displayed_count | 1.78889 | 0.16459 | 90 | available |
| F | validation | cin | agreement_delta_01_displayed_fraction | 0.0638889 | 0.0058782 | 90 | available |
| F | validation | cin | agreement_delta_01_precision | 0.884817 | 0.0246165 | 69 | available |
| F | validation | cin | agreement_delta_01_recall | 0.151111 | 0.0129577 | 90 | available |
| F | validation | cin | agreement_delta_02_displayed_count | 0.555556 | 0.0775903 | 90 | available |
| F | validation | cin | agreement_delta_02_displayed_fraction | 0.0198413 | 0.00277108 | 90 | available |
| F | validation | cin | agreement_delta_02_precision | 0.921053 | 0.0354122 | 38 | available |
| F | validation | cin | agreement_delta_02_recall | 0.05 | 0.00711068 | 90 | available |
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
| complete | 90 |
| error | 7 |
| stability: not_requested | 97 |
