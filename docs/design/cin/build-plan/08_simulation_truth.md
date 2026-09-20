# Task 08 — Simulation generators and exact truth

Roadmap: §10 (cost inputs), §11.1, M2/M4. Files: `src/mintnet/simulation/cin_networks.py`, `tests/unit/cin/test_simulation.py` (or `tests/unit/test_cin_networks.py`, matching the existing unit-test layout).

## 1. Purpose

Generate, for each frozen case, datasets with **exactly known observed-variable conditional-dependence graph** (and, where derivable, population CMI), plus the cost-pilot inputs that carry no truth. The generators are separate from estimation code and must be validated **before** any evidence run: positive definiteness, connectivity, exact-zero non-edges, non-degenerate signal, correct graph semantics.

## 2. Common interface

```python
@dataclass(frozen=True)
class SimulatedDataset:
    frame: pd.DataFrame
    schema: dict            # ready for fit_network
    truth_edges: frozenset[tuple[str, str]]     # canonical (schema-order) pairs
    population_cmi: dict[tuple[str, str], float] | None    # nats; None if not derived
    meta: dict              # case, seeds, structure params, rejection-sampling tries, signal summaries

generate_case(case: str, *, structure_seed: int, sample_seed: int, n: int | None = None) -> SimulatedDataset
generate_cost_input(kind: str, p: int, n: int, *, seed: int) -> tuple[pd.DataFrame, dict]
```

- `structure_seed` fixes topology/weights/potentials; `sample_seed` fixes the draw. Both come from the runner's seed derivation (task 09). Pairing B/D uses the **same** `structure_seed` and the same underlying standard-normal draw (D transforms B's data).
- Randomization by replicate is over topology and weights **within the case definition**; the case's signal specification (distributions of weights, density, potential ranges) is frozen in the charter and never adjusted after seeing method results.
- **Rejection sampling is allowed only on population quantities** (e.g., require at least `m_strong` edges with CMI ≥ 0.01; require connectivity) with a fixed `max_tries`; record the number of tries; if `max_tries` is exceeded raise (do not relax). Never select graphs using estimator output.
- Frame index is `range(n)` with string column names `V00…V{p-1}` (stable, zero-padded) unless the case defines meaningful names.

## 3. Shared utilities

- `exact_cmi_from_joint(P)`: for a finite joint `P` (ndarray over all variable states), return `I(X_i;X_j | rest)` for all pairs using `CMI = Σ P log[ P·P_rest / (P_{i,rest}·P_{j,rest}) ]` via axis sums and `np.where(P>0, …)`; exact zero for structural non-edges (assert `≤ 1e-12`). Vectorized with `np.einsum`/axis sums, tensors up to `3^6=729` and `2^8=256` states.
- `gaussian_truth(omega)`: partial correlations `ρ_ij = −Ω_ij / sqrt(Ω_iiΩ_jj)`, CMI `= −0.5·log(1−ρ²)`, truth edges = `Ω_ij ≠ 0` for `i≠j`.
- `is_connected(edges, p)` with a small BFS (no networkx).
- `population_signal_summary`: quantiles of CMI over true edges, count with CMI ≥ 0.01, edge density; stored in `meta` and used to write the charter's population table.

## 4. Case definitions (roadmap §11.1)

Parameters below are **[added] proposed concrete values** to make the specification executable; freeze after checking population signal distributions, before running anything.

**Gaussian cases A–D.** Symmetric sparse weighted adjacency `W` (zero diagonal), `Ω = I + a·W`, `a = 0.8/‖W‖₂` (so `λ_min(Ω) ≥ 0.2 > 0`), covariance `Σ = Ω⁻¹`, sample `X ~ N(0, Σ)`. Assert PD via Cholesky. Edge weights `w = ±U(w_lo, w_hi)` with random sign.

