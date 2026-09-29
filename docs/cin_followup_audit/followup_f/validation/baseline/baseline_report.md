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
| F | validation | cin | ap | 0.626259 | 0.0126491 | 88 | available |
| F | validation | cin | prevalence | 0.357143 | 5.95142e-18 | 88 | available |
| F | validation | cin | ap_minus_prevalence | 0.269116 | 0.0126491 | 88 | available |
| F | validation | cin | strong_edge_recall | 0.765476 | 0.0285759 | 84 | available |
| F | validation | cin | categorical_excess_loss | -0.00205207 | 0.0011601 | 90 | available |
| F | validation | cin | n_failed_pairs | 0.155556 | 0.109375 | 90 | available |
| F | validation | cin | elapsed_seconds | 0.20037 | 0.00485515 | 90 | available |
| F | validation | cin | orientation_gap_q95 | 0.0157557 | 0.00115476 | 90 | available |
| F | validation | cin | generator_attempts | 153.639 | 14.8096 | 97 | available |
| F | validation | cin | point_fit_seconds | 0.187901 | 0.00477132 | 90 | available |
| F | validation | cin | peak_rss_mb | 159.579 | 0.0636255 | 90 | available |
| F | validation | cin | n_pairs_complete | 27.8444 | 0.109375 | 90 | available |
| F | validation | cin | n_pairs_total | 25.9794 | 0.739471 | 97 | available |
| F | validation | cin | n_true_edges | 10 | 0 | 90 | available |
| F | validation | cin | n_strong_edges | 2.52222 | 0.129561 | 90 | available |
| F | validation | cin | n_nonempty_delta_views | 3.17778 | 0.0859373 | 90 | available |
| F | validation | cin | n_nonempty_agreement_views | 3.17778 | 0.0859373 | 90 | available |
| F | validation | cin | delta_0_strong_recall | 0.765476 | 0.0285759 | 84 | available |
| F | validation | cin | delta_005_strong_recall | 0.430754 | 0.035234 | 84 | available |
| F | validation | cin | delta_01_strong_recall | 0.266468 | 0.0306424 | 84 | available |
| F | validation | cin | delta_02_strong_recall | 0.0876984 | 0.0199786 | 84 | available |
| F | validation | cin | oracle_cmi_mae | 0.00908199 | 0.000299039 | 90 | available |
| F | validation | cin | oracle_cmi_bias | -0.00596946 | 0.000362253 | 90 | available |
| F | validation | cin | oracle_cmi_mae_true | 0.00908199 | 0.000299039 | 90 | available |
| F | validation | cin | oracle_cmi_bias_true | -0.00596946 | 0.000362253 | 90 | available |
| F | validation | cin | oracle_cmi_mae_all | 0.0054066 | 0.000223833 | 90 | available |
| F | validation | cin | oracle_cmi_bias_all | -0.00302362 | 0.000229626 | 90 | available |
| F | validation | cin | n_categorical_targets | 8 | 0 | 90 | available |
| F | validation | cin | positive_weight_q50 | 0.00305596 | 0.000220459 | 90 | available |
| F | validation | cin | positive_weight_q90 | 0.0113405 | 0.000678297 | 90 | available |
| F | validation | cin | positive_weight_q95 | 0.0151771 | 0.000837534 | 90 | available |
| F | validation | cin | positive_weight_q99 | 0.0192376 | 0.00118628 | 90 | available |
| F | validation | cin | positive_weight_max | 0.0202527 | 0.0012938 | 90 | available |
| F | validation | cin | tie_fraction | 0 | 0 | 90 | available |
| F | validation | cin | orientation_gap_q50 | 0.00233922 | 0.00020251 | 90 | available |
| F | validation | cin | orientation_gap_q90 | 0.0113062 | 0.000861245 | 90 | available |
| F | validation | cin | orientation_gap_q99 | 0.0235407 | 0.00153755 | 90 | available |
| F | validation | cin | orientation_gap_max | 0.0258754 | 0.00171745 | 90 | available |
| F | validation | cin | variance_floor_hits | 0 | 0 | 90 | available |
| F | validation | cin | variance_floor_observations | 8 | 0 | 90 | available |
| F | validation | cin | variance_floor_hit_rate | 0 | 0 | 90 | available |
| F | validation | cin | probability_clipped_fraction | 0.00390278 | 0.000496531 | 90 | available |
| F | validation | cin | zero_sum_fallbacks | 0 | 0 | 90 | available |
| F | validation | cin | minimum_probability | 0.00680625 | 0.00151205 | 90 | available |
| F | validation | cin | delta_0_displayed_count | 12.3667 | 0.256477 | 90 | available |
| F | validation | cin | delta_0_displayed_fraction | 0.441667 | 0.00915988 | 90 | available |
| F | validation | cin | delta_0_precision | 0.495229 | 0.0112379 | 90 | available |
| F | validation | cin | delta_0_recall | 0.605556 | 0.0155114 | 90 | available |
| F | validation | cin | delta_005_displayed_count | 3.8 | 0.225248 | 90 | available |
| F | validation | cin | delta_005_displayed_fraction | 0.135714 | 0.00804456 | 90 | available |
| F | validation | cin | delta_005_precision | 0.721268 | 0.0289834 | 89 | available |
| F | validation | cin | delta_005_recall | 0.272222 | 0.0161166 | 90 | available |
| F | validation | cin | delta_01_displayed_count | 1.78889 | 0.159192 | 90 | available |
| F | validation | cin | delta_01_displayed_fraction | 0.0638889 | 0.00568541 | 90 | available |
| F | validation | cin | delta_01_precision | 0.88844 | 0.024531 | 69 | available |
| F | validation | cin | delta_01_recall | 0.152222 | 0.0125647 | 90 | available |
| F | validation | cin | delta_02_displayed_count | 0.555556 | 0.079183 | 90 | available |
| F | validation | cin | delta_02_displayed_fraction | 0.0198413 | 0.00282796 | 90 | available |
| F | validation | cin | delta_02_precision | 0.925439 | 0.0342555 | 38 | available |
| F | validation | cin | delta_02_recall | 0.05 | 0.00711068 | 90 | available |
| F | validation | cin | agreement_delta_0_displayed_count | 10.0222 | 0.280439 | 90 | available |
| F | validation | cin | agreement_delta_0_displayed_fraction | 0.357937 | 0.0100157 | 90 | available |
| F | validation | cin | agreement_delta_0_precision | 0.514046 | 0.0149707 | 90 | available |
| F | validation | cin | agreement_delta_0_recall | 0.515556 | 0.0186907 | 90 | available |
| F | validation | cin | agreement_delta_005_displayed_count | 3.66667 | 0.214342 | 90 | available |
| F | validation | cin | agreement_delta_005_displayed_fraction | 0.130952 | 0.00765508 | 90 | available |
| F | validation | cin | agreement_delta_005_precision | 0.720528 | 0.029909 | 89 | available |
| F | validation | cin | agreement_delta_005_recall | 0.263333 | 0.0160718 | 90 | available |
| F | validation | cin | agreement_delta_01_displayed_count | 1.75556 | 0.158261 | 90 | available |
| F | validation | cin | agreement_delta_01_displayed_fraction | 0.0626984 | 0.00565217 | 90 | available |
| F | validation | cin | agreement_delta_01_precision | 0.887233 | 0.0246606 | 69 | available |
| F | validation | cin | agreement_delta_01_recall | 0.148889 | 0.0124666 | 90 | available |
| F | validation | cin | agreement_delta_02_displayed_count | 0.544444 | 0.0760464 | 90 | available |
| F | validation | cin | agreement_delta_02_displayed_fraction | 0.0194444 | 0.00271594 | 90 | available |
| F | validation | cin | agreement_delta_02_precision | 0.921053 | 0.0354122 | 38 | available |
| F | validation | cin | agreement_delta_02_recall | 0.0488889 | 0.00693189 | 90 | available |
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
| complete | 88 |
| error | 7 |
| incomplete | 2 |
| stability: not_requested | 97 |
