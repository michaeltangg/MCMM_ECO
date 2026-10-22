# Risk-Controlled Pruning for Timing Closure: Conformal Guarantees for MCMM Corner Reduction and ECO Candidate Filtering

Oct 22, 2026 · @Michael

## Problem

Timing closure repeats expensive evaluations that are rarely all needed: signoff STA runs every corner, and ECO repair runs incremental STA on every candidate move. Existing ways of skipping work are either heuristics or accurate predictors with no stated bound on what they miss.

- **Corners:** MCMM signoff runs STA at every combination of process, voltage and temperature (PVT) corner and RC extraction corner. Most corners never set the worst slack for most paths, but which ones matter is path-dependent: wire-dominated paths tend to be worst at RC-worst extraction and cell-dominated paths at C-worst, and temperature inversion at low voltage breaks simple "slow-hot is always worst" rules.
- **ECO candidates:** a repair loop enumerates many resize moves per violating endpoint and verifies each with incremental STA, though only the best one is applied.
- **How it is handled today:** dominant-scenario selection and dominance relations (heuristic), ML prediction of unobserved corners (accurate on average, no guarantee), and scenario compression in commercial tools. ML gate sizers improve solution quality but do not prune candidates with a stated error bound.
- **The gap:** none of these lets the engineer choose an acceptable miss rate and have the pruner provably stay under it. Signoff needs that property; average-error statistics do not provide it.

**Research question:** can conformal risk control turn a learned timing predictor into a pruner with a user-chosen bound on missed violations (corners) or lost best moves (ECO), how much STA work does it save at each bound, and does the guarantee survive transfer to a design it was not calibrated on?

## Related work and positioning

Predicting timing at unobserved corners is solved well on average; conformal pruning has precedent in other search problems. Combining them into a guaranteed-miss-rate corner pruner, and testing conformal candidate pruning inside an STA repair loop, is the open part.

