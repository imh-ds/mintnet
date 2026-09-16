# Post-Mortem: Search-Architecture Scaling Failure on Dense, Real-Shaped Networks (mi-native)

Date: 2026-09-16
Status: **Recorded finding — this is a post-mortem and forward-looking
policy document, not a charter.** It does not itself gate a
PROCEED/REASSESS decision; it records why an entire methodological
direction is being deprioritized, and sets binding requirements for
everything chartered after it. See `docs/decision_log.md` D-091 for
the pointer entry.

## 1. Verdict, stated plainly

**The current mi-native search architecture cannot be used on any
network that is a single, densely-interconnected connected component
of realistic size.** This is not a tuning problem, not a hardware
problem, and not fixed by sharding, parallelism, or more patient
infrastructure. It is a structural defect in how the search decides
what to test, and it was never exposed earlier because every DGP this
project has evaluated since Stage 1 was deliberately constructed to
avoid triggering it.

Measured directly (Stage 10a, `organic_network`, 18 nodes, 21 true
edges, a single connected component): five of six pair-batch shards,
each responsible for only about a sixth of the 51 candidate pairs,
took **2h36m, 3h44m, 4h25m, 4h54m, and 5h17m** respectively to
complete a single point-estimate search — no bootstrap, no rescue,
just the base discovery pass. A sixth shard exceeded 6 hours and was
cancelled unfinished. Summing the five completed shards alone already
exceeds **21 hours of compute for one single network model**, before
accounting for the shard that never finished. This is not a
back-of-envelope estimate; it is what actually happened, on an
18-node network — small by the standard of any real organizational,
social, or biological dataset this package would ever be pointed at.

## 2. The underlying technical defect

### 2.1 What the search actually does

`mintnet.pipeline.growing_subset_dpi_structured_density` (and its
Fisher-z ancestor, `growing_subset_dpi`, which it deliberately mirrors)
decides, for each candidate pair `(i, j)` that screening flags, which
other variables to condition on while testing whether `i` and `j` are
genuinely, directly related. The candidate conditioning variables — the
**pool** — are computed as:

```python
component = node_to_component[i]   # from connected_components(flagged)
pool = sorted(component - {i, j})
```

That is: **every other node reachable from `i` via any chain of
screened-in edges**, not merely the nodes `i` or `j` are themselves
connected to. The search then tries conditioning subsets drawn from
this pool, growing from size 1 up to `max_conditioning_size` (4
throughout this project), testing every combination at each size
before moving to the next.

### 2.2 Why this is fine for a small, disconnected motif and catastrophic for one connected network

For every DGP this project has evaluated through Stage 9 — the
isolated chain, fork, hub, triangle, and overlap motifs, and their
composed variants (`chain_fork_hub`, `overlap`) — the true
correlational structure was deliberately built as **several small,
disconnected components**, each with at most 5 nodes. In that regime,
"every node in the connected component" and "the nodes actually
relevant to this pair" are nearly the same set, because the component
itself is tiny. The pool size is bounded by construction, not by
anything the search itself does to keep it bounded.

The moment the true structure is **one single connected network** —
the shape any real dataset actually has — this equivalence breaks.
`organic_network`'s screened candidate graph forms **one connected
component of 15 nodes** (confirmed directly:
`connected_components(flagged)` returns exactly one component
spanning all 14 structural nodes plus a noise column that happened to
screen in). Every candidate pair's pool can therefore draw from up to
13 other nodes, not 2-3.

The search's own cost is combinatorial in pool size, capped at
`max_conditioning_size=4`:

| DGP | Worst-case pool size | Subset combinations tested (capped at size 4) |
|---|---|---|
| `overlap` (isolated motifs, largest component = 5 nodes) | 3 | `C(3,1)+C(3,2)+C(3,3) = 7` |
| `organic_network` (one connected component, 15 nodes) | 13 | `C(13,1)+C(13,2)+C(13,3)+C(13,4) = 1{,}092` |

That is a **~156x growth in worst-case combinatorial search space per
edge**, purely from connecting components together — with no change
to the actual local structure around any individual node. A node with
exactly the same real degree (4 connections) costs the same to search
whether it sits in a 5-node component or a 5,000-node one, **only if**
the pool is built from its own connections. Built from the whole
component instead, its cost scales with the size of everything it is
transitively reachable from, which for any real, non-trivial network
is unbounded in practice.

