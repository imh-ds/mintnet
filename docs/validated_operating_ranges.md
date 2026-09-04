# Validated Operating Ranges

This is a maintained reference, not a chronological log (see
`docs/decision_log.md` for the narrative). It tracks, per methodological
component, the sample size below which the component's automatic
data-driven decision should not be trusted on its own.

## How to read this table

The project's working stance (set 2026-08-29, informing how this table is
used going forward): at large `N`, the data carries enough power to drive
decisions with minimal researcher input — closer to exploratory analysis.
At small `N`, a component may still produce a number, but that number
should not be trusted to decide anything autonomously; the researcher's
own theoretical or conceptual justification should carry the actual
decision, with the data used to check consistency rather than to drive the
call. The **minimum N for autonomous use** column marks that transition
per component, as currently evidenced. Below it, treat the component's
output as informative context for a researcher-justified decision, not as
the decision itself.

This table records what has been *validated*, not what is *assumed*. A
component not listed here has no validated range yet; a range listed here
is only as good as the evidence behind it, cited in the Source column.

## Table

| Component | Reliable (autonomous) from | Below this | Source |
|---|---|---|---|
| Bivariate association estimation (KSG-1 mutual information, `k=20`, continuous Gaussian) | `N >= 100` (validated `100`-`1000`; gate specifically checked at `N=300, 500`) | Not separately tested below `N=100`; no evidence of a lower-bound problem in the tested range | Stage 0, `docs/decision_log.md` D-001 |
| DPI edge pruning — binary retain/prune decision (conditional-independence via partial correlation, three-node chain/fork/triangle motifs) | **Comfortable margin from `N >= 750`** (alpha decreasing `~0.15` at `750` to `~0.07` at `3000`, margin >= `.03`, see per-`N` table below). **Thin margin at `N = 700`** (alpha `(0.14, 0.16)`, margin `.012`, close to the `~.01` noise floor at 1000 replicates — a real pass, not a comfortable one) | `N <= 600`: no development-eligible alpha pair at all — decisive, not a tuning problem. `N = 650`: near-miss (eligible in development, fails validation). `N <= 300` (from the wider R2h sweep): decisive, structural gap across the whole tested alpha range | Stage 1g/1h/1i, `docs/decision_log.md` D-008, D-009, D-010 |
| `1 - p_value` as a candidate confidence-style score (continuous, non-binary) | Informative (Brier score well below a flat `0.25` baseline) across the *entire* tested range, `N = 100`-`3000` — **not** a validated calibration claim: no reliability diagram or prevalence-adjusted baseline has been computed, only a pooled Brier score against a flat baseline | Not yet chartered as a formal mechanism with its own gate — currently exploratory tracking only, alongside every Stage 1 charter since R2b, never itself validated as a decision rule or as calibrated | D-003 through D-009 (exploratory sections); no dedicated charter yet |
| Candidate-edge screening — per-pair Fisher-z on raw correlation, uncorrected or BH-corrected (`p=15` network, 9 true / 96 null pairs) | `N in [750, 1500]` (both tested points PROCEED). Uncorrected `alpha=.001` sufficient (recall ~1.0, FDR ~.01); BH correction available but not required for this DGP | Not tested below `N=750` or above `N=1500`; not tested at `p != 15`; validated only in isolation, not composed with DPI pruning | Stage 2, `docs/decision_log.md` D-013 |
| Candidate-edge screening at **`p=30`** — same mechanism, same 9 true signals, 426 null pairs (`~4.4x` worse true:null ratio than `p=15`) | `N in [750, 1500]` (both PROCEED). Uncorrected `alpha=.0001` selected (recall `.999`-`1.0`, FDR `.005`-`.007`) — a margin comparable to or better than `p=15`'s, once the candidate grid was extended below Stage 2's original lower bound. **Do not assume `alpha=.001` still suffices at this `p`** — it clears the gate (FDR `~.045`-`.049`) but is no longer the selected rule, and `alpha=.005`+ fails outright (FDR `.19`+, not a near-miss). BH `q=.05` also passes; **`q=.10` narrowly missed its own nominal level** (FDR `.11`-`.11`) — do not trust BH `q=.10` at this true:null ratio without further checking | Now also validated composed with DPI pruning (see the row below) at `p=30`; not tested at `p` values beyond `30`, nor different true-signal counts/true:null ratios. Corrects an initial "BH becomes more necessary as `p` grows" intuition: extending the uncorrected grid downward fully compensated here, for this specific true-signal count | Stage 2e, `docs/decision_log.md` D-023 |
| Composed pipeline at **`p=30`** — screening (`alpha=.0001`, D-023) then DPI (`alpha=f(N)`, D-012), on **two** candidate shapes: disjoint chain/fork/triangle (D-024) and chain/fork/hub (D-025) | `N in [750, 1500]` (both PROCEED, both shapes). Final false-edge rate `.0001`-`.0001` on both shapes, identical to screening-alone's own rate at both `N` (D-014's "DPI cannot rescue an isolated false positive" finding replicated twice at `p=30`); indirect TPR `.838`-`.891` (triangle shape) / `.839`-`.883` (hub shape); true-edge FPR `<=.006`; shape-validation rate `.98`-`.99` on both (slightly higher than `p=15`'s `~.96`) | Validated only for these two candidate shapes at `p=30`. **Do not extrapolate to the shared-node-overlap shape — see the REASSESS row directly below.** Bootstrap stability remains untested at `p=30` for any shape (Stage 3's line of work is `p=15`-only); not tested beyond `p=30` | Stage 2f/2g, `docs/decision_log.md` D-024, D-025 |
| Composed pipeline at **`p=30`**, **shared-node-overlap shape** — same mechanism, same D-023 screening threshold | **Located floor: `N=1750`, not `1500`.** `N in {1500, 1600}`: REASSESS without filtering (overlap TPR `.762`/`.786`, both below the `.80` gate — `1500` is `.750` at `p=15` (D-018) but no longer sufficient at `p=30`). **`N >= 1750`: PROCEED** (TPR `.815` at `1750`, rising to `.906` by `2500`). Chain/fork TPR and true-edge FPR behave normally at every tested `N`; the effect is isolated to the overlap motif's weak (`~.135`) cross-branch signal meeting `p=30`'s stricter, signal-agnostic threshold. **Both `N=1500` and `N=1600` can instead PROCEED via bootstrap-stability filtering at `pi_min=.80`, without collecting more data — see the filtering row below** | Floor is specific to this exact signal strength (`~.135`) and D-023's exact threshold (`alpha=.0001`) — a different weak signal or a different `p`-driven threshold needs its own floor search, not an assumption this transfers. Do not use unfiltered `N=1500` or `1600` for this shape at `p=30` | Stage 2h/2i, `docs/decision_log.md` D-026, D-027 |
| Composed pipeline at **`p=5` and `p=10`**, **shared-node-overlap shape** — same mechanism; screening `alpha` re-derived at `p=10` (`.0005` selected), fixed at D-013's `.001` at `p=5` (zero null pairs at that `p`, selection undefined) | **`N=750` REASSESS, `N=1500` PROCEED, at both `p=5` and `p=10` — the same floor as `p=15`, not lower.** Overlap TPR `.606` (`p=5`)/no eligible screening alpha at all (`p=10`) at `N=750`; `.836`/`.814` at `N=1500`. **This contradicts the charter's own prediction** that fewer null pairs (looser required screening alpha) would make `N=750` sufficient at lower `p` — it does not. True-edge FPR `0` throughout at `N=1500`. `chain TPR` and false-edge-rate metrics are undefined (not merely untested) at `p=5`, which has zero noise columns and therefore zero null pairs | The overlap shape's `N=750` failure is governed by the per-pair Fisher-z detection power of its weak (`~.135`) correlation at fixed `N`, not by null-pair count/screening pressure — that mechanism only matters when it shifts the selected `alpha` by an order of magnitude, as it did at `p=30` (not between `p=5`/`10`/`15`). **Treat this shape's `N=1500` floor as effectively `p`-invariant across `[5, 30]`, except `p=30` itself needs `N=1750`.** Real `p=5`-`10` behavioral datasets with a similarly weak-signal shared-cause structure should budget `N>=1500`, not assume relief from having fewer variables | Stage 2j, `docs/decision_log.md` D-029 |
| Composed pipeline — screening (`alpha=.001`) then generalized DPI (`mintnet.pipeline.compose`) within any validated clique shape (size 3, 4, or 5), using the D-012 `alpha(N)` formula (`p=15`) | `N in [750, 1500]` for triad-only (D-014) and triad+hub (D-016) networks — both PROCEED at both `N`. **For the triad+shared-node-overlap network, PROCEED only at `N=1500`; REASSESS at `N=750`** (D-018) — see the overlap-specific row below for why. Final false-edge rate exactly tracks screening's own rate in every test so far; true-edge FPR is `0`-`.005` throughout | **Validated for disjoint candidate components of size 3, 4, or 5 that are full cliques — but "validated clique size" alone does not guarantee PROCEED at every `N`: screening must also reliably produce that clean clique for the specific DGP's signal strength (D-018).** Non-clique shapes, cliques of size 6+, larger networks, and components sharing variables across *more than one pair* of motifs are explicitly untested | Stage 2b/2c/2d, `docs/decision_log.md` D-014, D-016, D-018 |
| Multi-variable conditioning — DPI conditioning on all other nodes in a candidate component, tested on a 4-node hub (1 hub, 3 children) | `N in [750, 1500]` (both PROCEED, comfortable margin `.05`-`.09`). The existing D-012 `alpha(N)` formula works unmodified — no new fit needed for two-variable conditioning. **Wired into the composed pipeline, PROCEED at both tested `N`** (D-016) | Validated only for the hub shape (one shared cause, independent children). Components formed by two motifs sharing a node, or larger structures, remain untested | Stage 1k, `docs/decision_log.md` D-015 |
| Multi-variable conditioning — same rule, tested on a genuinely different topology: two `balanced` triangles sharing one node (5 variables, 3-variable conditioning) | Mechanism validated at `N in [750, 1500]` (both PROCEED, margin `.06`-`.09`) *when handed a clean component directly*. **Wired into the composed pipeline: PROCEED only at `N=1500`, REASSESS at `N=750`** (D-018) — the mechanism itself is fine at `N=750` (D-017); the bottleneck is screening's power to detect this DGP's weak (`~.135`) cross-branch correlation, only `~66%` at `N=750` (vs. `~98%` at `N=1500`), so a clean candidate clique forms only `~29%` of the time at `N=750` vs. `~92%` at `N=1500` | **Do not trust this shape below `N=1500` in a full pipeline**, even though the DPI mechanism and the general `N>=750` floor would suggest otherwise — this is a screening-detection-power limitation specific to weak-signal shapes, not a DPI limitation. The hub shape (above) does not share this caveat; its signal is strong enough to detect reliably at `N=750` too | Stage 1L/2d, `docs/decision_log.md` D-017, D-018 |
| Bootstrap edge stability — row resampling (`B=500`) of the composed screen-then-prune pipeline, final-edge stability `pi_final` thresholded at a calibrated `pi_min` | `N in [750, 1500]` (both PROCEED), on **all three** composed-pipeline DGPs studied so far: disjoint chain/fork/triangle (D-014), chain/fork/hub (D-016), and shared-node overlap (D-018) — `p=15` each. Smallest candidate `pi_min=.70` eligible and selected at both `N` on **all three** DGPs; stability recall `1.0` (`.995` at one cell), stability FDR `0`-`.007`, no measurable regression vs. the point-estimate baseline | **This gate answers a narrower question than "is the network accurate": it separates stable from unstable edges, and says nothing about indirect-edge pruning correctness.** On the overlap DGP specifically, this gate PROCEEDs at `N=750` even though D-018 independently found REASSESS there for indirect-edge pruning — these are answers to different questions about the same DGP and must never be merged or treated as contradictory. Not validated for `B` values other than `500`, or for any DGP outside `p=15`/`N in [750, 1500]` | Stage 3/3c/3d, `docs/decision_log.md` D-019, D-021, D-022 |
| Bootstrap stability, **indirect-edge categories specifically** (descriptive, not gated by the row above) — how the edges D-018 found problematic behave under resampling | Wrongly-retained/still-present overlap-indirect edges show *intermediate* stability at both tested `N` (`N=750` mean `pi_final` `.505`, only `23%` would survive even a `pi_min=.70` filter; `N=1500` mean `.653`) — clearly separated from null (`~.02`) but well below true edges (`~1.0`) at every measurement across D-019 and D-022 | Not itself a gate or a fix — see the dedicated rescue-mechanism row below (Stage 3b) for the one validated way to act on this observation | Stage 3/3d, `docs/decision_log.md` D-019, D-022 |
| Bootstrap stability **filtering as a rescue mechanism** — post-hoc `pi_final < pi_min` edge removal, gated on the shared-node-overlap DGP itself, `~.135` cross-branch correlation, **confirmed at both `p=15` and `p=30`** | `p=15`, `N in [750, 1500]` (both PROCEED, D-020). `p=30`, `N in [1500, 1600, 1750]` (all three PROCEED, D-028; `1750` already passed unfiltered — included as a no-regression check). **`pi_min=.80` — the smallest candidate in the grid — is eligible and selected at every `N` tested at both `p` values**, with true-edge FPR exactly `0` throughout. `p=15` `N=750`: TPR `.558`-`.633` baseline -> `.867` filtered. `p=30` `N=1500`/`1600`: TPR `.742`-`.800` baseline -> `.850`-`.900` filtered | Validated **only** for this exact DGP shape and signal strength, at `B=500`, now at two `p` values (`15`, `30`). The selected threshold (`pi_min=.80`) transferred across the `p` change without recalibration. **Not** validated: other under-powered shapes, other signal strengths, `p` values other than `15`/`30`, `pi_min` values below `.80` (untested whether an even cheaper threshold also works), or adopting this as a permanent stage in `mintnet.pipeline.compose` (a separate architecture decision; the `~500x` per-dataset bootstrap cost is unresolved for production use) | Stage 3b/3e, `docs/decision_log.md` D-020, D-028 |

