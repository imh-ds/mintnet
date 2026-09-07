# Archive: partial-correlation-era pipeline (pre-MI pivot)

This directory holds the code, tests, configs, and charters from mintnet's
original partial-correlation-based pipeline (Stage 0 through most of Stage 5),
kept here for transparency and historical reference rather than deleted. The
project pivoted to a mutual-information-based conditional-independence
mechanism (`mi-native` track, Stage 6 onward); the partial-correlation
network built during the earlier arc has already been copied into a separate
repository for anyone who needs to run it going forward.

**Nothing here is imported by anything in `main`.** Files were moved out of
`src/mintnet`, `tests/`, `configs/`, and `docs/` only after a mechanical,
verified dependency-closure check confirmed no code outside this directory
references them. A handful of Stage 0-5 modules that MI-native's own
evidence still actively depends on (e.g. `experiments/stage5a.py` as
Stage 6a's comparator baseline, `experiments/stage1b.py`/`stage1j_fit.py` as
shared gate/fitting machinery, `pipeline/growing_subset_dpi.py` as the
partial-correlation DPI baseline) were deliberately left in `main` rather
than archived here, along with their own charters/configs, since they are
still load-bearing.

This directory mirrors the original repository layout:

- `src/mintnet/...` -- archived source modules
- `tests/unit/...`, `tests/integration/...` -- their corresponding tests
- `configs/...` -- their experiment configs
- `docs/...` -- their charters, reports, and related historical documents
  (`handoff_stage1.md`, `handoff_stage4.md`, the peer-review briefs/followups,
  `stage4o_recommendation.md`)

`docs/decision_log.md` and `docs/validated_operating_ranges.md` were **not**
archived -- they are living, append-only records spanning both eras and
remain in `docs/` at the repository root.