| Work | What it does | Gap relative to this project |
| --- | --- | --- |
| [Kahng et al., "Unobserved Corner" Prediction, DATE 2019](https://ieeexplore.ieee.org/abstract/document/8715102) | Linear regression predicts 48 unobserved corners from 10 observed; <0.5% relative RMSE on a 1M-instance 16nm design | Point prediction; error statistics, no bound on missed violations |
| [ML multi-corner timing prediction, Electronics 2022](https://www.mdpi.com/2079-9292/11/10/1571) | Strategy for choosing dominant (observed) corner combinations with high prediction accuracy | Same: accuracy, not a guarantee |
| [Synopsys patent: signoff-safe multi-corner reduction](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12675622) | One ML model judges whether prediction error is below a threshold; a second predicts slack | Learned safety check, not a distribution-free bound |
| [Synopsys scenario reduction via corner dominance](https://patents.google.com/patent/US8707241) | Drops scenarios dominated by another corner in the same mode | Rule-based; no per-path learning |
| [Synopsys Adaptive Scenario Compression](https://semiengineering.com/predictable-design-optimization-and-closure-with-adaptive-scenario-compression/) | Compresses many scenarios into fewer views that retain timing characteristics | Commercial alternative; implementation-side, no stated miss bound |
| [Cadence MMMC view pruning](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10133842) | Prunes analysis views per node | Heuristic dominance |
| [Conformalized Vmin prediction, DATE 2024](https://arxiv.org/html/2406.18536v1) | Conformalized quantile regression for minimum operating voltage with coverage guarantee | Conformal in test/manufacturing, not STA |
| [Diffusion Mutation Kernels, arXiv 2608.27649](https://arxiv.org/pdf/2608.27649) | Conformal risk control prunes candidates with a winner-preservation guarantee in circuit/physical design search | Closest method precedent for the ECO half; different loop |
| [Certified candidate-set pruning, EMNLP 2022](https://arxiv.org/pdf/2205.09638); [conformal HW-NAS filters, arXiv 2610.03127](https://arxiv.org/pdf/2610.03127) | Conformal pruning of candidates with error control; NAS work shows exchangeability breaks inside an adaptive search loop | Outside EDA; the exchangeability caveat applies directly to ECO loops |
| [RL-Sizer](https://gtcad.gatech.edu/www/papers/dac21-3.pdf), [LEGO-Size (NVIDIA)](https://ispd.cc/ispd2026/slides/2025/protected/10_2_slides.pdf), [TimeBoost](https://www.sciencedirect.com/science/article/pii/S1434841125002110) | Learned/differentiable sizing; XGBoost selects an STA method per stage | Improve quality or STA speed; no guaranteed candidate pruning |

**Positioning:** to our knowledge, the first distribution-free miss-rate guarantee for MCMM corner reduction, plus a measurement of whether conformal candidate pruning stays calibrated inside an incremental-STA repair loop. Re-check Google Scholar before submission.

## Proposed solution

One method, two applications: a learned predictor ranks expensive evaluations, conformal calibration sets the pruning threshold so the miss rate stays below a user-chosen α, and only the retained evaluations are run. α is the single knob: loose for fast early exploration, tight for signoff.

### Part A (core): corner pruning with guaranteed violation recall

Run STA at a small set of anchor corners A. For every endpoint e and every unobserved (corner, check) unit c (setup and hold handled separately), a model predicts slack ŝ_c(e).

**Calibration (class-conditional split conformal).** On calibration designs where every corner was run, take the n endpoint–corner pairs that truly violate (slack below guard band g). Set the threshold at their conformal quantile of predicted slack:

```latex
\hat{\tau} = \hat{s}_{(k)}, \quad k = \left\lceil (1-\alpha)(n+1) \right\rceil
\quad\Rightarrow\quad
\Pr\!\left(\hat{s}_c(e) \le \hat{\tau} \;\middle|\; s_c(e) < g\right) \ge 1-\alpha
```

where ŝ_(k) is the k-th smallest predicted slack among calibration violators. A pair is flagged if ŝ_c(e) ≤ τ̂.

**Decision.** A (corner, check) unit is skipped only if none of its endpoints are flagged. Guarantee: at least 1−α of true violations fall in units that get run. Realized misses can only be lower, because a run unit catches all its violations, flagged or not.

**Inputs (per endpoint):**

- Slack, arrival and required time at each anchor corner, setup and hold
- Data-path delay split into cell delay and wire delay; number of stages
- Cell mix along the worst path (e.g., share of high-stack cells, which are more voltage-sensitive)
- Average stage slew and load; clock latency and skew at anchors
- Target corner descriptors (process, voltage, temperature, R and C scale factors) so one model can serve all unobserved corners

**Model:** XGBoost/LightGBM per check type with corner descriptors as features; Kahng-style linear regression as the accuracy baseline. The conformal step is model-agnostic: a worse model gives a looser threshold and fewer skipped corners, never a broken guarantee.

### Part B (stretch, gated): ECO candidate pruning with best-move retention

Inside a greedy setup fixer (worst endpoint first, enumerate resize moves on its path), a model predicts each candidate's slack gain ĝ(m). Only candidates within λ of the top prediction are verified with incremental STA:

```latex
K_\lambda = \{\, m : \hat{g}(m) \ge \max_{m'} \hat{g}(m') - \lambda \,\}, \qquad
\lambda_i = \max_{m'} \hat{g}(m') - \hat{g}(m_i^\star)
```

where m*_i is the STA-measured best move in calibration instance i. λ̂ is the conformal quantile of the λ_i, giving Pr(m* ∈ K) ≥ 1−α under exchangeability.

**The interesting part:** exchangeability is strained here, because candidates change as repair progresses. Measure coverage across early, middle and late repair iterations, and compare static calibration against adaptive conformal inference if coverage drifts.

&#91;flow: anchor STA → predict unobserved slack → conformal threshold (α) → run only flagged corners → report misses\]

## Experimental setup

Signoff-style STA over PVT × RC corners on Sky130, with ASAP7 as the fallback platform. The method consumes only STA outputs, so it transfers to commercial STA unchanged.

| Item | Choice | Note |
| --- | --- | --- |
| Flow | OpenROAD-flow-scripts, OpenSTA for all corner analysis | Fully scriptable; every STA run timed |
| PDK (primary) | Sky130, sky130_fd_sc_hd | Ships many PVT Liberty corners, including low-voltage cold corners where temperature inversion may make dominance path-dependent; confirm the exact list from the PDK |
| PDK (fallback) | ASAP7 (7nm predictive) | Only three PVT corners in ORFS (confirm from the files), but wires dominate delay, so RC corners matter more: 3 PVT × 4 RC = 12 corners. Matches the advanced-node story |
| Corner set | PVT corners, then RC corners (C-worst, RC-worst, C-best, RC-best style) | RC corners built by scaling R and C separately; loaded with `define_corners` and `read_spef -corner`. Flat standard derates only; no artificial per-corner derates |
| Stage | Post-route, extracted SPEF from the ORFS final stage | Signoff-like; scaled RC corners approximate multi-corner extraction (limitation) |
| Designs | Calibrate on aes and jpeg; hold out ibex; riscv32i optional on Sky130 | Confirm each completes on the chosen platform |
| Data variety | Several clock targets and placement seeds per design | Creates violations and gives multiple design instances for calibration studies |
| Anchor corners | Chosen greedily (most violations covered) and by physics rule (slowest setup, fastest hold) | Compared as part of the study |
| ECO fixer (Part B) | Own greedy fixer, resize moves via `replace_cell` | Same fixer for pruned and unpruned runs |
| Model | XGBoost/LightGBM; linear regression baseline | Small tabular data; fast to train |
| Conformal | Class-conditional split conformal (Part A); conformal set calibration (Part B) | A few dozen lines of code; no library dependence |

## Step-by-step breakdown

Eight days, with go/no-go gates before any modeling and before starting Part B.

1. **Flow bring-up (Oct 22).** Run aes, jpeg and ibex through ORFS on sky130hd at tightened clocks; collect final SPEF; list available Liberty corners.
2. **Gate 1: is there anything to prune? (Oct 22, platform decided by end of day).** Run all corners on one design and check setup and hold separately (hold may be less clean because clock-tree and data-path delays scale differently, shifting skew). Escalate only as far as needed:
   1. **Sky130, PVT corners only.** If the slowest setup corner and fastest hold corner do not catch every violation, continue on Sky130.
   2. **Sky130, PVT × RC corners.** If PVT dominance is trivial, add scaled RC corners and re-check.
   3. **Switch to ASAP7, PVT × RC corners.** If dominance is still trivial, or for a stronger advanced-node story. Reuses the ASAP7 bring-up planned for the earlier hold-cost project.

   Do not bring up both platforms in parallel. Do not inject random derates to manufacture non-trivial dominance; a model that learns injected derates proves nothing.
3. **Dataset generation (Oct 23).** All designs × variants × corners; per-endpoint setup and hold slack plus path features from anchor runs. Log STA runtime per (corner, check).
4. **Models and calibration (Oct 24).** Train slack predictors; implement the conformal threshold; implement baselines.
5. **Evaluation (Oct 25).** α sweep in-distribution and on held-out ibex, with zero and small amounts of ibex calibration data. Analyze where misses land.
6. **Gate 2: start Part B? (Oct 26).** Only if Part A results and figures are complete.
7. **Part B (Oct 26–27).** Greedy fixer, candidate enumeration with STA-measured gains, conformal set pruning, coverage across repair iterations.
8. **Ablations and figures (Oct 28).** Feature ablation, anchor-set size, guard band g, calibration-set size.
9. **Writeup (Oct 29–30).** Final document and slides; deadline Oct 30, 11:59 PM. Problem, related work and method drafted in parallel from day 1.

## Baselines and comparison metrics

**Part A variants:**

1. **Run all corners:** ground truth and runtime ceiling.
2. **Physics rule:** run slowest corner for setup and fastest for hold only.
3. **Dominant-corner heuristic:** keep corners that were worst for any endpoint on calibration designs.
4. **Point predictor + fixed margin:** ML or linear prediction with an empirical margin (Kahng / patent-style).
5. **Conformal pruner (proposed):** same predictor, conformal threshold at chosen α.

**Part B variants:** no pruning; fixed top-k; analytical first-order gain estimate (cell delay change plus driver resistance × added input capacitance) with the same conformal step; learned gain predictor with conformal step.

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Violation recall | Fraction of true violations in (corner, check) units that were run | The guaranteed quantity; must be ≥ 1−α |
| STA work saved | Fraction of (corner, check) units skipped; wall-clock saved | The payoff |
| Net runtime | STA saved minus anchor runs, feature extraction, inference and calibration | Honest accounting |
| Coverage on new design | Recall on held-out ibex vs. amount of ibex calibration data | Tests the exchangeability assumption |
| Miss distribution | Misses by slack range, path depth, clock domain | Average coverage can hide clustered failures |
| Best-move retention (B) | Fraction of repair steps where the STA-best move survived pruning | The Part B guarantee |
| STA calls and final WNS/TNS (B) | Incremental timing updates per repair; final timing vs. unpruned fixer | Savings at equal quality |

**Primary claim tested:** at α = 1%, the conformal pruner keeps violation recall ≥ 99% while skipping more corners than the dominant-corner and fixed-margin baselines achieve at the same recall.

## Expected outcomes, risks and limitations

Every outcome is reportable, because the guarantee and its failure modes are both measurable.

| Outcome | What it shows |
| --- | --- |
| Conformal pruner skips more work than baselines at equal recall | Guaranteed pruning is practical, not just safe |
| Guarantee holds in-distribution but breaks on ibex | Quantifies how much new-design calibration a deployment needs |
| Physics rule is already near-optimal on PVT corners but not PVT × RC | Dominance flips come from wire/cell balance; supports pruning across RC corners specifically |
| Physics rule is near-optimal even with RC corners | Corner dominance is clean on this platform; the method matters where it is not (stated as finding) |
| Part B coverage drifts across repair iterations | Static conformal filters are unsafe inside adaptive loops; motivates adaptive calibration |

| Risk | Mitigation |
| --- | --- |
| Corner dominance is trivial on Sky130 | Gate 1 on day 1; add RC corners; switch to ASAP7 PVT × RC if still trivial |
| ASAP7 switch costs bring-up time | Decide platform by end of Oct 22; prior ASAP7 planning reused; designs already scoped |
| Too few violations for class-conditional calibration | Tighter clocks, more variants, guard band g > 0 |
| STA runtime too small to make savings impressive | Report fractions and scaling with design size and corner count |
| Part B not reached | Part A stands alone; Part B becomes a short preliminary section |

**Limitations to state up front:**

- Sky130 is a mature node, and ASAP7 is predictive with only three PVT corners; neither has LVF/POCV variation data, so flat derates only.
- RC corners are approximated by scaling R and C from one extraction, not by separate extraction rule decks.
- The guarantee is marginal (average over endpoints), not per-path, and assumes calibration and test data are exchangeable.
- Few designs; generalization claims stay modest.

## Future work

- **Risk-controlled hold-cost prediction for setup repair.** Setup fixes in the slow corner speed up cells that short paths share, consuming fast-corner hold margin that hold repair later pays back with buffers. The calibration machinery used here extends directly: alongside predicted setup gain, each candidate move would carry a conformal upper bound on the fast-corner hold slack it consumes, so moves are penalized only when the bound indicates likely new hold violations. The corner pruner decides which slow and fast corners need full analysis. This requires a flow that models useful skew and scan-path hold fixing realistically, so it is left to evaluation in an industrial setting.
- **Signoff extraction corners.** Replace scaled RC corners with separate extraction rule decks per RC corner.
- **Adaptive calibration across designs.** Weighted or adaptive conformal methods to keep the guarantee valid on new designs with little calibration data.

## Approaches considered and rejected

- **Ripple-aware ECO pruning (predict net path Δslack including driver loading):** driver loading is already handled by sizers and by incremental STA; a first-order formula captures most of it.
- **Predictive NDR / layer assignment:** auto NDR and timing-driven layer assignment already exist commercially and in research (TILA, CPLA, MiniDelay); per-net labels ignore joint congestion, and router DRC behavior does not transfer across tools.
