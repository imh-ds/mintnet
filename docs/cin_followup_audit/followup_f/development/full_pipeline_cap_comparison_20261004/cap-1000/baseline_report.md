# CIN statistical panel

Rows emitted: 100; pair sidecar rows audited: 2800.
Development-selected display delta: None
Counts are preserved behind every aggregate; incomplete and failed methods remain visible.
Monte Carlo standard errors are descriptive and do not establish tail probabilities or FDR control.
Oracle CMI, regression, null, stability, and variance-only/XOR sections are descriptive or unsupported where no gate applies.
This panel does not establish causal effects or broad recovery claims beyond named validation scopes.

## Metric summaries

Mean, Monte Carlo standard error (MCSE), and contributing row count are shown. An unavailable value has no contributing finite observations; it is not zero.

| Case | Phase | Method | Metric | Mean | MCSE | n | Availability |
|---|---|---|---|---:|---:|---:|---|
| F | development | cin | ap | 0.62207 | 0.00935905 | 100 | available |
| F | development | cin | prevalence | 0.357143 | 1.67372e-17 | 100 | available |
| F | development | cin | ap_minus_prevalence | 0.264927 | 0.00935905 | 100 | available |
| F | development | cin | strong_edge_recall | 0.736806 | 0.0281148 | 96 | available |
| F | development | cin | categorical_excess_loss | -0.00200549 | 0.000887407 | 100 | available |
| F | development | cin | n_failed_pairs | 0 | 0 | 100 | available |
| F | development | cin | elapsed_seconds | 0.750333 | 0.0391093 | 100 | available |
| F | development | cin | orientation_gap_q95 | 0.017974 | 0.00101636 | 100 | available |
| F | development | cin | generator_attempts | 139.7 | 12.6053 | 100 | available |
| F | development | cin | point_fit_seconds | 0.6739 | 0.0390765 | 100 | available |
| F | development | cin | n_pairs_complete | 28 | 0 | 100 | available |
| F | development | cin | n_pairs_total | 28 | 0 | 100 | available |
| F | development | cin | n_true_edges | 10 | 0 | 100 | available |
| F | development | cin | n_strong_edges | 2.63 | 0.129221 | 100 | available |
| F | development | cin | strong_edge_set_available | 1 | 0 | 100 | available |
| F | development | cin | n_nonempty_delta_views | 3.31 | 0.0706321 | 100 | available |
| F | development | cin | n_nonempty_agreement_views | 3.31 | 0.0706321 | 100 | available |
| F | development | cin | delta_0_strong_recall | 0.736806 | 0.0281148 | 96 | available |
| F | development | cin | delta_005_strong_recall | 0.388368 | 0.0331998 | 96 | available |
| F | development | cin | delta_01_strong_recall | 0.234201 | 0.0280687 | 96 | available |
| F | development | cin | delta_02_strong_recall | 0.101736 | 0.0198641 | 96 | available |
| F | development | cin | oracle_cmi_mae | 0.00929992 | 0.000269397 | 100 | available |
| F | development | cin | oracle_cmi_bias | -0.00581979 | 0.000321552 | 100 | available |
| F | development | cin | oracle_cmi_mae_true | 0.00929992 | 0.000269397 | 100 | available |
| F | development | cin | oracle_cmi_bias_true | -0.00581979 | 0.000321552 | 100 | available |
| F | development | cin | oracle_cmi_mae_all | 0.00556927 | 0.000186417 | 100 | available |
| F | development | cin | oracle_cmi_bias_all | -0.00300447 | 0.000162891 | 100 | available |
| F | development | cin | n_categorical_targets | 8 | 0 | 100 | available |
| F | development | cin | positive_weight_q50 | 0.00294868 | 0.000219299 | 100 | available |
| F | development | cin | positive_weight_q90 | 0.0116607 | 0.000619607 | 100 | available |
| F | development | cin | positive_weight_q95 | 0.0165707 | 0.000880302 | 100 | available |
| F | development | cin | positive_weight_q99 | 0.0215859 | 0.00140321 | 100 | available |
| F | development | cin | positive_weight_max | 0.0228397 | 0.00154926 | 100 | available |
| F | development | cin | tie_fraction | 0 | 0 | 100 | available |
| F | development | cin | orientation_gap_q50 | 0.00221807 | 0.000148403 | 100 | available |
| F | development | cin | orientation_gap_q90 | 0.0130151 | 0.000739746 | 100 | available |
| F | development | cin | orientation_gap_q99 | 0.0256331 | 0.00151298 | 100 | available |
| F | development | cin | orientation_gap_max | 0.02795 | 0.00174739 | 100 | available |
| F | development | cin | variance_floor_hits | 0 | 0 | 100 | available |
| F | development | cin | variance_floor_observations | 8 | 0 | 100 | available |
| F | development | cin | variance_floor_hit_rate | 0 | 0 | 100 | available |
| F | development | cin | probability_clipped_fraction | 0.00389583 | 0.000419576 | 100 | available |
| F | development | cin | zero_sum_fallbacks | 0 | 0 | 100 | available |
| F | development | cin | minimum_probability | 0.00580737 | 0.00137035 | 100 | available |
| F | development | cin | delta_0_displayed_count | 12.26 | 0.26728 | 100 | available |
| F | development | cin | delta_0_displayed_fraction | 0.437857 | 0.0095457 | 100 | available |
| F | development | cin | delta_0_precision | 0.495205 | 0.00859336 | 100 | available |
| F | development | cin | delta_0_recall | 0.601 | 0.0145987 | 100 | available |
| F | development | cin | delta_0_empty | 0 | 0 | 100 | available |
| F | development | cin | delta_005_displayed_count | 3.73 | 0.209788 | 100 | available |
| F | development | cin | delta_005_displayed_fraction | 0.133214 | 0.00749244 | 100 | available |
| F | development | cin | delta_005_precision | 0.763032 | 0.0221979 | 100 | available |
| F | development | cin | delta_005_recall | 0.268 | 0.0139899 | 100 | available |
| F | development | cin | delta_005_empty | 0 | 0 | 100 | available |
| F | development | cin | delta_01_displayed_count | 1.94 | 0.147587 | 100 | available |
| F | development | cin | delta_01_displayed_fraction | 0.0692857 | 0.00527095 | 100 | available |
| F | development | cin | delta_01_precision | 0.825388 | 0.0292983 | 86 | available |
| F | development | cin | delta_01_recall | 0.153 | 0.0112326 | 100 | available |
| F | development | cin | delta_01_empty | 0.14 | 0.0348735 | 100 | available |
| F | development | cin | delta_02_displayed_count | 0.63 | 0.0848707 | 100 | available |
| F | development | cin | delta_02_displayed_fraction | 0.0225 | 0.0030311 | 100 | available |
| F | development | cin | delta_02_precision | 0.885185 | 0.0399292 | 45 | available |
| F | development | cin | delta_02_recall | 0.053 | 0.00717107 | 100 | available |
| F | development | cin | delta_02_empty | 0.55 | 0.05 | 100 | available |
| F | development | cin | agreement_delta_0_displayed_count | 9.96 | 0.255018 | 100 | available |
| F | development | cin | agreement_delta_0_displayed_fraction | 0.355714 | 0.0091078 | 100 | available |
| F | development | cin | agreement_delta_0_precision | 0.525912 | 0.00989227 | 100 | available |
| F | development | cin | agreement_delta_0_recall | 0.519 | 0.0148864 | 100 | available |
| F | development | cin | agreement_delta_0_empty | 0 | 0 | 100 | available |
| F | development | cin | agreement_delta_005_displayed_count | 3.52 | 0.198723 | 100 | available |
| F | development | cin | agreement_delta_005_displayed_fraction | 0.125714 | 0.00709726 | 100 | available |
| F | development | cin | agreement_delta_005_precision | 0.774369 | 0.022433 | 100 | available |
| F | development | cin | agreement_delta_005_recall | 0.257 | 0.0134281 | 100 | available |
| F | development | cin | agreement_delta_005_empty | 0 | 0 | 100 | available |
| F | development | cin | agreement_delta_01_displayed_count | 1.9 | 0.142489 | 100 | available |
| F | development | cin | agreement_delta_01_displayed_fraction | 0.0678571 | 0.00508888 | 100 | available |
| F | development | cin | agreement_delta_01_precision | 0.823837 | 0.0293706 | 86 | available |
| F | development | cin | agreement_delta_01_recall | 0.15 | 0.0109637 | 100 | available |
| F | development | cin | agreement_delta_01_empty | 0.14 | 0.0348735 | 100 | available |
| F | development | cin | agreement_delta_02_displayed_count | 0.63 | 0.0848707 | 100 | available |
| F | development | cin | agreement_delta_02_displayed_fraction | 0.0225 | 0.0030311 | 100 | available |
| F | development | cin | agreement_delta_02_precision | 0.885185 | 0.0399292 | 45 | available |
| F | development | cin | agreement_delta_02_recall | 0.053 | 0.00717107 | 100 | available |
| F | development | cin | agreement_delta_02_empty | 0.55 | 0.05 | 100 | available |

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
| complete | 100 |
| stability: not_requested | 100 |