## Per-N alpha table for DPI pruning (from Stage 1h/1i)

| N | status | alpha pair | margin |
|---|---|---|---|
| 500 | REASSESS | none | — |
| 550 | REASSESS | none | — |
| 600 | REASSESS | none | — |
| 650 | REASSESS (near-miss) | (0.14, 0.16), failed validation | .018 (dev only) |
| 700 | PROCEED (thin) | (0.14, 0.16) | .012 |
| 750 | PROCEED | (0.14, 0.16) | .032 |
| 1000 | PROCEED | (0.12, 0.14) | .041 |
| 1500 | PROCEED | (0.10, 0.12) | .075 |
| 2000 | PROCEED | (0.08, 0.10) | .087 |
| 3000 | PROCEED | (0.06, 0.08) | .099 |

## Candidate alpha(N) formula (from Stage 1j, D-012)

```
alpha(N) = 0.5222 - 0.0566 * ln(N)
```

Fit on the six points above (`R^2 = .997`) and validated by predicting a
single alpha (no grid search) at four interpolated, held-out `N` values
never used in fitting — all four passed with comfortable margin (`.039`
to `.097`, all `>= .02`; see `docs/decision_log.md` D-012 and
`docs/stage1j_report.md`).

**Scope: interpolation only, `N` in `[700, 3000]`.** Do not extrapolate
below `700` (the D-010/D-011 floor) or above `3000` (edge of the tested
range) — both are outside this formula's validated scope, regardless of
what the formula computes there. This is a *candidate* default rule for a
future production implementation, not itself a production default; that
adoption decision is separate and has not been made.

