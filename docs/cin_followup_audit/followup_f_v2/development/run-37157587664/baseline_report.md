# CIN statistical panel

Rows emitted: 20; pair sidecar rows audited: 560.
Development-selected display delta: None
Counts are preserved behind every aggregate; incomplete and failed methods remain visible.
Monte Carlo standard errors are descriptive and do not establish tail probabilities or FDR control.
Oracle CMI, regression, null, stability, and variance-only/XOR sections are descriptive or unsupported where no gate applies.
This panel does not establish causal effects or broad recovery claims beyond named validation scopes.

## Metric summaries

Mean, Monte Carlo standard error (MCSE), and contributing row count are shown. An unavailable value has no contributing finite observations; it is not zero.

| Case | Phase | Method | Metric | Mean | MCSE | n | Availability |
|---|---|---|---|---:|---:|---:|---|
| F | development | cin | ap | 0.660517 | 0.0279005 | 20 | available |
| F | development | cin | prevalence | 0.357143 | 1.27351e-17 | 20 | available |
| F | development | cin | ap_minus_prevalence | 0.303374 | 0.0279005 | 20 | available |
| F | development | cin | strong_edge_recall | 0.696667 | 0.0912919 | 20 | available |
| F | development | cin | categorical_excess_loss | -0.00357462 | 0.00199496 | 20 | available |
| F | development | cin | n_failed_pairs | 0 | 0 | 20 | available |
| F | development | cin | elapsed_seconds | 0.251656 | 0.00716784 | 20 | available |
| F | development | cin | orientation_gap_q95 | 0.0126335 | 0.00149329 | 20 | available |
| F | development | cin | generator_attempts | 130.95 | 27.1973 | 20 | available |
| F | development | cin | point_fit_seconds | 0.238492 | 0.0070017 | 20 | available |
| F | development | cin | peak_rss_mb | 159.309 | 0.0470625 | 20 | available |
| F | development | cin | n_pairs_complete | 28 | 0 | 20 | available |
| F | development | cin | n_pairs_total | 28 | 0 | 20 | available |
| F | development | cin | n_true_edges | 10 | 0 | 20 | available |
| F | development | cin | n_strong_edges | 2.8 | 0.304354 | 20 | available |
| F | development | cin | strong_edge_set_available | 1 | 0 | 20 | available |
| F | development | cin | n_nonempty_delta_views | 3.2 | 0.137649 | 20 | available |
| F | development | cin | n_nonempty_agreement_views | 3.2 | 0.137649 | 20 | available |
| F | development | cin | delta_0_strong_recall | 0.696667 | 0.0912919 | 20 | available |
| F | development | cin | delta_005_strong_recall | 0.399167 | 0.0780283 | 20 | available |
| F | development | cin | delta_01_strong_recall | 0.299167 | 0.0694956 | 20 | available |
| F | development | cin | delta_02_strong_recall | 0.0933333 | 0.0354256 | 20 | available |
| F | development | cin | oracle_cmi_mae | 0.00823998 | 0.000544654 | 20 | available |
| F | development | cin | oracle_cmi_bias | -0.00573786 | 0.000591747 | 20 | available |
| F | development | cin | oracle_cmi_mae_true | 0.00823998 | 0.000544654 | 20 | available |
| F | development | cin | oracle_cmi_bias_true | -0.00573786 | 0.000591747 | 20 | available |
| F | development | cin | oracle_cmi_mae_all | 0.00469541 | 0.000243255 | 20 | available |
| F | development | cin | oracle_cmi_bias_all | -0.00274758 | 0.00027308 | 20 | available |
| F | development | cin | n_categorical_targets | 8 | 0 | 20 | available |
| F | development | cin | positive_weight_q50 | 0.00231849 | 0.000314145 | 20 | available |
| F | development | cin | positive_weight_q90 | 0.0114512 | 0.00127225 | 20 | available |
| F | development | cin | positive_weight_q95 | 0.0152492 | 0.00185015 | 20 | available |
| F | development | cin | positive_weight_q99 | 0.018657 | 0.00245911 | 20 | available |
| F | development | cin | positive_weight_max | 0.019509 | 0.00262345 | 20 | available |
| F | development | cin | tie_fraction | 0 | 0 | 20 | available |
| F | development | cin | orientation_gap_q50 | 0.001933 | 0.000165368 | 20 | available |
| F | development | cin | orientation_gap_q90 | 0.00895494 | 0.000952978 | 20 | available |
| F | development | cin | orientation_gap_q99 | 0.0179282 | 0.00276922 | 20 | available |
| F | development | cin | orientation_gap_max | 0.0194885 | 0.00325546 | 20 | available |
| F | development | cin | variance_floor_hits | 0 | 0 | 20 | available |
| F | development | cin | variance_floor_observations | 8 | 0 | 20 | available |
| F | development | cin | variance_floor_hit_rate | 0 | 0 | 20 | available |
| F | development | cin | probability_clipped_fraction | 0.00214583 | 0.000590243 | 20 | available |
| F | development | cin | zero_sum_fallbacks | 0 | 0 | 20 | available |
| F | development | cin | minimum_probability | 0.00356154 | 0.0013428 | 20 | available |
| F | development | cin | delta_0_displayed_count | 12.9 | 0.619422 | 20 | available |
| F | development | cin | delta_0_displayed_fraction | 0.460714 | 0.0221222 | 20 | available |
| F | development | cin | delta_0_precision | 0.496321 | 0.0241128 | 20 | available |
| F | development | cin | delta_0_recall | 0.63 | 0.0341051 | 20 | available |
| F | development | cin | delta_0_empty | 0 | 0 | 20 | available |
| F | development | cin | delta_005_displayed_count | 3.95 | 0.425966 | 20 | available |
| F | development | cin | delta_005_displayed_fraction | 0.141071 | 0.0152131 | 20 | available |
| F | development | cin | delta_005_precision | 0.75254 | 0.0553438 | 20 | available |
| F | development | cin | delta_005_recall | 0.305 | 0.0393867 | 20 | available |
| F | development | cin | delta_005_empty | 0 | 0 | 20 | available |
| F | development | cin | delta_01_displayed_count | 1.95 | 0.26631 | 20 | available |
| F | development | cin | delta_01_displayed_fraction | 0.0696429 | 0.00951107 | 20 | available |
| F | development | cin | delta_01_precision | 0.888889 | 0.0602585 | 18 | available |
| F | development | cin | delta_01_recall | 0.175 | 0.0260314 | 20 | available |
| F | development | cin | delta_01_empty | 0.1 | 0.0688247 | 20 | available |
| F | development | cin | delta_02_displayed_count | 0.4 | 0.152177 | 20 | available |
| F | development | cin | delta_02_displayed_fraction | 0.0142857 | 0.0054349 | 20 | available |
| F | development | cin | delta_02_precision | 0.916667 | 0.0833333 | 6 | available |
| F | development | cin | delta_02_recall | 0.035 | 0.0131289 | 20 | available |
| F | development | cin | delta_02_empty | 0.7 | 0.105131 | 20 | available |
| F | development | cin | agreement_delta_0_displayed_count | 10.55 | 0.697646 | 20 | available |
| F | development | cin | agreement_delta_0_displayed_fraction | 0.376786 | 0.0249159 | 20 | available |
| F | development | cin | agreement_delta_0_precision | 0.540549 | 0.0246438 | 20 | available |
| F | development | cin | agreement_delta_0_recall | 0.56 | 0.0372756 | 20 | available |
| F | development | cin | agreement_delta_0_empty | 0 | 0 | 20 | available |
| F | development | cin | agreement_delta_005_displayed_count | 3.9 | 0.428584 | 20 | available |
| F | development | cin | agreement_delta_005_displayed_fraction | 0.139286 | 0.0153066 | 20 | available |
| F | development | cin | agreement_delta_005_precision | 0.75254 | 0.0553438 | 20 | available |
| F | development | cin | agreement_delta_005_recall | 0.3 | 0.0390681 | 20 | available |
| F | development | cin | agreement_delta_005_empty | 0 | 0 | 20 | available |
| F | development | cin | agreement_delta_01_displayed_count | 1.9 | 0.250263 | 20 | available |
| F | development | cin | agreement_delta_01_displayed_fraction | 0.0678571 | 0.00893796 | 20 | available |
| F | development | cin | agreement_delta_01_precision | 0.888889 | 0.0602585 | 18 | available |
| F | development | cin | agreement_delta_01_recall | 0.17 | 0.0241704 | 20 | available |
| F | development | cin | agreement_delta_01_empty | 0.1 | 0.0688247 | 20 | available |
| F | development | cin | agreement_delta_02_displayed_count | 0.4 | 0.152177 | 20 | available |
| F | development | cin | agreement_delta_02_displayed_fraction | 0.0142857 | 0.0054349 | 20 | available |
| F | development | cin | agreement_delta_02_precision | 0.916667 | 0.0833333 | 6 | available |
| F | development | cin | agreement_delta_02_recall | 0.035 | 0.0131289 | 20 | available |
| F | development | cin | agreement_delta_02_empty | 0.7 | 0.105131 | 20 | available |
| F | development | cin | stability_repeats_requested | unavailable | unavailable | 0 | unavailable |
| F | development | cin | stability_repeat_seeds_json | unavailable | unavailable | 0 | unavailable |
| F | development | cin | stability_completed_repeat_ids_json | unavailable | unavailable | 0 | unavailable |
| F | development | cin | stability_node_order_json | unavailable | unavailable | 0 | unavailable |
| F | development | cin | stability_status | unavailable | unavailable | 0 | unavailable |

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
| complete | 20 |
| stability: not_requested | 20 |