| Case | N,p | Topology | Weight law (proposed) |
|---|---|---|---|
| A | 100, 8 | Random spanning tree + 2 extra edges (connected, sparse) | `U(0.6, 1.2)`; require ≥ 3 edges with CMI ≥ 0.01 |
| B | 200, 30 | Connected: random spanning tree + Erdős–Rényi extras until density ≈ 25% | Mixture: 70% `U(0.3,0.8)`, 30% `U(1.0,1.8)` (diffuse + strong); require ≥ 8 edges with CMI ≥ 0.01 |
| C | 150, 100 | One dense community of 25 nodes (within density 0.5), remaining 75 nodes sparse (density 0.03), plus ~30 between-community links; connected | Mixture as B; report signal distribution; **no** strong-edge requirement (dense-graph edges are often intrinsically weak — record the distribution, do not interpret recall before consulting it) |
| D | 200, 30 | B's structure and B's draw | Apply invertible monotone `sinh(0.5·z)` to a fixed half of the coordinates (every other index); zero-pattern and population CMI unchanged (invariance of CMI under invertible marginal maps); truth equals B's |

Note for C: because `a = 0.8/‖W‖₂` shrinks weights in dense graphs, expect very small partial correlations; `population_signal_summary` is mandatory output and is reviewed before freezing.

**E — nonlinear tree (N=200, p=30).** Draw a rooted 25-node tree with maximum depth 3 (each nonroot has exactly one parent; e.g. sample parent uniformly among nodes with depth < 3). `X0 ~ N(0,1)`, `Xk = a_k·g_k(X_parent(k)) + ε_k`, `ε_k ~ N(0, σ_k²)`. Edge function assignment (fixed proportions, randomized positions per replicate): one third each of linear `g(x)=x`, saturating `tanh(1.5x)`, even `2x²/(1+x²) − 1`. Coefficients `a_k ~ ±U(0.8,1.2)`, `σ_k ~ U(0.4,0.7)` (proposed; freeze after population checks). Append 5 independent `N(0,1)` distractors. Truth = tree edges (parent–child); non-adjacent pairs, including siblings, are conditionally independent given all others (each variable has one parent ⇒ no co-parent/collider structure ⇒ moral graph = tree). Bounded `g` limits propagation. **Population CMI for E is optional** (no closed form); if wanted, compute once per frozen configuration by 2-D numeric quadrature of the adjacent pair's joint given the other variables, on a small sample of draws, and record it only in the charter's population table — not per replicate.

**F — binary Ising (N=150, p=8).** States `x ∈ {0,1}^8`; `P(x) ∝ exp(Σ h_i x_i + Σ_{(i,j)∈E} J_ij x_i x_j)`. Graph: random connected graph with 8 nodes, 10 edges (tree + 3 extras). `h_i ~ U(−0.5,0.5)`, `J_ij ~ U(0.6, 1.2)` (positive). Enumerate all 256 states, sample i.i.d. from the exact joint, compute exact edge CMI (assert every true edge CMI ≥ 0.005 and non-edges ≤ 1e-12; redraw structure only on this population rule). Schema: all binary categorical `levels=[0,1]`. No MCMC.

**G — three-level pairwise categorical (N=150, p=6).** `P(x) ∝ exp(Σ_i h_i[x_i] + Σ_{(i,j)∈E} J_ij·1[x_i = x_j])`, `J_ij ~ U(0.6,1.2)`, `h_i[·] ~ U(−0.5,0.5)`. Graph: 6 nodes, 7 edges connected. Enumerate `3^6 = 729` states. Verify edge CMI ≥ 0.005. Schema: categorical with three levels.

**H — mixed star (N=150, p=8).** Binary `H ~ Bernoulli(π)` with `π ~ U(0.35,0.65)`; 4 continuous children `X_k = a_k·(H − π) + ε_k`, `a_k ~ ±U(0.8,1.4)`, `ε_k ~ N(0,1)`; 3 independent `N(0,1)` distractors. Factorization gives the observed star: children conditionally independent given H and everything else; child–child edges are absent in the *conditional* graph. Truth: H–child edges. Exercises both response orientations (categorical target with continuous predictors and vice versa). Population CMI per edge by closed-form 1-D quadrature (mixture of two Gaussians) — optional and recorded in the charter.

