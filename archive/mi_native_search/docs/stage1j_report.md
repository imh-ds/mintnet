# Stage 1j alpha(N) Fitting and Held-Out Validation Report (R2j)

Status: **PROCEED**

## Fitting

Four predeclared candidate forms fit to the six known validated points
(`docs/decision_log.md` D-008 through D-010):

| Form | R^2 |
|---|---|
| Linear in `N` | .952 |
| **Linear in `log(N)`** | **.997** |
| Power law | .987 |
| Inverse-sqrt | .989 |

`linear_log_n` wins outright (`.997`), more than `.005` ahead of every
other form — no tiebreaker needed. Selected formula:
`alpha(N) = 0.5222 - 0.0566 * ln(N)`.

## Held-out validation

`configs/stage1j_dpi.yaml`: four interpolated sample sizes never
simulated before, testing only the formula's single predicted `alpha_hat`
at each (no grid search). 72,000 raw rows, zero errors, runtime 35.9s.

`results/generated/stage1j_dpi/decision.json`:

| N | alpha_hat | status | margin |
|---|---|---|---|
| 900 | .1373 | **PROCEED** | .039 |
| 1250 | .1187 | **PROCEED** | .069 |
| 1750 | .0996 | **PROCEED** | .079 |
| 2500 | .0795 | **PROCEED** | .097 |

Every held-out sample size clears the required `.02` margin comfortably —
none are thin-margin passes in the D-011 sense. Margin increases with `N`,
consistent with every prior finding in this line of charters (D-006,
D-009, D-010).

## Outcome

**PROCEED.** The `linear_log_n` formula, fit only on six known points at
`N in [700, 3000]`, correctly predicts a working single alpha value —
not merely a plausible one, but one with real margin — at four sample
sizes it never saw during fitting. This is the actual test this charter
was designed for: curve-fit quality alone (`R^2 = .997`) would not have
been sufficient evidence on its own, since a formula can fit known points
well and still fail to generalize between them. It did not fail here.

**Frozen candidate default rule** (interpolation only, `N` in
`[700, 3000]`; do not extrapolate outside this range per
`docs/stage1j_charter.md`):

```
alpha(N) = 0.5222 - 0.0566 * ln(N)
```

This is a candidate for a production default, not itself a production
default — adopting it as one is a separate, later decision, per the
charter's consequences.

See `raw_metrics.csv`, `decision.json`, `resolved_config.yaml`, and
`alpha_n_fit.png` under `results/generated/stage1j_dpi/` for complete
evidence.