### 2.3 This was not a code bug — it was an unvalidated design assumption

`docs/validated_operating_ranges.md` (Stage 1k / D-015) explicitly
names this behavior as the validated mechanism: **"DPI conditioning on
all other nodes in a candidate component."** This is not a defect that
crept in unnoticed — it is the mechanism working exactly as designed
and exactly as validated. What was never tested, across ten stages and
dozens of charters, is what happens to "all other nodes in a candidate
component" once a candidate component is not a small, hand-built
motif but a real, single, densely-connected network. Every falsification
test this project ran was — by deliberate, otherwise-sound design —
structured so that a component's size and a node's local degree were
approximately the same number. That equivalence is what silently
carried an untested assumption through nine stages of otherwise
rigorous validation.

This is stated directly, not to assign blame, but because it is the
actual lesson: **the discipline of isolating one variable at a time
(the project's own stated methodology) has a specific, structural
blind spot for any defect whose cost scales with global structure
size rather than local structure size.** Small isolated motifs cannot
reveal that defect by construction, no matter how many of them are
tested, no matter how many sample sizes or DGP shapes are swept. Only
a test against one genuinely large, single connected component can
surface it. That test did not exist until Stage 10a — chartered nine
stages after the mechanism it eventually broke was first validated.

### 2.4 A second, related manifestation: unbounded per-unit cost in bootstrap-rescue

The same disease — a mechanism whose cost has no upper bound tied to
the actual size of the problem — also killed the full-repeat
bootstrap-rescue mechanism (D-088, D-090), independently of the pool
defect above. There, re-screening and re-searching from scratch on
every bootstrap resample meant one resample's cost could land
anywhere on a heavy right tail already disclosed at D-085 (`mean 377s,
max ~14,548s`) — and empirically, one resample finished in 43 minutes
while a second, nominally identical resample exceeded 6 hours without
finishing. **Two independent mechanisms in this project have now each
failed for the same underlying reason: an operation whose cost is not
provably bounded by the actual local size of what it's operating on,
tested only in a regime small enough that the lack of a bound never
mattered.** That is the pattern to guard against going forward, not
merely a property of one function.

## 3. Binding policy going forward

The following two gates are now mandatory for every future mi-native
charter. Neither is a suggestion; a charter that cannot clear both is
not eligible to reach a PROCEED decision, regardless of how well it
performs on any other measure.

### Gate 1 — No unbounded-cost mechanism proceeds, ever, regardless of infrastructure

**Any mechanism whose measured cost is not demonstrably bounded by a
function of *local* structure (a node's own degree, a pair's own
Markov blanket) — rather than *global* structure (network size,
component size, total candidate-pair count) — is disqualified from
proceeding, full stop.** This applies regardless of available compute,
sharding cleverness, or patience. A result that requires 30 hours, or
6 hours, or any similarly unusable amount of wall-clock time to
produce ONE network model is not a slow success; it is a failure to
clear this gate, and must be recorded and treated as such — REASSESS,
not "REASSESS for now, revisit with more infrastructure later."
Throwing more shards, more parallelism, or more GitHub Actions minutes
at an unbounded-cost mechanism does not fix it; it only delays
discovering that it was never fixed. This project already made that
mistake twice (D-088's first unsharded attempt, then its own
resample-level sharding retry) before recognizing it as a structural
problem rather than an infrastructure one.

### Gate 2 — No mechanism is considered validated for real use without a dense, single-connected-component test

**A charter that has only been tested against disjoint, small,
isolated motifs — no matter how many DGP shapes, sample sizes, or
replicates — has not established real-world validity and must not be
described or treated as production- or API-ready.** Every future
charter for a discovery or search mechanism must include, before any
PROCEED claim, a test against at least one single, non-trivial,
densely-interconnected connected component (not a disjoint union of
small motifs) at a size large enough that local degree and component
size meaningfully diverge. A mechanism that cannot complete correctly
and in bounded time on such a network is DOA for real use, regardless
of its performance on isolated motifs — isolated-motif performance
establishes only that the underlying statistical test is sound, never
that the search wrapped around it is usable.

## 4. Stage-by-stage disposition

Classification standard used below: **SALVAGEABLE (unconditional)**
means the component's own correctness does not depend on, and is not
exercised by, the broken pool-construction behavior — it would answer
the same question the same way even after the search architecture is
replaced. **ARCHIVE** means the component's own validated result was
produced by, or exists only to serve, the broken search architecture,
and must be re-derived from scratch (not merely re-checked) once a
replacement architecture exists. Nothing below is deleted from the
repository or the decision log — the record of how this was learned
stays intact — but nothing marked ARCHIVE should be cited as a
currently-trustworthy result or built upon further as-is.

| Stage(s) | Component | Disposition | Why |
|---|---|---|---|
| Stage 0 | Bivariate MI estimation (KSG-1) | **SALVAGEABLE** | A pairwise estimator; no conditioning-pool concept exists here at all. |
| Stage 1-2 (screening) | `compute_pairwise_screening_evidence`, `screen_uncorrected` | **SALVAGEABLE** | Pure pairwise marginal-correlation testing. Does not construct or use a conditioning pool; unaffected by how the search downstream decides what to condition on. |
| Stage 1 (`mi/structured_density.py`) | `local_permutation_test`, the structured-density conditional-independence estimator itself | **SALVAGEABLE** | Given a specific `(X, Y, Z)`, this correctly tests conditional independence. It has no opinion on how `Z` was chosen. The defect is entirely in the *caller's* choice of candidate `Z` sets, not in this test. |
| Stage 1k / D-015 | "Conditioning on all other nodes in a candidate component" (the pool design itself) | **ARCHIVE** | This is the mechanism now shown not to scale. Validated only ever at component size <=5; the validation itself never tested the assumption that "the whole component" stays small. |
| Stage 1L-2j (composed pipeline results, all `p<=30` rows in `validated_operating_ranges.md`) | Every composed-pipeline PROCEED/REASSESS decision | **ARCHIVE** | Every one of these was produced using components deliberately kept small (cliques of size 3-5). None of them tested, or could have tested, the scaling defect. Their numeric thresholds (`alpha(N)`, screening cutoffs) may or may not transfer once the pool design changes — this is unknown, not assumed either way, and must be re-derived, not inherited. |
| Stage 4-5 (`chain_fork_hub`, comparator benchmarking) | Composed disjoint-motif DGPs, EBICglasso comparison | **ARCHIVE** | Same reason: disjoint small components by construction, never stress-tested at connected scale. The comparator-benchmarking conclusion itself (does mint occupy a meaningful niche vs. EBICglasso) is now unsupported until re-run against a network the search can actually finish on. |
| Stage 6a (structured-density search introduced) | `growing_subset_dpi_structured_density`'s own architecture | **ARCHIVE** | This is the specific function containing the defect (Section 2.1). Everything built on top inherits the same unvalidated scaling assumption. |
| Stage 7e-7h (`degree=1` calibration, confidence-margin calibration) | D-063, D-076, D-085 | **ARCHIVE** | Each of these calibrated a threshold or a curve against `decisive_p_value`/`conditioning_size_used` outputs produced by the flawed search on small components. Once the pool design changes, the same pairs can produce different `decisive_p_value`s (a pool of `{8}` vs. `{8,9,10}` for the same edge is not the same search) — these calibrations do not carry over and must be re-run against the corrected search, not assumed to still hold. |
| Stage 8 (composed calibration) | `stage8c_composed_calibration` and related | **ARCHIVE** | Downstream of the same search; same reasoning as above. |
| Stage 9a-9d (bootstrap-rescue, full-repeat and localized alike) | D-077 through D-090 | **ARCHIVE** | Two independent reasons: (1) it is built entirely on top of the Stage 6a search architecture and inherits its unvalidated scaling assumption; (2) the full-repeat variant specifically was independently shown to have its own unbounded-cost defect (Section 2.4), regardless of the pool question. Rescue exists to cheaply resolve ambiguous decisions from a base search — with the base search itself unusable on real networks, rescue's own correctness is currently moot, not merely unproven. |
| Stage 10a | The `organic_network` DGP/topology itself (nodes, edges, precision matrix) | **SALVAGEABLE** | The fixture is a reusable stress test, independent of which search architecture is run against it. Keep it; it is the tool that surfaced this entire finding and is exactly the kind of test Gate 2 (Section 3) now requires for every future charter. |
| Stage 10a | Any *result* produced by running the current search against `organic_network` | **ARCHIVE** | REASSESS-on-cost, decisively confirmed (Section 1). No correctness claim was ever reached — the search never finished. |
| All stages | The falsification discipline itself (frozen charters, sequential decision log, disclosed corrections, sharded evidence generation, seed determinism) | **SALVAGEABLE (process asset)** | Nothing about this finding indicates the *process* of chartering, measuring, and disclosing honestly is broken — quite the opposite: that process is what surfaced this defect with a precise, named, reproducible cause instead of a vague "it's slow" complaint. The process stays; the specific search architecture it was applied to does not. |

## 5. What is actually left to build on

Stripped to only what Section 4 marks unconditionally salvageable:

1. **The statistical primitive is sound.** `local_permutation_test` correctly tests conditional independence given a specific conditioning set. This has never been called into question and does not need to be re-derived.
2. **Screening is sound and cheap.** Pairwise marginal correlation testing has no scaling defect of this kind and remains usable as the first filtering step for any network size.
3. **The `organic_network` fixture is a reusable, correctly-designed stress test** for exactly the property that matters now: a real, single, densely-connected structure with known ground truth.
4. **The engineering discipline (sharded evidence generation, deterministic seeding, disclosed corrections) is sound** and should be applied to whatever search architecture replaces the current one — that machinery is not what failed.

Everything else — every calibrated threshold, every PROCEED decision for a composed pipeline, the entire bootstrap-rescue arc — was built on an untested scaling assumption in the search architecture itself, and per the strict standard requested (not merely "probably fine" but unconditionally guaranteed to still hold), none of it clears that bar. It is archived, not deleted: it remains available as historical evidence of what small-motif behavior looked like, and as a baseline to re-compare against once a replacement search architecture exists, but it is not currently a valid claim about anything real.

## 6. What a viable next attempt requires

Not a new charter yet — a precondition for one. Any replacement search
architecture must, before any further evidence generation:

1. Build its conditioning pool from a pair's own local structure (its
   actual screened neighbors, in the manner of PC-algorithm-style
   constraint-based discovery) rather than the whole connected
   component, so that cost scales with local degree, not network
   size.