## Recommended default floor: N = 750, not N = 700

Both `700` and `750` PROCEED, but they should not be treated as
interchangeable. **`N = 750` is the recommended default floor for
autonomous use; `N = 700` is documented as an available thin-margin
option, not a default.**

Justification:

1. **Margin size relative to noise.** `700`'s margin (`.012`) sits at
   roughly `1.3` standard errors above the pass/fail line at 1000
   validation replicates (`~.0095`-`.0126`, D-006/D-009). `750`'s margin
   (`.032`) sits at roughly `3`-`4` standard errors. A floor meant for
   *autonomous* use — the whole point of a "reliable without researcher
   oversight" threshold — needs to hold up under the ordinary sampling
   variation of a real dataset, not just the specific replicate draw that
   happened to pass in this simulation. `700`'s margin is the kind that
   has, in this exact project, previously flipped sides on independent
   re-checks (D-005, D-007). `750`'s has not.
2. **`650` is a near-miss right next door.** The evidence chain from
   `650` (fails) to `700` (barely passes) to `750` (comfortably passes)
   is a fast transition over a short interval, not a flat plateau. Being
   one step past a demonstrated failure case, at a margin close to the
   size of the step itself, is a fragile place to set a default.
3. **The floor's job is to be trustworthy without inspection.** Per this
   document's own stated stance (top of this file), the value of an
   "autonomous use" floor is that a researcher doesn't have to
   double-check it case by case. A thin-margin floor partially defeats
   that purpose — it would still warrant the researcher-judgment caveat
   this document recommends for below-floor `N`, just less severely.

`N = 700` remains a legitimate, disclosed option for a user who
understands and accepts the thinner margin (e.g., a researcher who cannot
collect more data and wants the best validated option available, with the
explicit caveat that it is close to the noise floor). It is not withheld
— it is labeled honestly.

## Caveat: weak-signal overlapping shapes need N = 1500, not the general N = 750 floor

The `N = 750` default above applies to the DPI mechanism itself and to
every candidate shape tested so far *except one*. **The shared-node-
overlap shape (two motifs meeting at one variable, D-017/D-018) requires
`N >= 1500` in a full pipeline, not `750`**, even though `750` clears
every other bar in this document (the general DPI floor, and the DPI
mechanism's own accuracy on this exact shape when handed a clean
component directly).

The reason is specific and does not generalize to other shapes: at
`N=750`, screening only detects this shape's weak (`~.135`) cross-branch
correlation `~66%` of the time per edge, so all four cross-branch edges
are simultaneously detected — the condition needed to form a clean,
DPI-eligible candidate clique — only `~29%` of the time. The other `71%`
of the time, DPI is correctly *not* applied (per the pipeline's
conservative design), and un-pruned candidate edges pass straight
through, dragging the overlap-specific indirect-edge accuracy down to
`.569`, below the `.80` gate. At `N=1500`, per-edge detection is `~98%`,
clean-clique formation is `~92%`, and the shape clears the gate
comfortably (`.817`).

**This caveat is shape-specific, not a general revision to the `N=750`
floor.** The hub shape (D-015/D-016) has a stronger signal and does not
share it — it clears the gate at `N=750` in the full pipeline just as
reliably as it does as an isolated mechanism test. Before trusting any
*new* multi-node candidate shape at the general `N=750` floor, check its
screening-detection power specifically, the way D-018 did — do not assume
it transfers from the hub case.

## Practical translation for smaller-`N` datasets