**I — low-N null (N=60, p=30).** 15 continuous `N(0,1)` and 15 three-level categorical (independent, prevalence drawn once per replicate from `Dirichlet(4,4,4)`). No edges. Used to report positive-weight quantiles, maximum weights, and displayed fractions; average precision is undefined and not computed.

**Outside recovery gates (demonstrations, not requirements).** Variance-only dependence (`Y = X·ε`) and XOR (`Z = XOR(X,Y)` as binary/continuous surrogate) as two-to-three-variable illustrative datasets, recorded as expected failures.

**Historical regression smoke.** `sample_organic_network(n, rng)` from `simulation/motifs.py` (14 connected + 4 distractors per the smoke review) with its existing truth edges, N=300, one replicate, used as a numerical-sanity regression (strong ranking, no gate).

## 5. Cost-pilot inputs (roadmap §10; no truth claimed)

`generate_cost_input(kind, p, n, seed)`:

- `dense_continuous`: multivariate normal with dense positive-definite covariance from a random 5-factor model plus diagonal (`Σ = ΛΛᵀ + D`, standardized). Correlations moderate; this is a numerical stress input, not a network with declared truth.
- `categorical5` / `categorical10`: latent Gaussian from the same dense generator, each column cut at fixed random-quantile thresholds into 5 or 10 levels (every level appears with ≥ 1% expected mass).
- `mixed`: 50 continuous (dense generator) + 50 five-level categorical columns.
- Return schema. No truth attached. Do **not** score recovery on these inputs.

## 6. Tests

1. **Gaussian validity**: over 200 random structures per case, `Ω` PD (min eigenvalue ≥ 0.19), connectivity holds, density in the intended band, `truth_edges == support(Ω)`, analytic CMI matches a numeric Gaussian conditional-MI calculation on a small case (`−0.5 log(1−ρ²)` vs the entropy formula with `logdet`).
2. **Pairing**: B and D from the same seeds share structure and truth; D's transformed columns are exactly `sinh(0.5·z)` of B's; untouched columns identical.
3. **Exact categorical truth**: F/G exact CMI computed by enumeration equals a brute-force per-pair computation; non-edges are `< 1e-12`; sampling frequencies converge to the joint in a fixed-seed chi-square test (n=100k, kept small and deterministic).
4. **Star (H)**: factorization check — conditional independence of child pairs given H numerically holds via the Gaussian conditional covariance of an analytic joint for the mixture (`E[X_a X_b | H] = E[X_a|H]E[X_b|H]`); edge set equals star.
5. **Tree (E)**: tree depth ≤ 3, one parent per non-root, distractors independent, function assignment counts, nonzero dependence for the even function (correlation ≈ 0 but mutual dependence > 0 verified by a simple binned dependence check on a large draw kept out of the unit suite or with n=20k only if it runs in < 1 s).
6. **Rejection sampling**: only population criteria used; exceeding `max_tries` raises; tries recorded.
7. **Determinism**: identical seeds ⇒ identical frames; changing `sample_seed` alone keeps structure; changing `structure_seed` alone keeps only marginal design.
8. **Schema**: schemas load cleanly through `prepare_data` (task 01); categorical level sets are exactly declared.
9. **Population-signal summaries** exist and are non-empty for A, B, C, E (mandatory recorded outputs).

## 7. Acceptance

All above green; one **population-property report** (`docs/cin_baseline_charter.md` appendix, produced by a small script run once) lists, for A–I: density, edge count, CMI quantiles, strong-edge counts, tries. This report is reviewed and the charter frozen **before** any method result is seen.

## 8. Pitfalls

- Truth semantics: latent-Gaussian discretizations do not have the latent precision graph as observed truth; they appear only in cost inputs.
- Do not use a nonlinear SEM edge list as truth without an explicit factorization argument (moral graph is only an upper bound; cancellations exist).
- Keep `sample_seed`-dependent draws independent of the count of rejection tries (derive the sample RNG from a separate child seed).
