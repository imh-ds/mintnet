# Spinoff Plan: Growing-Order Partial-Correlation Screening for Network Psychometrics

Status: **PROPOSAL — not yet executed.** This document records the
plan and the literature basis for it; it does not itself authorize
creating the new repository. Execute only after explicit go-ahead on
the specific open decisions listed at the bottom.

## Background

`main`'s `v1-partial-correlation-baseline` tag (commit `e844fc3`, tagged
2026-09-01) captures a complete, independently benchmarked methodology:
Fisher-z correlation screening followed by a DPI-motivated partial-
correlation conditional-independence prune, escalating the
conditioning-set size only as needed (D-053's growing-subset variant).
It was built and validated as MINT's own Stage 1-6a arc, under the
(later-corrected) assumption that this was a temporary substitute for
a mutual-information estimator — see `docs/decision_log.md` D-050
through D-054 for the full evidentiary record. Two of those findings
are independently interesting regardless of the MI question:

- **D-050**: this method's precision advantage over EBICglasso *grows*
  with signal strength, where EBICglasso's own precision collapses.
- **D-051** (as corrected): PC's skeleton beats this method on
  precision on composed networks, but misses weak true edges this
  method and EBICglasso both catch — a genuinely different tradeoff
  profile, not strict dominance either way.

That is a real result on its own, independent of whether `mi-native`'s
MI-based generalization ever ships.

## Literature check (quick, not exhaustive — see caveat below)

Before treating this as worth a standalone paper, checked whether the
core mechanism already exists in the network-psychometrics literature
(where it would be redundant) or in an adjacent field (where it would
still be new to psychometrics, just not new absolutely).

**Finding: the core algorithm is not new.** It closely matches **LOPC**
("low-order partial correlation"), from systems biology (gene
co-expression / metabolomic network inference, ~2014,
[PMC4194134](https://pmc.ncbi.nlm.nih.gov/articles/PMC4194134/) /
[PubMed 25003577](https://pubmed.ncbi.nlm.nih.gov/25003577/)): screen
by zero-order correlation, escalate to first-order partial correlation
only for pairs that survive screening, escalate further only if still
ambiguous. Architecturally the same idea as this project's own
growing-subset DPI (D-053).

**Finding: the cross-application appears genuinely open.** Across
several searches — including ones specifically targeting 2023-2025
psychometric-methods papers — nothing surfaced showing LOPC (or an
equivalent growing-order partial-correlation screen) ever applied,
cited, or benchmarked within network psychometrics against EBICglasso,
using the field's own simulation conventions. Related but genuinely
different psychometric-network methods checked and ruled out as
matches: PC-algorithm skeleton estimation (already an established
comparator in this literature, unlike LOPC), Bayesian conditional-
independence testing for individual edges (Multivariate Behavioral
Research, 2024 — different mechanism, no screen-then-prune pipeline),
and Information Filtering Networks (a fixed-edge-count topological
rule, not conditional-independence testing at all).

**Finding: even LOPC's own motivation differs.** LOPC's paper justifies
itself purely as a computational/statistical shortcut (exploiting
network sparsity to avoid computing full-order partial correlations
for every pair). It does not invoke the data-processing-inequality
argument (an indirect edge must be weaker than the direct paths
composing it) that motivates this project's own version, borrowed from
ARACNE-style information-theoretic pruning. That framing difference
survives even though the computational mechanism does not.

**Caveat**: this was a handful of targeted web searches, not a
systematic database review (no PsycInfo/Scopus citation-graph check,
no manual backward/forward citation tracing on LOPC or on Epskamp's
own tutorial papers). Confident enough to proceed on this basis, not
confident enough to call it a cleared, exhaustive novelty check —
worth a proper reference-manager-assisted pass before submission.

## Honest framing for the resulting paper

**Not**: "a novel algorithm for network estimation."
**Is**: the first application of a growing-order partial-correlation
screen-then-prune procedure (closely related to LOPC, cited as such)
to network psychometrics, motivated through data-processing-inequality
logic rather than LOPC's original sparsity argument, and benchmarked
against the field's own standard (EBICglasso) using the field's own
simulation conventions (the exact motifs and grids already validated
in `docs/stage5a_charter.md` through `stage5f_charter.md`).

This is a legitimate, normal category of methods paper (cross-domain
adaptation + first validation in a new field), but LOPC must be cited
as directly related prior work up front, not discovered by a reviewer.

## What migrates

Everything at or before `v1-partial-correlation-baseline` (189 commits,
through `e844fc3`) — the full screening/DPI pipeline, the Stage 0-6a
validation arc, the comparator benchmarks (D-047-D-054), and every
charter/decision-log entry documenting them. Nothing from `mi-native`
(diverges after this tag; not an ancestor of it, so it will not come
along regardless of migration method — see below).

## Migration procedure (preserves full commit history, verified)

Because `v1-partial-correlation-baseline` is a tag on an ancestor
commit of `mi-native`'s own later work, and git only follows ancestry
when pushing, the following brings across every one of those 189
commits — full authorship, dates, messages, diffs, unmodified — and
excludes every `mi-native`-only commit automatically, with no
history-rewriting tool required:

```bash
# 1. Create a new, empty GitHub repository (name/visibility: open decision, see below)
gh repo create <new-repo-name> --private   # or --public

# 2. From a fresh clone of the existing mintnet repo (or this worktree)
git remote add spinoff https://github.com/<you>/<new-repo-name>.git
git push spinoff v1-partial-correlation-baseline:main
git push spinoff v1-partial-correlation-baseline   # also push the tag itself
```

Optional, later, once the new repo exists on its own: trim files that
are irrelevant to this specific package (e.g. any `mi-native`-only
staging that might have leaked in, unrelated exploratory stages) via
`git filter-repo --path ...` — additive/subtractive, does not need to
happen before the initial push, and should be decided once the new
repo's own scope (a "lightweight analytical package," per your framing)
is settled.

## Open decisions before executing anything

1. **Repo name and visibility** (public from the start, or private
   until submission-ready).
2. **Package scope**: full trim to just the screen+DPI-prune pipeline
   and its own tests, or carry over more of the surrounding
   experiment/reporting infrastructure as-is and trim later.
3. **Package/method name** — "MINT" branding shouldn't carry over
   unmodified, since this package deliberately does *not* use mutual
   information; needs its own name.
4. **Target venue** — a methods-focused psychometrics journal
   (*Behavior Research Methods*, *Multivariate Behavioral Research*,
   *Psychological Methods*) fits the "adaptation + validation" framing
   established above.
5. **Timing relative to `mi-native`** — whether to start this now in
   parallel, or after `mi-native` reaches its own next milestone.
