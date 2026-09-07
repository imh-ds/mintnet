# Peer-review follow-up: second review response (Stage 1/Stage 2 extension)

This archives the second external review's verdict and requested corrections
(received 2026-08-30, in response to `docs/peer_review_brief_2026-08-30.md`),
matching how the first review was archived in
`docs/peer_review_followup_2026-08-29.md`.

## Review verdict

Broadly positive: validated the core math, the pipeline composition logic,
and D-018's per-motif (not pooled) gating design. Identified four specific
corrections required before proceeding to Stage 3, and recommended against
adding further topology variants in the meantime.

## Requested corrections

1. **Stage 2's FDR gate implementation does not match the charter's frozen
   pooled-FDR definition.** The code averaged each replicate's own FDR ratio
   instead of computing total false discoveries / total discoveries pooled
   across replicates, per `docs/stage2_charter.md`'s "fraction of all flagged
   pairs ... that are actually null." The reviewer independently recalculated
   pooled FDR as `.0121` (N=750) and `.0106` (N=1500), both still under the
   `.10` gate, so D-013's decision was expected not to flip -- but the
   implementation and evidence artifacts needed correcting regardless.
2. **`multi_conditional.py` and `pairwise_correlation.py` silently accept
   zero-variance/degenerate inputs**, letting `np.corrcoef` produce `NaN`
   that silently becomes a non-retained/non-screened edge (via
   `nan <= alpha == False`) rather than a recorded error. Requested explicit
   variance/finite-result checks plus tests.
3. **`docs/stage2c_report.md` overstates an exact equality** ("identical")
   between screening and final false-edge rates; the true recorded values at
   N=750 (`.00101075` vs. `.00100000`) are extremely close but not literally
   equal.
4. **Pre-charter simulation predictions that closely matched frozen results
   should be described as "successful pre-specified predictions," not
   "independent confirmation/replication,"** since they share DGP/code
   assumptions with the frozen runs.

## Closing recommendation

Fix the two implementation issues, regenerate affected Stage 2 evidence,
then begin Stage 3 -- do not add more topology variants right now.

## Disposition

All four corrections applied, in three commits on
`codex/stage1-dpi-motifs`:

1. `fix: reject zero-variance/degenerate inputs in DPI and screening` --
   addresses item 2. Explicit `ValueError` guards added to
   `mintnet.dpi.multi_conditional` and `mintnet.screening.pairwise_correlation`,
   with new unit tests (`tests/unit/test_multi_conditional.py`,
   `tests/unit/test_pairwise_correlation.py`).
2. `fix: compute Stage 2 FDR gate as pooled counts, not mean of ratios` --
   addresses item 1. `mintnet.experiments.stage2` now records raw
   `true_positives`/`false_positives`/`total_flagged` counts per replicate;
   `mintnet.experiments.stage2_reporting`'s `_rule_metrics` and
   `aggregate_stage2` now pool by summed counts. Stage 2's evidence was
   regenerated (`results/generated/stage2_screening/`): corrected FDR is
   `.0121`/`.0106` at N=750/1500, matching the reviewer's independent
   recalculation almost exactly. D-013's PROCEED decision and selected rule
   (`uncorrected, alpha=.001`, both N) are unchanged.
3. `docs: correct overstated identical/confirmed claims (2nd peer review)`
   -- addresses items 3 and 4. `docs/stage2c_report.md` and the D-016 entry
   in `docs/decision_log.md` now state the true N=750 values instead of
   claiming exact equality (N=1500's values are genuinely bit-for-bit
   identical and remain described as such). D-013, D-016, and D-018 in
   `docs/decision_log.md` now describe pre-charter simulation matches as
   "successful pre-specified predictions," not independent confirmation.

Full test suite (190 tests) passes after all three commits.