2. Be re-validated from the ground up against the small isolated
   motifs first (Gate 2 does not exempt small-scale testing — it adds
   a requirement, it does not remove the existing one), to confirm the
   new pool design does not silently change or break any correctness
   property the old one had for cases where the two designs agree.
3. Clear Gate 1 and Gate 2 (Section 3) against `organic_network`
   specifically, with real measured cost and correctness numbers, before
   any claim is made that the scaling problem is solved.

Until all three are satisfied, "the package works" is not a claim this
project has evidence for.

## 7. Files and functions an independent reviewer must read to get full context

Ordered by priority. An agent with no prior context on this project
should be able to reconstruct the entire finding from these alone,
without needing this conversation.

**The defect itself — read these first, in this order:**

1. `src/mintnet/pipeline/growing_subset_dpi_structured_density.py` —
   the broken search. The specific line is `pool = sorted(component -
   {i, j})` inside `growing_subset_dpi_structured_density()`. Read the
   whole function; the pool is used to build every candidate
   conditioning subset tested from size 1 up to `max_conditioning_size`.
2. `src/mintnet/pipeline/compose.py` — `connected_components()`, the
   function that produces `component` above. Confirms the pool is
   drawn from the *entire* screened connected component, not a node's
   own adjacency.
3. `docs/validated_operating_ranges.md` — the row for Stage 1k/D-015
   ("Multi-variable conditioning — DPI conditioning on all other nodes
   in a candidate component"). This is the documentary proof that the
   whole-component pool was the deliberate, explicitly-named, validated
   design from the start, not an unnoticed bug.
4. `src/mintnet/simulation/motifs.py` — `sample_organic_network()`,
   `ORGANIC_NETWORK_TRUE_EDGES`, `_build_organic_network_precision()`.
   The one DGP in this project's history that is a single connected,
   cyclic, realistically-shaped network rather than disjoint small
   motifs — the fixture that exposed the defect.
5. `src/mintnet/experiments/stage10a.py` and the `"organic_network"`
   entry in `_DGP_REGISTRY` (`src/mintnet/experiments/stage5a.py`) —
   how the fixture is wired into the project's shared DGP registry.
6. `scripts/stage10a_cost_shard.py` — reproduces the search's own
   per-pair loop for sharding purposes; this is the script that
   actually produced the multi-hour-per-shard timings cited in Section
   1. Its module docstring explains why the pool must be computed from
   the *full* candidate graph even when sharding by pair batch (a
   shard-local subset would silently shrink the pool and change the
   answer).
7. `.github/workflows/stage10a_cost.yml` and
   `scripts/aggregate_stage10a_cost_shards.py` — the dispatch mechanics
   for the run that produced the timings. GitHub Actions run ID
   `35013637338` (cancelled by explicit instruction after 5 of 6 shards
   confirmed the finding) is the actual run referenced throughout this
   document.

**The core primitives that are sound and must not be confused with the defect:**

8. `src/mintnet/mi/structured_density.py` — `local_permutation_test()`.
   Given a specific conditioning set, this test is correct. The defect
   is entirely upstream of this function, in how candidate conditioning
   sets are chosen, never in this function's own logic.
9. `src/mintnet/screening/pairwise_correlation.py` —
   `compute_pairwise_screening_evidence()`, `screen_uncorrected()`. No
   conditioning-pool concept exists here; unaffected by any of this.

**The related, independently-confirmed failure mode (bootstrap-rescue):**

10. `src/mintnet/bootstrap/stability.py` —
    `compute_edge_stability_growing_subset_structured_density()` /
    `_run_one_growing_subset_structured_density()` (the archived
    full-repeat mechanism) and
    `compute_edge_stability_localized_structured_density()` (the
    localized replacement, itself now also archived per Section 4,
    since it sits on top of the same broken base search).
11. `src/mintnet/pipeline/stability_rescue.py` —
    `growing_subset_dpi_structured_density_with_stability_rescue()`
    and `growing_subset_dpi_structured_density_with_localized_rescue()`,
    the two rescue entry points built on the functions above.
12. `docs/decision_log.md` entries **D-085** (the heavy-tailed cost
    distribution disclosed before any of this, `mean 377s, max
    ~14,548s` — should have been a warning sign earlier than it was),
    **D-088** (first, unsharded cost-measurement failure), **D-090**
    (the resample-sharded retry, where one resample finished in 43
    minutes and a sibling exceeded 6 hours on nominally the same
    computation), and **D-091** (the pointer entry to this document).
    Read in that order; they are the actual narrative of how this was
    discovered, not just the conclusion.
13. `src/mintnet/experiments/stage9d_localized_rescue.py` and
    `src/mintnet/experiments/stage9c_bootstrap_rescue.py` /
    `stage9c_bootstrap_rescue_reporting.py` — the evidence-generation
    runners for the (now archived) rescue calibration work. GitHub
    Actions run ID `35037634057` (Stage 9d Steps 3-4, cancelled by
    explicit instruction alongside `35013637338`) is referenced in
    D-091 as the concurrently-cancelled dispatch.

**Product-surface documents that assumed the search was usable and now need revisiting:**

14. `src/mintnet/api.py` — `discover()`, the public v1 API function.
    Built assuming the underlying search and rescue mechanisms were
    usable at real scale; that assumption is now known false.
15. `outline/package_scope_v1.md`, `outline/api_design_v1.md` — the
    product-scope and API-design documents that named `enable_rescue`
    and the search itself as the path to real usability. Both need a
    disclosed correction (in the manner already used twice in
    `outline/api_design_v1.md`'s own history) reflecting this finding,
    not a silent rewrite.

**Frozen charters providing background (read for context, not as current truth):**

16. `docs/stage10a_charter.md` — the charter that commissioned the test
    that found this. Still frozen and historically accurate about what
    was planned; its own topology-design history is further corrected
    in D-089 (a separate, smaller correction that predates this
    finding — the topology fix for screening reliability, not the
    scaling defect).
17. `docs/stage9d_charter.md` — the localized bootstrap-rescue charter,
    now archived per Section 4 for reasons unrelated to its own
    internal logic (it inherits the base search's defect).
