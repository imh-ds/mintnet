# Peer-review follow-up: approved Stage 1 pivot

The project owner has explicitly approved the pivot from tolerant pairwise-MI
DPI to Gaussian conditional-independence pruning by partial correlation. This
is a documentation-alignment task, not a request to revert the pivot.

Before advancing the governing plan, update
`outline/information_network_technical_build_plan.md` and the relevant
decision documentation to do the following:

1. Record that the original tolerance-modified pairwise-MI DPI mechanism
   failed its Stage 1 gate, and that an approved replacement mechanism is
   Gaussian conditional-independence pruning via partial correlation.
2. State the validated scope precisely: continuous jointly Gaussian data,
   three-node motifs, observed conditioning variable, and `N >= 750`.
   Do not imply validation of a nonparametric conditional-MI estimator,
   nonlinear data, mixed data, or arbitrary graph sizes.
3. Revise later-stage references that mandate `MI -> screen -> tolerant DPI`
   so a future Stage 2 charter can use the approved conditional-independence
   mechanism explicitly. Preserve the original DPI result as a recorded
   failed alternative rather than silently overwriting history.
4. Correct R2h wording: shared `N = 750, 1000, 1500, 2000` samples are
   intentionally reproduced from earlier seed derivations. R2h is valid as
   a predeclared reanalysis under a new per-N rule, but is not an independent
   fresh replication at those N values.
5. Limit the `N <= 300` conclusion to the frozen alpha grid
   `[.0001, .50]` unless a broader sweep or analytic proof supports a claim
   about every possible alpha.
6. Relabel `1 - p_value` as an exploratory score, not a calibrated confidence
   probability. Do not use its Brier score against a `.25` baseline as a
   calibration claim without a prevalence baseline and a dedicated
   held-out reliability analysis.

Technical review conclusion: the partial-correlation formula, Fisher-z
scaling `sqrt(N - 4)` for one conditioning variable, p-value decision rule,
development/validation separation, and R2g/R2h gate implementation are
correct for their stated Gaussian scope. Fisher-z p-values should be called
an asymptotic normal approximation, while the population equivalence between
zero partial correlation and zero Gaussian conditional MI is exact.
