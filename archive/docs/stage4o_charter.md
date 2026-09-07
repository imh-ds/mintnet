# Stage 4o Charter: Synthesis and Recommendation — Resolving the R6a Milestone (R6a Resolution)

Status: **FROZEN before the synthesis is drafted**
Date: 2026-08-31

## Background and objective

`outline/information_network_technical_build_plan_v3_2026-08-30.md`'s
R6a milestone asks a two-part question that has governed every Stage 4
charter since `docs/stage4a_charter.md`: does the sequential/greedy
conditioning engine achieve a materially lower `N` requirement than the
conservative engine on weak-signal shapes, **without** a cascading-error
rate that makes its failures worse than the conservative engine's own?
Fourteen charters (`docs/stage4a_charter.md` through
`docs/stage4n_charter.md`, `docs/decision_log.md` D-030 through D-043)
have now generated the evidence both halves require, across four
shapes (overlap, chain, fork, hub-2-children), isolated and composed
settings, a signal-strength range, and three structurally distinct
cascading-error stress tests. **No charter in this arc has yet stated
the actual recommendation** — each one answered its own narrow
question and explicitly deferred the "is this engine usable" call to a
later synthesis step (most recently, `docs/stage4n_charter.md`'s own
consequences: "the natural next steps are... before any such
recommendation").

**Objective:** this charter is that synthesis step. It does not
generate new simulation evidence. It produces a single, explicit,
per-shape recommendation — RECOMMEND / RECOMMEND WITH DISCLOSED
CAVEATS / INSUFFICIENT EVIDENCE / DO NOT RECOMMEND — built from the
existing record, with a rubric fixed **before** the verdict prose is
written, for the same reason every prior charter fixed its gate before
seeing results: to prevent the act of writing the recommendation from
becoming an exercise in finding words that justify whatever conclusion
feels right in hindsight.

## Scope: the frozen evidence base

This charter synthesizes **exactly** the following, and nothing else.
If a claim in the final synthesis cannot be traced to one of these
sources, it does not belong in the synthesis.

- `docs/decision_log.md` entries **D-030 through D-043** (the complete
  sequential/greedy engine arc).
- `docs/validated_operating_ranges.md`'s own rolled-up paragraphs for
  each of the above (already the project's authoritative quick-
  reference, not restated from scratch here).
- The four shapes tested: **overlap** (`docs/stage1l_charter.md`'s
  fixture), **chain**, **fork**, **hub(2-children)** — no other shape
  (larger hubs, disjoint triads, `p` values other than `15`/isolated,
  etc.) has sequential-engine evidence and none may be described as
  covered.

No new charter's worth of simulation is authorized under this one. If
synthesizing the existing record surfaces a gap that matters enough to
change the recommendation, that gap is reported as a limitation, not
filled in ad hoc within this charter.

## Synthesis rubric (fixed before the verdict is drafted)

For each shape, answer two questions strictly from the frozen evidence
base above, then apply the decision rule below.

**Question A — N-savings.** Is there direct evidence (isolated and/or
composed) that the sequential engine achieves a materially lower `N`
than the conservative engine's own documented requirement for a
comparable DGP, at a specific, named `N` range? "Materially lower" means
a specific `N` at which the sequential engine PROCEEDs and the
conservative engine's own recorded result at the same or larger `N` did
not (or where no direct floor comparison exists, the sequential engine's
own validated floor is stated plainly without a comparison claim).

**Question B — cascading-error characterization.** Has this shape's
cascading-error rate been directly measured (not assumed, not
inferred from a different shape) via a Stage 4c/4m/n-style stress test?
If yes, is the measured effect (a) a clean null, (b) small and
disclosed, or (c) large enough to be concerning? If no measurement
exists for this shape, Question B is **unanswered**, not "presumed
fine."

**Decision rule:**

| Question A | Question B | Verdict |
|---|---|---|
| Materially lower `N`, validated range stated | Measured, null or small-and-disclosed | **RECOMMEND WITH DISCLOSED CAVEATS** (never bare RECOMMEND — every shape tested has at least one caveat on record; a bare RECOMMEND would overstate the evidence) |
| Materially lower `N`, validated range stated | Measured, concerning | **DO NOT RECOMMEND** until the concerning effect is addressed |
| Materially lower `N`, validated range stated | Unanswered | **INSUFFICIENT EVIDENCE** — half the milestone's own question was never asked for this shape |
| Not demonstrated, or demonstrated only outside a validated `N`/strength range | (any) | **INSUFFICIENT EVIDENCE**, scoped to exactly the tested range; explicitly not a negative finding outside it |

This rubric is mechanical by design — it does not leave room for a
shape with genuinely strong Question-A evidence and a genuinely clean
Question-B answer to still be talked into anything less than RECOMMEND
WITH DISCLOSED CAVEATS, nor for a shape missing either half to be
rounded up to a recommendation it hasn't earned.

## Required deliverable

A single new document, `docs/stage4o_recommendation.md`, containing:

1. **A per-shape table** applying the rubric above literally: shape,
   Question A answer (with the specific validated `N`/strength range
   and the decision-log citation), Question B answer (with the
   specific measured effect and citation), and the resulting verdict.
2. **For every shape that reaches RECOMMEND WITH DISCLOSED CAVEATS**,
   the caveats section is not optional boilerplate — it must enumerate
   the *specific* disclosed risks from the frozen evidence base (e.g.,
   overlap's `2%`-`6%` opposite-triangle structural rate from D-043;
   chain/fork/hub's `17`/`18`-cells-positive noise effect from D-042)
   by their actual measured magnitude, not a generic "some risk exists"
   statement.
3. **An explicit boundary-of-recommendation section**: every named
   condition (shape, `N` range, signal strength, `p`, isolated-vs-
   composed) that was tested and is therefore covered, stated
   separately from every condition that was not tested and is
   therefore explicitly **not** covered by any verdict in this
   document — mirroring the discipline `docs/validated_operating_ranges.md`
   already applies to the conservative engine.
4. **A single top-line answer to the outline's own R6a question**:
   given the four per-shape verdicts, does the sequential/greedy engine
   as a whole clear the R6a milestone? A milestone can be cleared for
   some shapes and not others simultaneously — this section states
   that plainly rather than forcing one binary answer across
   structurally different evidence.
5. **Recommended next steps**, drawn only from gaps the synthesis
   itself surfaces (per the "no new charter's worth of simulation"
   scope rule above, these are proposals for *future* charters, not
   work done here).

## Consequences

This charter's own output becomes the answer future work points to
when asked "should the sequential engine be used, and for what" — it
does not itself unlock any new engineering work, and it does not
retroactively change any prior charter's own recorded PROCEED/REASSESS/
descriptive finding. If the synthesis reveals the evidence does not
actually support a clean per-shape verdict (for instance, if two
sources in the frozen base appear to conflict), that conflict is
reported explicitly in the deliverable rather than resolved by
selectively citing one source over the other. This charter closes the
R6a milestone as a piece of project governance; it does not close the
broader project, and `outline/information_network_technical_build_plan_v3_2026-08-30.md`'s
own R6 milestone (broad benchmarking against incumbents) remains
entirely separate, unstarted work.
