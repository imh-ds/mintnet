# Stage 4h Charter: Composed Pipeline with Noise (Sequential Engine, p=15) (R6h)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

Every Stage 4 charter so far has tested the sequential engine on
isolated, noise-free DGPs — the same deliberate scoping Stage 1
mechanism charters used before Stage 2 embedded them in a real,
screening-realistic network. This charter is that step for the
sequential engine, mirroring `docs/stage2d_charter.md`'s own role after
`docs/stage1L_charter.md` precisely: **reuse an isolated-mechanism-
validated `alpha` rule unmodified, in a full, noisy `p=15` network, as
an explicit hypothesis to test — not an assumption.**

This is the charter the whole overlap-shape sub-investigation
(D-026 through D-036) has been building toward: does the sequential
engine, embedded in the exact same realistic network D-018 REASSESSed
on at `N=750`, actually PROCEED where the conservative engine did not —
using the alpha(N) formula Stage 4g fit and validated on the isolated
shape, not a newly re-derived one?

**Scope discipline, stated explicitly.** Stage 4g's fitted formula is
validated only for interpolation within `N in [300, 750]`
(`docs/stage4g_charter.md`'s own scope). This charter therefore does
**not** test `N=1500` — extrapolating the fitted formula beyond its
validated range to chase D-018's second comparison point would violate
the exact discipline this project has repeatedly insisted on (D-012's
own `[700,3000]` scope note, Stage 4g's own `[300,750]` note). `N=1500`
under the sequential engine remains untested and unclaimed after this
charter; a future charter would need its own held-out validation
extending Stage 4g's fit before testing there.

## Data-generating process

Identical to `docs/stage2d_charter.md`, reused unmodified for direct
comparability against D-018: `p=15` — chain (`0-2`), measured fork
(`3-5`), shared-node-overlap motif (`6-10`, node `8` shared), 4 noise
columns (`11-14`). Ground truth: 16 true candidate pairs, 89 null pairs,
10 true direct edges, 6 indirect edges (chain 1, fork 1, overlap 4).

**`N = [625, 700, 750]`** — three of Stage 4g's own already-validated
held-out points (all strictly within `[300, 750]`), with `750` as the
primary comparison point against D-018's own REASSESS. `625`/`700`
extend the question downward within the already-validated range, not
beyond it. Master seed `20260830`, 2,000 replicates (development
0-999, validation 1000-1999) — matching Stage 2d's own scale.

## Mechanism

No code change. `mintnet.pipeline.sequential_screen_and_prune_detailed`
run on the **full 15-column data** each replicate — all `C(15,2)=105`
pairs ranked and processed together, not the isolated 5-node submatrix
Stage 4b/d/e/f/g tested. `alpha` at each `N` is the single value
predicted by Stage 4g's fitted formula (`mintnet.experiments.
stage4g_fit`), reused exactly as fit — no new selection step, mirroring
Stage 2d's own reuse of D-012's formula.

## Selection and gate

Identical four-part gate to `docs/stage2d_charter.md`, on validation
replicates:

1. Chain indirect-edge TPR `>= .80`.
2. Fork indirect-edge TPR `>= .80`.
3. Overlap indirect-edge TPR `>= .80` (pooled across the 4 cross-branch
   pairs — the same composite definition D-018 used, for direct
   comparability).
4. True-edge retention FPR `<= .10`.
5. Final false-edge rate (fraction of the 89 null pairs wrongly present
   in the final graph) does not exceed the engine's own screening-stage
   false-edge rate by more than `.01`.

**PROCEED** for a given `N` only if all five hold with no recorded
error. **REASSESS** otherwise.

**Required, non-gating decomposition — do not repeat D-032's mistake.**
Alongside the composite overlap TPR above, separately report, for the 4
cross-branch pairs specifically: candidacy rate (fraction that clear
initial screening at all) and conditional accuracy (correctness among
candidates only) — Stage 4e/4g's own corrected metric — so a PROCEED or
REASSESS here is never read through the same non-detection-conflation
lens D-032 found. Also report, for each cross-branch pair when
wrongly retained, which node index it was tested against (mirroring
Stage 4c's contamination diagnostic) — with 4 noise columns and 8 other
network variables now present, this is the first test of whether the
cascading-contamination pathway Stage 4c found negligible in isolation
behaves differently inside a realistic, larger candidate pool.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (per-pair candidacy/confirmation/
tested-neighbor detail for the 4 cross-branch pairs, pooled metrics for
every category), aggregate metrics, the per-`N` decision table, a
direct comparison table against D-018's own recorded numbers at
matching `N` (`750`), report, and figures.

## Consequences

If PROCEED at `N=750`: this is the first direct, composed-pipeline
evidence that the sequential engine's alternative composition strategy
achieves at `N=750` what the conservative engine needed `N=1500`-`1750`
for, on the exact DGP and signal strength this whole investigation has
tracked since D-018. This still does not authorize a user-facing
default-engine recommendation — Stage 4c's own caveats (this result
type has not been stress-tested for cascading error *inside* a network
this size, only in the earlier isolated triangle test) and a broader
shape/signal-strength sweep remain open before that.

If REASSESS at `N=750`: this would mean the isolated-DGP evidence
(Stage 4b/g) does not transfer once embedded in a realistic screening
pool — the same kind of composition-context gap D-017/D-018 found for
the conservative engine's own mechanism, now discovered for the
sequential engine's alpha calibration specifically rather than its
conditioning logic. This would be a genuinely informative negative
result, not a failure to explain away: it would mean Stage 4g's fitted
formula needs its own re-derivation inside a composed network, not
merely reuse, before the overlap-shape story can be closed out.

Either outcome should be read alongside the disclosed candidacy/
conditional-accuracy decomposition and the contamination diagnostic
above — a PROCEED driven by low candidacy (few cross-branch pairs even
evaluated) would not carry the same weight as one with both candidacy
and accuracy comfortably high, and this charter's report must say which
occurred, not just report the composite pass/fail.