For DPI edge-pruning decisions below the recommended default (`N < 750`;
`N = 700` is a disclosed thin-margin exception, not part of "below the
floor"; firmly below `N <= 600`; decisively below `N <= 300`): do not let
the automatic significance test decide whether an edge is real. Use it as
one input among others —
alongside prior domain knowledge, theoretical justification, or
qualitative reasoning the researcher states and defends — and let the
`1 - p_value` score (which stays informative, though not itself
validated as calibrated, even at small `N`) flag which specific edges are
most uncertain and therefore most in need of that justification, rather
than using it to make the cut itself.

## New engine in progress: sequential/greedy conditioning (not yet validated for any use)

A second, alternative engine — rank candidates by association strength,
confirm the strongest immediately, test the rest by conditioning on
already-confirmed neighbors, with permanent pruning — is being developed
alongside the conservative engine documented in every row above, not as
a replacement. **It has no validated operating range yet and must not be
assumed to inherit any row in this table.** Status as of Stage 4a
(`docs/decision_log.md` D-030): on the smallest falsifiable slice
(three-node chain/fork/triangle motifs, Stage 1b's original `N in
[100,1000]` grid), it reproduces the conservative engine's own numbers
almost exactly (mean absolute delta `.01`-`.02` across 486 matching
cells) and shows one favorable divergence at small `N` (fewer wrongly-
pruned true triangle edges, by design — at most one of a triangle's
three edges can ever be wrongly pruned under this engine, versus all
three independently at risk under the conservative engine's symmetric
test). This is informational only; no `N` recommendation follows from
it.

**Promising unresolved signal from Stage 4b (D-031):** on the isolated
(noise-free) hub and shared-node-overlap DGPs, run end-to-end with no
pre-flagged input, the sequential engine PROCEEDs on hub at both `N in
[750, 1500]` (slightly beating the conservative engine's own hand-fed
numbers) and on overlap at `N=1500`. **At overlap `N=750` — the exact
`N` and shape where the conservative composed pipeline REASSESSes at
TPR `.569` (D-018) — the sequential engine reaches TPR `.818`,
recovering `~86%` of the gap** to the conservative mechanism's own
hand-fed ceiling (`.858`, D-017), clearing the raw `.80` gate but
narrowly missing this charter's own stricter `.02` comfort-margin
requirement. **This is not a validated floor of `N=750` for this shape
under the sequential engine** — it is evidence the mechanism is on the
right track, on a noise-free DGP, still short of a comfortable margin,
and untested embedded in a larger noisy candidate pool. Do not recommend
`N=750` for this shape under any engine on the strength of this result
alone.

**Stage 4e correction attempt — the artifact is fixed, but a second,
unexplained pattern replaced it.** Separating screening candidacy from
conditioning correctness (D-033) confirms candidacy behaves normally
(rises with `N`, `.874` at `N=300` to `.991` at `N=700`), but the
corrected `conditional_accuracy` metric itself still declines modestly
as `N` rises, at every tested alpha and uniformly across all 4
cross-branch pairs (e.g. at alpha `.10`: `.934` at `N=300` down to
`.917` at `N=750`) — the opposite of the normal, expected direction, and
not explained by the non-detection confound this metric was built to
remove. **This is now an open, unexplained anomaly, not a floor in
either direction.** Do not report any `N` recommendation for the
overlap shape under the sequential engine — favorable or unfavorable —
until this pattern is explained or ruled out as noise. See D-033.
**Resolved by D-034 below — see that entry before acting on this
paragraph.**

**Stage 4d floor search — hub confirmed robust down to N=300; overlap's
low-N floor is unknown, not favorable.** Hub's indirect-edge TPR stays
flat (`.895`-`.911`) across `N=300`-`750`, verified via a diagnostic
showing every indirect pair reliably reaches an actual conditioning test
at every tested `N` — a genuine finding, though not comparable to the
base mechanism's own `[600,700]` transition (that reference was
calibrated on a harder, worst-case asymmetric-triangle grid, not this
DGP's fixed, more favorable signal strength). **Overlap's apparent
"PROCEED down to N=300" result is a metric artifact and must not be
used**: at low `N`, fewer of the 4 weak cross-branch pairs even clear
initial screening (`3.42`/`4` at `N=300` vs. `3.96`/`4` at `N=750`,
verified directly), and a pair that is never flagged as a candidate is
scored identically to one correctly pruned via conditioning — inflating
apparent TPR at exactly the `N` where the engine is actually doing
*less*, not more. **Overlap's floor below `N=750` remains genuinely
unknown** and should not be assumed favorable; a corrected metric
(tracking cross-branch candidacy rate separately from final TPR) is
needed before that question can be answered. See D-032.
**Resolved by D-034 below — see that entry before acting on this
paragraph.**

**Stage 4f diagnostic — the anomaly is explained, and it retroactively
invalidates every fixed-alpha overlap-shape `N` comparison run so far
(D-031/D-032/D-033).** The apparent low-`N` advantage was never a
property of the sequential engine's reasoning — it is the same
miscalibration D-012 was originally built to fix for the conservative
engine: a fixed significance level requires a *larger* observed effect
to count as "significant" at small `N` (the exact `|r|` needed at
`alpha=.10` is `.095` at `N=300` vs. `.060` at `N=750`), so a fixed
threshold is mechanically more lenient (easier to correctly fail to
reject) at low `N`, regardless of whether the underlying edges are
actually easier to classify there. A direct check (Stage 4f) found the
opposite of the original "marginal detection is an unrelated fluke"
hypothesis — low-`N` candidates' partial correlations are *larger* and
*more correlated* with their marginal detection strength, not smaller
or independent — confirming this is pure threshold miscalibration, not
a real reasoning advantage at low `N`. **No `N` recommendation for the
overlap shape under the sequential engine is authorized by any evidence
collected so far** — Stage 4b/4d/4e all used a fixed, `N`-independent
alpha. A follow-up fitting an `N`-adjusted alpha for the sequential
engine's conditioning step (mirroring D-012's own methodology), then
re-running the floor search under it, would be needed before this
shape's true floor under this engine can be assessed. Hub's own Stage 4d
PROCEED result is unlikely to be affected given its much wider
true/indirect signal separation, but has not been explicitly
re-confirmed under a calibrated alpha either. See D-034.

**Stage 4g recalibration — the conditioning mechanism is now validated
under proper calibration, but the practical floor question remains
open.** A fitted `alpha(N)` formula (inverse-sqrt, R² `.966`, fit from
Stage 4e's own evidence with a `.80` candidacy-rate floor added during
implementation to keep the fitting target meaningful) PROCEEDs at every
held-out `N` tested — `[400, 550, 625, 675, 725]` — with conditional
accuracy `.913`-`.999`, comfortably above the `.80` gate throughout.
**This resolves D-034's anomaly**: the mechanism itself is sound across
this whole range once `alpha` is not held fixed across `N`. **This is
not yet a floor recommendation**, for two disclosed reasons: (1)
candidacy rate — how often a cross-branch pair even gets evaluated at
all — is not guaranteed to stay comfortable everywhere the fitted curve
interpolates; it drops to `.688` at the largest held-out `N` (`725`)
even though the fitting procedure required `>= .80` at the six known
points. (2) This is still evidence from the isolated, no-noise overlap
DGP, not a composed, screening-realistic network. See D-035.

**Stage 4c cascading-error stress test — no contamination effect
detected, with two disclosed caveats.** The R6a milestone's own
precondition: does a wrongly-confirmed noise variable propagate into
wrongly pruning an unrelated true edge? Tested on Stage 1's asymmetric
`strong` triangle plus 0 vs. 5 pure-noise columns (paired, identical
triangle draw per replicate), `N=[100,200,300]`, both engines on
identical data. **Result: the sequential engine's weak-edge wrong-
pruning rate is bit-for-bit identical with and without noise at every
tested cell** — a noise column is implicated in fewer than `.6%` of
wrong prunings (the joint requirement — spurious correlation with
*both* endpoints of the target pair — is a much stronger filter than
expected). The conservative engine's wrong-pruning rate *improves* with
noise (contamination breaks clique validity, disabling DPI, which helps
here since the untested edge is genuinely real). **Do not read this as
"cascading error is not a risk for this engine" in general** — two
specific limits: the baseline wrong-pruning rate here is already high
(`59%`-`84%`, from weak-signal detection power alone), which could mask
a smaller contamination effect; and only one DGP and one contamination
pathway (independent noise, not noise correlated with a real node) was
tested. See D-036.

**Stage 4h composed pipeline, p=15, with noise — the headline result of
this entire investigation (D-026 through D-037).** Embedded in D-018's
exact `p=15` noisy network, using Stage 4g's fitted `alpha(N)` formula
unmodified: **`N=625` and `N=700` both PROCEED with composite overlap
TPR `.986` and `.998` — higher than the conservative engine's own
`N=1500` PROCEED (`.817`), using less than half the sample size.**
Candidacy (`.84`-`.89`) and conditional accuracy (`.984`-`.997`) both
comfortably high — a genuine result, not D-032's non-detection
artifact. Zero contamination detected. **`N=750` itself is not resolved
by this evidence**: Stage 4g's fitted formula predicts a *negative*
alpha exactly at `N=750` (a real bug in that formula's own boundary
behavior, since `750` was one of Stage 4g's *fitting* points, never
itself held out and validated) — every `N=750` replicate errored rather
than testing anything real. Do not read `N=750` as REASSESSed on the
merits; it is an open, cheaply-fixable gap (re-fit Stage 4g's formula
with `750` held out and re-verified), not a negative finding. See
D-037. **This result, combined with Stage 4c's cascading-error caveats
(no contamination detected, but not stress-tested at this network
size), is the strongest evidence yet that the sequential engine is a
real, usable alternative for this weak-signal shape — but still not a
user-facing recommendation** on its own; the R6a milestone's
preconditions are now substantially met, and the natural next steps are
testing a broader shape/signal-strength sweep before any such
recommendation.

**Stage 4i attempted repair — the `N=750` gap is not a simple fitting-
set fix; it relocates rather than closes.** Re-fit the overlap `alpha(N)`
formula with `N=750` moved from the fitting set to the held-out
validation set, adding a new self-check that the refit formula is valid
at its own fitting points (it was — the self-check passed cleanly at
all five). **But the refit curve is measurably steeper than Stage 4g's
original** (`inverse_sqrt` parameters `(-0.358, 9.577)` vs. `(-0.344,
9.307)`), so its zero-crossing lands earlier, between `N=700` and
`N=725` instead of between `N=725` and `N=750`. **`N=725`, previously a
clean PROCEED under Stage 4g's original formula, now fails too** —
alongside `N=750`, still negative and slightly more so than before
(`-.0083` vs. `-.0044`). Net effect: **the sequential engine's validated
overlap `alpha(N)` range is now `[400, 725]` under Stage 4g's original
formula** (not `[400, 750]` as previously scoped) — `N=725` and `N=750`
are both explicitly unvalidated for any fitted `alpha` and must not be
used with one. For `N=750` specifically, the right artifact is a
**lookup value**, not a fitted extrapolation: Stage 4e's own
already-validated point (`alpha=.005`, meeting both the accuracy and
candidacy floors) remains directly usable if `N=750` evidence is needed.
Genuine coverage near `N=700`-`750` would require new simulated points
densely spaced inside that specific range to constrain the curve near
its crossing — not a re-selection of which existing points to fit on.
Stage 4h's accepted `N=625`/`700` results (D-037) are unaffected, both
sitting safely inside the narrower `[400, 725]` range. See D-038.

**Stage 4j densely-spaced refit — the gap narrows substantially (`~4x`)
but does not fully close.** Adding four new fitting points densely
spaced inside `N=700`-`750` (`710, 720, 730, 740`, freshly simulated,
`2,000` replicates each) and re-fitting on all ten points moved the
zero-crossing from between `N=700`/`725` (Stage 4i, D-038) to between
`N=735`/`745`. **`N=725` — Stage 4i's casualty — is fully restored**,
PROCEEDing with a comfortable margin (candidacy `.786`, accuracy
`.998`), alongside `705, 715, 735`. Only `N=745` (held out) and `N=750`
(now itself a fitting point, caught by the fitting-point self-check)
still produce an invalid negative alpha. **Net effect: the sequential
engine's validated overlap `alpha(N)` range is now `[400, 735]`** — an
improvement over both Stage 4i's and Stage 4g's `[400, 725]`. The
unresolved gap has narrowed from `50` units (`700`-`750`, Stage 4g's
original overbroad claim) to `10` units (`740`-`750`), `1.3%` of the
full validated range. Candidacy rate falls steadily across the dense
region (`.881` at `400` down to `.696` at `735`) even as accuracy keeps
rising — the same `alpha`-vs-candidacy tension `alpha(N)` exists to
manage, now visibly approaching its steep end, not a new artifact.
**For `N=740`-`750` specifically**, Stage 4e's own lookup value for
`N=750` (`alpha=.005`) remains the right fallback (per D-038); closing
this final, narrow gap with a formula would need points spaced even
more densely inside `[740, 750]` itself, at increasing simulation cost
for now-marginal practical value — likely not worth pursuing unless a
specific downstream use needs exactly this narrow range. Stage 4h's
accepted `N=625`/`700` results (D-037) remain unaffected throughout.
See D-039.

**Stage 4k shape/signal-strength sweep — overlap's miscalibration does
not generalize; D-012's existing formula works unmodified for every
other shape tested.** Swept `3` motifs (chain, fork, hub-2-children) x
`4` signal strengths (`0.30`-`0.70`, bracketing overlap's own `~.135`
correlation from both sides) x `3` sample sizes (`750, 1000, 1500`,
inside D-012's own validated range) — `36` cells total, **all PROCEED**,
reusing D-012's already-frozen `alpha(N)` formula with no new fitting
at all. Candidacy `.86`-`1.0`, conditional accuracy `.82`-`.94`,
comfortably clear of the `.80` floor everywhere, though six cells (all
at `N=750`, the tightest point) have margins under `.05`, smallest
`.022` (hub, `strength=0.70`). **Chain, fork, and hub(2-children) are
now validated for the sequential engine's isolated conditioning at `N
in [750, 1000, 1500]` across this strength range, using the same
formula long used for the conservative engine — no shape-specific
recalibration needed.** This substantially strengthens the reading that
overlap's own D-032-D-039 saga was a property of its specific DGP
(five-variable, dual-triangle topology), not a systemic weak-signal
issue with the engine. **Still not sufficient alone for a user-facing
recommendation**: this sweep is isolated-only (no screening, no noise,
no composed pipeline), and Stage 4c's cascading-error stress test
covered only the triangle shape, not these three. See D-040.

**Stage 4l composed/noisy chain-fork-hub — the isolated-vs-composed gap
closes with no new fitting.** Embedded chain/fork/hub(2-children) in a
new, noisy `p=15` network (`96` null pairs, `6` noise columns,
deliberately distinct from Stage 2d's own overlap-based `p=15` DGP) at
`strength in [0.30, 0.50]`, `N in [750, 1000, 1500]` — **all `6` cells
PROCEED**, reusing D-012's already-frozen `alpha(N)` formula unmodified,
the exact same formula and values Stage 4k already validated in
isolation. All indirect TPRs `.86`-`.94`, comfortably clear of `.80`;
true-edge FPR exactly `0` throughout; final false-edge rate always
below screening's own rate. **Unlike overlap (Stage 4h), which needed
Stage 4g's dedicated per-shape recalibration to PROCEED in the composed
setting (D-037), chain/fork/hub required no new fitting at all** — the
isolated result (D-040) transferred directly. Combined with D-040, this
substantially satisfies the R6a milestone's broader shape/signal-
strength precondition for chain, fork, and hub(2-children): **`N in
[750, 1000, 1500]`, `strength in [0.30, 0.50]`, composed and noisy, is
now validated for these three shapes using the same `alpha(N)` formula
long used for the conservative engine.** The one remaining precondition
before a user-facing recommendation for these shape types is Stage 4c's
cascading-error stress test, tested only on the triangle shape so far.
Overlap's own dedicated `alpha(N)` treatment remains necessary and
unaffected — this result confirms overlap was the DGP-specific
exception, not evidence the whole engine needs shape-specific tuning.
See D-041.

**Stage 4m cascading-error stress test for chain/fork/hub — a real,
small effect, unlike Stage 4c's clean null on the triangle.** Extended
Stage 4c's exact mechanism (paired same-draw noise injection, both
engines, quantify not gate) to chain, fork, and hub(2-children) at a
deliberately weak, uniform `strength=0.15`. **Unlike D-036's clean null
on the triangle, the sequential engine's wrong-prune-rate delta
(`noise=5` minus `noise=0`) is positive in `17` of `18` tested cells and
never negative** (sign-test `p<.001`) — small in absolute magnitude
(mean `.0017`, max `.0045`) but statistically robust and mechanistically
confirmed (a noise column is specifically implicated in `.07%`-`1.6%` of
wrong prunings under contamination). The conservative engine shows the
mirror pattern predicted (delta always negative, `-.0012` to `-.0070`,
since noise breaks clique completeness and disables DPI, letting real
edges pass through unpruned) — same direction as D-036's own Q2 result.
**Likely explanation for the divergence**: Stage 4c's triangle has two
strong anchor edges that reliably out-rank noise columns for "confirmed
neighbor" status, structurally shielding its weak tested edge; chain/
fork/hub's uniformly weak condition removes that shield, giving noise a
real (if small) chance to be selected as a conditioning variable ahead
of a genuine edge. **D-036's reassuring near-zero finding should not be
generalized past the triangle's own asymmetric design** — for uniformly-
weak-signal shapes (the overlap shape's own historical difficulty
included), a small, non-zero cascading effect should be assumed present
until measured otherwise. No motif (chain/fork/hub) is meaningfully more
susceptible than the others. Combined with D-040/D-041, chain/fork/hub
now have every named R6a milestone precondition addressed — not with a
clean "no risk" verdict like the triangle, but with a specific,
quantified, small risk, disclosed rather than assumed away. See D-042.

**Stage 4n cascading-error stress test for overlap — clean null on
noise (like the triangle, not chain/fork/hub), but a new, noise-
independent structural finding.** Extended the same mechanism to
overlap's own DGP, pooling wrong-pruning across its `6` true direct
edges. **On the noise axis specifically, overlap matches Stage 4c's
triangle, not the paragraph above's own prediction that overlap's
weak-signal history would put it in Stage 4m's exposed regime**: the
sequential engine's wrong-prune-rate delta is `~0.0000` at every tested
cell — a correction to that prediction, made transparently. The reason:
this charter's `6` direct edges are moderate-strength (`-0.25`), not
uniformly weak like Stage 4m's deliberately constructed `0.15`
condition — the "uniformly weak" label describes overlap's *cross-
branch, indirect* correlation (`~.135`), not its direct edges, and it
is edge strength specifically that governs this noise pathway. **A new
question this charter added (Q4) found something the noise axis
couldn't**: even with **zero** injected noise, `2%`-`6%` of wrongly-
pruned direct edges implicate a node from the *opposite* triangle —
overlap's own shared-node structure providing a plausible wrong
"confirmed neighbor" independent of any noise, a pathway with no analog
in either prior cascading-error charter (neither DGP has a second,
structurally-connected cluster). **Overlap's headline result (D-037) is
not threatened by noise-driven cascading error** (now measured and
negligible), but this small, structural, noise-independent risk should
be disclosed alongside it for any shared-node/multi-cluster shape.
Combined with D-037-D-042, overlap now has every named R6a-adjacent
cascading-error question answered as thoroughly as chain/fork/hub's.
See D-043.

**Stage 4p canonical benchmark — a public-facing side-by-side table,
with two disclosure-worthy findings, not a change to any prior
verdict.** Both engines, both `p=15` networks (overlap-based, hub-
based), one shared alpha-selection rule (D-012's general formula, not
overlap's own specialized one), across `N=[400,500,600,750,1000,1500]`.
Hub-based network: clean (one isolated, thin miss at `N=500`). Overlap-
based network surfaces two things worth knowing before citing this
table: **(1)** the conservative engine REASSESSes at every tested `N`
including `1500` (`.791` vs. D-018's own `.817`) — not a contradiction,
since D-018's own `N=1500` margin was already thin (`.017` above the
gate) and this charter draws an independently-seeded sample; the newly-
visible dip across intermediate `N` (worst at `750`) is itself new
information D-018's own two-point test never had. **(2)** the sequential
engine PROCEEDs at every tested `N` including `400`-`600`, but this
uses the same coarse, pooled TPR metric D-032 already showed can be
inflated by non-detection — this result should **not** be read as
beating or superseding Stage 4g/4i/4j's own properly-decomposed
`[400, 735]` finding, which remains the trustworthy source for that
specific shape/engine combination. See D-045; `docs/stage4o_recommendation.md`'s
own per-shape verdicts are unaffected.

**Stage 4q repair — a confident conservative floor at `N=1750`, and the
composite-metric gap confirmed small.** Directly addressed both D-045
findings. **Part A**: the conservative engine on the overlap-based
`p=15` network PROCEEDs with real margin at `N=1750` (`.839` TPR,
`.039` above the gate) and `N=2000` (`.850`, `.050` above) — margin
*increasing* with `N`, the expected shape of a genuine floor.
**`N=1750` is now the recommended threshold for the conservative engine
on this shape**, superseding `N=1500` (`.817`, only `.017` margin,
D-018) as the practical recommendation without retracting that earlier
result. **Part B**: re-scored Stage 4p's own sequential-engine-on-
overlap draws (bit-identical seeds and alpha) with the proper
candidacy/conditional-accuracy decomposition. The non-detection gap
D-045 flagged is real but small and shrinks toward zero as `N` grows —
largest at `N=400` (composite `.869` vs. decomposed `.858`, gap
`.011`), essentially zero by `N=1000`-`1500` as candidacy rate
approaches `1.0`. **Conditional accuracy clears `.80` at every tested
`N`**, confirming Stage 4p's own composite-TPR sweep was mostly
genuine, not primarily an artifact. See D-046.

Full context: `outline/information_network_technical_build_plan_v3_2026-08-30.md`.

## Comparator benchmarking (Stage 5a, R6): MINT vs. EBICglasso

**First R6 charter — descriptive, not a validation gate.** MINT's
conservative engine occupies its own niche on the two composed, noisy
`p=15` shapes already characterized above (chain/fork/hub;
shared-node overlap): its per-edge screening step (Fisher-z evidence
before DPI conditioning) prunes noise-driven false edges that
EBICglasso's single global L1 penalty (`gamma=.5`, `qgraph`'s own
default) does not. On `chain_fork_hub`, MINT clears `F1>=.90` already
at `N=400` and keeps improving (`.954` to `.966` by `N=1750`);
EBICglasso never clears `.90` anywhere on the `[400, 1750]` grid,
plateauing around `F1~.84`-`.86` (precision `.73`-`.76` vs. MINT's
`.92`-`.94` — both have perfect recall, so the gap is entirely
EBICglasso retaining false edges). `overlap` shows the same pattern at
smaller magnitude (MINT `.910`-`.959`; EBICglasso flat `~.879`-`.889`).
On the noise-free, three-node triangle fixtures (balanced/moderate/
strong), **the two methods are indistinguishable** — both floor at
`N=400`, no material gap at any tested strength, the expected result
on a DGP with no nuisance variables for MINT's screening step to help
with. EBICglasso's own fit is also `2`-`3` orders of magnitude slower
per replicate than MINT's (unplanned finding, not a predeclared
metric, but directly supports the "moderate compute" niche language in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`
Section 22.2).

**Scope — do not overclaim.** This result is strictly Gaussian, both
methods on their own native assumption class; a genuinely differentiating
(assumption-violation) comparison is reserved for a future charter
contingent on Stage 8's nonlinear known-graph DGPs, not yet chartered.
Only the conservative engine was tested — the sequential/greedy engine
was excluded pending one general per-shape recommendation (Stage 4o's
own caveats are per-shape, not yet unified). MINT's `alpha(N)` here is
D-012's *general* formula applied uniformly across all five shapes
(including overlap, for which a specialized formula exists but was not
reproducible in the Stage 5a worktree — see D-047's own scope note),
mirroring Stage 4p's own precedent. See D-047 for full evidence and the
per-shape verdict table; `docs/stage5a_charter.md` for the frozen
charter and fair-comparison rules.

**Scope limitation, from Stage 5b/5c (D-048/D-049): MINT's advantage
over EBICglasso as `p` grows depends on using a `p`-adjusted screening
`alpha`, and even then is closer to flat than reliably growing.**
Appending extra noise columns to the same two shapes (multiplier
`1`/`2`/`3` of each shape's own native noise-column count, `N in {500,
1500}`) with MINT's screening `alpha` held **fixed** at `.001`
regardless of `p` found the F1 gap **shrinks** substantially as noise
columns increase (D-048) — traced to MINT's own precision declining
with `p` under a fixed `alpha`, while EBICglasso's own extended-BIC
criterion has a built-in `ln(p)` penalty that makes it automatically
stricter as `p` grows. **Re-running the identical sweep with a
`p`-adjusted `alpha(p)`** (a disclosed log-linear interpolation between
Stage 2's own two calibrated anchor points, `.001` at `p=15`, `.0001`
at `p=30`) fixed MINT's own precision decline — it now *improves* with
`p`, at every tested `dgp`/`N` — but did **not** cleanly restore a
growing gap either (D-049): three of four `dgp`/`N` series are now
roughly flat or slightly increasing, one (`overlap`, `N=1500`) still
declines beyond tolerance. **Read this as: MINT's own `alpha`-fixed
precision problem is real and fixable, but EBICglasso's own `p`-aware
penalty is also doing genuine, ongoing work, so the net gap-vs-`p`
relationship should be treated as roughly flat with shape/`N`-specific
variation, not as reliably growing in either direction**, until further
`p` values or shapes are tested. Neither D-047 nor D-048 is retracted —
both are valid readings of their own distinct MINT configuration (fixed
vs. `p`-adjusted `alpha`). `alpha(p)` is the better-tested
configuration going forward for any further `p`-varying R6 work. See
D-048 and D-049.

**Second axis, signal strength (D-050): MINT's advantage grows sharply
as effects get stronger — the cleanest result in the R6 arc.** Sweeping
strength `in {.3, .5, .7}` (noise held at native, `alpha(p)`
throughout) found the F1 gap **increasing at every one of the four
`(dgp, N)` series tested, no exceptions.** Mechanism: MINT's own
precision is roughly flat across strength, while **EBICglasso's own
precision collapses** as strength rises (e.g. `chain_fork_hub`,
`N=500`: precision `.882` at strength `.3` down to `.526` at `.7`) —
EBICglasso keeps roughly twice as many false edges at strong signal as
at weak signal. Recall stayed at `1.0` for both methods in essentially
every cell (one negligible exception, `.9999`), so — as in every prior
R6 charter — **the entire gap remains a precision, not a detection,
story: both methods find every real connection; EBICglasso just
returns a substantially noisier graph, especially when the true
effects are strong.** No mechanism for EBICglasso's own precision
collapse was tested here (flagged as a plausible hypothesis —
estimation-noise coupling under strong true correlations — for a
future diagnostic charter, not established). See D-050. This completes
the two-axis characterization (noise-count: D-048/D-049; strength:
D-050) `docs/stage5a_charter.md`'s own recommendation called for.

**Second incumbent, PC-algorithm skeleton comparison (D-051): on the
composed noisy networks, PC's F1 beats MINT's own — not just
EBICglasso's.** Reusing D-047's own exact draws (identical condition
seeds), the PC algorithm's skeleton phase (subset-conditioning
independence tests, `alpha=.01` fixed, no orientation phase implemented
at all — see `docs/stage5e_charter.md` for why that scope avoids the
entangled-with-direction-finding concern that applies to score-based
DAG learners) **beats MINT's own D-047 F1 on both composed noisy
networks, at every tested `N`.** `chain_fork_hub`: PC matches MINT's
perfect recall (`1.0`) and has strictly better precision at every `N`
(`.945`-`.950` vs. MINT's `.917`-`.939`) — PC dominates MINT outright
there, not a trade-off. `overlap`: PC's recall is marginally below
MINT's perfect `1.0` at low `N` (`.997`) but its precision is high
enough (`.97`+ vs. MINT's `.84`-`.93`) that PC's F1 still wins at every
`N`. This is not an artifact of favoring PC: MINT's own `alpha(N)` was
originally calibrated via truth-informed simulation on these exact DGP
shapes in earlier charters, while PC's `alpha=.01` is a generic
literature value unrelated to these specific networks — MINT had the
tuning advantage here and still lost on F1. **On the two weak-signal
triangle shapes (`moderate`, `strong` — each has one deliberately weak
true edge, partial correlation `-.12`/`-.08`), the position reverses:
PC's recall degrades substantially more than either incumbent's on the
identical DGP** (`triangle_strong, N=400`: PC recall `.720` vs. MINT
`.868` vs. EBICglasso `.953`), though D-047 already showed both
incumbents with imperfect recall there too — a difference of degree,
not a new phenomenon in kind. Plausible mechanism (not established): PC
removes an edge on the *first* conditioning subset that fails to reject
independence, an OR-rule across many tests that plausibly helps
precision (more chances to correctly detect a noise pair's
independence) at the cost of recall on weak true edges (more chances
for one underpowered test to wrongly declare independence). **Net
reading, corrected from this finding's initial framing: MINT's own
comparative niche on the composed noisy networks — this project's
primary DGP interest — is beating EBICglasso, not dominating incumbents
in general; PC beats MINT there on F1.** What remains in MINT's favor:
it still beats PC specifically on weak-edge recall, and remains
meaningfully faster than PC (`2`-`6x`, smaller than the `2`-`3`
orders-of-magnitude margin over EBICglasso). See D-051 and its own
same-day correction.

**Diagnostic follow-up (D-052): a concrete, measured, partial
explanation for D-051's precision gap.** `compose_screen_then_prune`'s
own documented scope — DPI conditioning only examines validated 3/4/5-
node clique candidate components; every other component (including an
isolated two-node component) passes through into the final graph
completely untested — accounts for a **real, structural share of
MINT's own false positives**: `~28`-`40%` on `chain_fork_hub`
(PARTIAL, stable across `N`, no clean trend), and the **majority**
(`.77`-`.82`) on `overlap` at `N in {400, 500, 600, 750}`, dropping
below the material threshold at `N in {1500, 1750}` (`.49`, `.46`).
`overlap`'s own larger passthrough share lines up with its own larger
MINT-vs-PC F1 gap in D-051 — a coherent, if not independently proven
causal, pattern. This is a partial, not complete, explanation (DPI's
own examined-and-wrongly-retained decisions still contribute on both
shapes), and identifies a concrete candidate for a **future
implementation charter** — extending DPI's conditioning to non-clique
or smaller components — which would need its own fresh false-edge-rate
and recall validation before any claim it improves precision safely.
Not attempted or authorized by this diagnostic charter. See D-052.

**Scope limitation, data type: continuous only — mixed/discrete data
support is unvalidated, reserved for future work.** Every DGP validated
anywhere in this project (Stage 0 through Stage 5d) is continuous
Gaussian, and the estimator behind MINT's bivariate association step
(KSG-1 mutual information, `k=20`) is specifically a continuous-data
estimator — its nearest-neighbor-distance computation is unreliable on
binary, ordinal (e.g. Likert-scale), or count data without swapping in
a different estimator built for discrete or mixed variables (such
estimators exist in the literature but are not implemented or tested
here). Mutual information as a general quantity is not restricted to
continuous data, but that is a claim about the theory, not about this
codebase: MINT-as-built has never been run against a discrete or mixed
DGP, so no operating range exists for that setting. Treat this as an
explicit, named limitation in any paper claim about MINT's data-type
coverage — do not claim binary/ordinal/count support without a
dedicated future charter (new estimator, new DGPs with known discrete
structure, the same falsification discipline as every other
mechanism) validating it first.

## mi-native track: conditioning-set architecture (Stage 6a, D-053)

**Branch note**: as of 2026-09-01, `main` is tagged
`v1-partial-correlation-baseline` and frozen as the complete,
validated Gaussian/partial-correlation MINT (R1-R6 above). A separate
branch, `mi-native`, carries forward development of a genuinely
MI-based mechanism (KSG-1 is validated bivariate-only, Stage 0; the
live pipeline through `v1-partial-correlation-baseline` uses closed-form
Fisher-z tests throughout, not MI — see D-003's own disclosed scope
note). This section tracks `mi-native`-only findings.

**Stage 6a (D-053) — conditioning-dimension requirement, no new
estimator yet.** Before building a conditional-MI estimator, this
charter tested whether DPI's own conditioning-set *architecture* (not
its estimator) needs to change, using the existing Fisher-z primitive
as the testbed. Finding: a PC-style growing-conditioning-set search
(size 1, escalate only if nothing prunes, run on MINT's own screened
candidate graph) **matches or beats full-component conditioning's own
F1 at every tested N on all five shapes, with zero measured recall
cost anywhere** — including the composed noisy `p=15` networks, where
precision improves substantially (`overlap`: `.84`-`.93` to
`.95`-`.97`) with recall staying at exactly `1.0`. Unlike PC itself
(D-051), this design does not trade recall for precision, plausibly
because it only ever runs on pairs that already passed MINT's own
screening step first. **Dimension requirement for `mi-native`'s own
future estimator**: most decisions (`55`-`97%` depending on shape)
resolve at conditioning size `1`, but the composed networks show a
real minority needing size `3` or more, with a measured, non-trivial
tail whose true dimension exceeds this charter's own disclosed search
cap of `4` (`~1-3%` of candidate edges on the composed networks hit
that cap without resolving). **A single-variable conditional-MI
estimator (e.g. Runge 2018) is necessary but not sufficient** — the
future estimator-validation charter must support multivariable
conditioning (`|S| >= 3`) from the start, or explicitly characterize
the accuracy cost of whatever cap it chooses. See D-053. No production
pipeline change was made or authorized by this charter.

**Stage 6b (D-054) — CMIknn estimator, first-pass validation: point
estimate and power confirmed, Type-I error control inconclusive (not
disconfirmed) at this replicate count.** `mintnet.mi.cmiknn` (Frenzel
& Pompe 2007, generalizing the validated bivariate KSG-1 formula) with
a local-permutation significance test (Runge 2018) was validated
against a known closed-form Gaussian reference across `|S| in
{0,1,2,3}`. **`|S|=0` matches the existing validated bivariate
estimator bit-for-bit** (not approximately) on identical data — the
new estimator's own base correctness is confirmed, not assumed.
**Power is strong and scales correctly with `N`**: `100%` rejection at
`alpha=.05` for `|S| in {0,1,2}` at every tested `N in {300,500,750}`;
`|S|=3` (hardest case) climbs `74% -> 98% -> 100%` across that same
`N` range. **Type-I error control formally REASSESSed against the
frozen gate's own strict bands, but every out-of-band observation was
checked directly with an exact binomial test and none reached even
`p<.05` against its own nominal rate** — with only `50` validation
replicates (this run's own disclosed, timing-driven scope reduction
from the charter's own `500`), the evidence cannot distinguish
correct calibration from mild over-liberality. **Do not read this as
a confirmed defect in the local-permutation construction** — read it
as "needs more replicates to resolve," the concrete, already-scoped
next step (same `N`/`k`/`k_perm`/`B`, replicate count only increased).
`mi-native` remains blocked from composing this into any retain/prune
mechanism until a replicate-count follow-up resolves Type-I error
either way. See D-054.

**Stage 6c (D-055) — local-permutation test's Type-I error control is a
confirmed, replicated defect, not an artifact of replicate count.** The
follow-up D-054 called for (400 replicates/cell, not 50; Wilson 95%
CIs reported per cell; `k_perm in {3,5,10,20,adaptive}` swept
independently of `k_CMI`, fixed at `40`) came back **REASSESS with a
clear, non-noise pattern**, not the earlier ambiguity. `|S|=0`
(unconditional, no local-neighborhood matching) is close to calibrated.
**`|S| in {1,2}` are liberal at `alpha=.05` under every swept `k_perm`,
and the excess rejection rate does not shrink with `N`** (e.g. `kperm3`
at `|S|=2`: `.1175 -> .11 -> .11` from `N=150` to `N=750` — flat, the
signature of a real construction bias, not finite-sample noise).
`|S|=3` is the best-behaved conditional case, counter to the naive
expectation that higher-dimensional conditioning should calibrate
worse, not better — plausibly a DGP-density effect (overlapping-
triangles' own local neighborhood structure vs. the fork/hub fixtures'),
flagged as a pattern to investigate rather than a general claim.
**No `(k_CMI, k_perm)` regime in the tested grid controls Type-I error
across the full `|S| in {0,1,2,3}` range `mi-native` needs (D-053).**
**No CMI-based significance test in this codebase is validated for use
until this is resolved** — this is a harder block than D-054's, since
D-054 left open the possibility that more replicates alone would
confirm calibration; that possibility is now closed. The most likely
locus of the defect is `mintnet.mi.cmiknn._local_permutation`'s own
matching construction (already disclosed in its own module docstring
as unverified against Runge (2018)'s reference implementation), not a
tunable parameter within that construction. See D-055 for the full
per-cell evidence and next-step priority order.

**Correction (Stage 6d, superseding this paragraph's own speculation
above)**: the "`|S|=3` calibrates better because it's a denser DGP with
less local-neighborhood exhaustion" explanation was checked directly
(`scripts/measure_permutation_exhaustion.py`, requested by independent
peer review before trusting the fix below) and found **wrong** —
exhaustion rate actually *increases* with `|S|` (`s3_null` has the
highest rate of the three conditions, not the lowest). The `|S|`
gradient in D-055's results is not explained by exhaustion frequency
alone; left as an open, disclosed question, not resolved.

**Stage 6d (D-056) — local-permutation construction fixed to match
Runge/tigramite's own reference implementation; PROCEED.** Comparing
`mintnet.mi.cmiknn`'s shuffle directly against
`tigramite.independence_tests.cmiknn.CMIknn`'s own
`get_shuffle_significance`/`get_restricted_permutation` found three
discrepancies, now fixed: self-inclusive Z-neighbor lists (was
excluded), Chebyshev distance for the Z-neighbor query (was Euclidean),
and — the likely primary cause of D-055's finding — reusing the
last-tried neighbor on local exhaustion rather than falling back to a
uniformly random point from the entire dataset (which could be
arbitrarily far in Z-space, corrupting the local structure the shuffle
exists to preserve). Re-running Stage 6c's own identical design (same
grid, same 400 replicates/cell, same gate) against the fix: **`k_perm=3`
is defensible across every tested `N in {150,300,750}` x `|S| in
{1,2,3}` x `alpha in {.05,.01}` cell (18/18)** — D-055's own worst cell
(`kperm3`/`s2_null`, flat `.11`-`.1175` against a `.05` target,
unmoved by `N`) is now `.0325`-`.0525` across that same range under the
identical label. `k_perm=10` is also fully defensible; `k_perm in
{5,20,adaptive}` each have scattered, non-systematic misses and are not
the selected default. **`mi-native` now has a validated, calibrated
significance test** (`k_CMI=40`, `k_perm=3`) — the block from D-055 is
lifted. See D-056.

**Stage 6d Stage C (D-057) — power confirmed; `|S|=3` needs `N>=750`.**
At the calibrated setting (`k_CMI=40`, `k_perm=3`): **100% power at
`|S| in {0,1,2}`** for both `N=300` and `N=750`, both `alpha in
{.05,.01}`. **`|S|=3` (overlapping-triangles DGP, the hardest case)
needs `N=750`, not `N=300`, for reliable detection**: `77.5%` power at
`N=300`/`alpha=.05` (just under the `>=.80` threshold) climbing to
`99%` at `N=750`; `50%` at `N=300`/`alpha=.01` climbing to `95%` at
`N=750`. This matches D-054's own earlier finding for `|S|=3` almost
exactly (`74% -> 98% -> 100%` across `N=300/500/750` there, under the
pre-fix construction) — consistent across two different local-
permutation constructions, so this is a genuine property of detecting
a direct edge at conditioning depth `3` on this DGP, not a construction
artifact. **Operating-range note**: budget `N>=750` wherever `|S|=3`-
depth conditioning is expected to matter for edge detection at
`alpha=.05`; `N=300` is borderline for that specific case only (fine
for `|S| in {0,1,2}` at either `N`). This closes the Stage
6b/6c/6d estimator-validation arc — `mi-native` may now plan the
Stage-1-equivalent composition charter (D-053/D-054/D-056's own named
next step), reusing Stage 6a's growing-subset DPI architecture and
this calibrated estimator/test pair. See D-057.

**Stage 7 isolation tier (D-059, revised after independent peer
review) — REASSESS: a proven structural conflict between the gate's
two criteria at this signal strength, not a grid-resolution issue and
not (yet) a fixable tuning problem.** The first Stage-1-equivalent
composition attempt (`R=500`, `N in {750,1500}`, calibrated
`k_CMI=40`/`k_perm=3`) found no eligible development alpha pair.
Chain/fork pruning rate tracks `1 - alpha` almost exactly (confirming
D-056/D-057's calibration generalizes to these new DGPs), which
requires `alpha <~ .2` to meet the `>= .80` TPR gate. The `strong`
triangle family's own FPR does not clear the `<= .10` gate anywhere
below `alpha = .5` (`.241`/`.187`/`.142`/`.084` at `alpha=
.1/.2/.3/.5`) — by which point chain TPR has collapsed to `.543`.
**No `alpha` in `(0,1)` satisfies both constraints simultaneously**;
a finer alpha grid cannot fix this. The underlying cause: the
`strong` family's third edge has true Gaussian conditional MI of only
`~0.0032` nats (partial r `-0.08`) — CMIknn pays a real, expected
efficiency cost relative to the analytically-correctly-specified
Fisher-z test at this near-null Gaussian alternative, not a defect.
`mi-native` remains blocked from any Stage-1-equivalent composition
charter until a dedicated power-curve/operating-frontier charter
(sweep partial-correlation strength finely, several `N`, calibrated
estimator held frozen, overlay the `1-alpha` null constraint) maps
where — if anywhere — a feasible operating point exists; retuning the
estimator against this one fixture before that mapping exists risks
overfitting the tuning to a validation target. See D-059's own
same-day revision for the full derivation.

## Maintenance

Add a row (or update an existing one) whenever a new charter validates
(or invalidates) a component's autonomous-use range. Stage 2 and later
will each need their own entries once chartered.
