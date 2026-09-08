# Stage 8e Charter: Validating the Composed-Tier False-Edge Recalibration Mapping (main)

Status: **FROZEN before results**
Date: 2026-09-07

## Background and objective

D-068's own exploratory question 2 fit a fresh isotonic curve per
`(dgp, N)` directly on Stage 8c's own composed-tier evidence,
development/validation split already in place (replicates `0`-`999`
development, `1000`-`1999` validation), and found held-out validation
ECE of `.003`-`.017` — well within the `0.10` tolerance this project's
own confidence-calibration work has used throughout. That result was
explicitly **descriptive, not gated, and not deployed** — D-068's own
charter scoped it that way deliberately, since its job was to
characterize whether *a* recalibration approach could work in the
composed setting, not to decide whether to ship one.

This charter promotes that already-computed, already-held-out-validated
finding to an actual decision: an explicit `PROCEED`/`REASSESS` gate on
the same number, a persisted fitted-curve artifact (mirroring D-067's
own `chain_fork_margin_curves.json`), and a scoped wiring option into
`growing_subset_dpi`. **No new significance-test evidence is generated
— this reuses Stage 8c's own already-collected (enriched) evidence
entirely**, the same "compute once, threshold many times" reuse
discipline Stage 8b applied to D-067's own curve.

**A scoping caveat this charter takes more seriously than D-067's own
wiring did, not less**: `chain_fork_hub` and `overlap` are specific,
whole-network synthetic DGP constructions (`p=15`, a particular
generative structure) — not a locally-identifiable substructure the
way "a chain" or "a fork" can be recognized within an arbitrary
3-variable neighborhood. A real dataset can never legitimately claim
to *be* the `chain_fork_hub` or `overlap` DGP the way three real
variables could plausibly resemble an isolated chain or fork. This
charter's own wiring is therefore scoped, in its non-goals below, even
more narrowly than D-067's: valid only for a caller reproducing or
closely mirroring these exact synthetic fixtures (e.g. a future
Stage 8-series evidence runner), never for an arbitrary real or
composed dataset.

## Mechanism

Reuses `mintnet.experiments.stage8c_composed_calibration_reporting
.exploratory_false_edge_recalibration`'s own procedure exactly — per
`(dgp, N)` isotonic regression (`mintnet.confidence.recalibration
.fit_isotonic_curve`), fit on development replicates, evaluated on
validation replicates — applied to Stage 8c's own already-downloaded
enriched `raw_metrics.csv` (the same run D-068/D-069 already used).
The only change is packaging: this charter's own code persists the
fitted curves (`save_curves`) and formalizes the validation ECE check
as a gate rather than a descriptive report.

**Wiring**: `growing_subset_dpi`'s existing `motif_family` parameter
gains two additional valid values, `"chain_fork_hub"` and `"overlap"`,
resolved against this charter's own bundled curve store (loaded
alongside D-067's own, not replacing it — `calibrated_margin`'s
existing nearest-N-snapping and out-of-range-raises behavior applies
identically). No change to `growing_subset_dpi`'s own decision logic
or default (`motif_family=None`) behavior.

## Data-generating processes

None — zero new evidence collection. Reuses Stage 8c's own composed
DGPs, `N` grid, and replicate range entirely (see
`docs/stage8c_charter.md`).

## Selection and gate

**PROCEED**: validation-replicate ECE `<= 0.10` for both `chain_fork_hub`
and `overlap`, at every tested `N in {400,500,600,750,1000,1500,1750}`
— the same tolerance and structure Stage 8b's own gate used. D-068's
own exploratory number (`.003`-`.017`) already suggests this will
hold; this charter re-derives and formally checks it rather than
assuming the descriptive number transfers unexamined into a gated
decision.

**REASSESS**: any tested cell exceeds tolerance — would mean D-068's
own exploratory finding does not hold up under a stricter, dedicated
check (e.g. a transcription or scope error in how the descriptive
number was originally computed), worth its own diagnosis before
deployment.

## Explicit non-goals

- **No claim this mapping applies to any real or arbitrary composed
  dataset.** Explained above — `chain_fork_hub`/`overlap` are specific
  synthetic constructions, not general composed-network labels. Valid
  `motif_family` values here are for reproducing or closely mirroring
  those exact fixtures, not production use on real data.
- **No re-diagnosis of D-069's own open mechanism question** (why
  `conditioning_size_used >= 2` triggers the reversal). This charter
  fixes the symptom via a validated mapping independent of whether
  that cause is ever confirmed.
- **No claim about the isolated-tier motifs.** D-067's own curve and
  scope stand unchanged; this is an entirely separate curve store.
- **No extension to CMIknn or structured-density.** Same D-053-only
  scope restriction as every Stage 8 charter.
- **No claim outside `N in [400, 1750]`** or outside `chain_fork_hub`/
  `overlap` specifically.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the refit curves
and their own validation-ECE table (the gate's own direct evidence),
the persisted curve artifact, the gate decision, and a report.

## Consequences

**If PROCEED**: `calibrated_margin`/`growing_subset_dpi`'s own
`motif_family` parameter gains two validated composed-DGP options,
narrowly scoped per the non-goals above. D-068's own open option (a)
("validate and deploy a composed-tier recalibration mapping") is
resolved; D-069's own mechanism question (option (a) there) remains a
separate, still-open thread, not required before this deployment.

**If REASSESS**: D-068's own exploratory finding does not survive a
dedicated re-check — its own descriptive framing was correct to
withhold deployment, and this charter's own failure becomes a new,
disclosed finding requiring its own diagnosis before any composed-tier
recalibration mapping is trusted.
