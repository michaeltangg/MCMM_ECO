# Risk-Controlled Pruning for Timing Closure: Conformal Guarantees for MCMM Corner Reduction and ECO Candidate Filtering

Oct 22, 2026 (updated Oct 27) · @Michael

## Problem

Timing closure repeats expensive evaluations that are rarely all needed: signoff STA runs every corner, and ECO repair runs incremental STA on every candidate move. Existing ways of skipping work are either heuristics or accurate predictors with no stated bound on what they miss.

- **Corners:** MCMM signoff runs STA at every combination of process, voltage and temperature (PVT) corner and RC extraction corner. Most corners never set the worst slack for most paths, but which ones matter is path-dependent. On our data, hold paths launched from input ports are worst at the slow corner (their input delay does not scale with the corner while the capture clock does), while self-loop and register-to-register hold paths are worst at the fast corner.
- **ECO candidates:** a repair loop enumerates many resize moves per violating endpoint and verifies each with incremental STA, though only the best one is applied.
- **How it is handled today:** dominant-scenario selection and dominance relations (heuristic), ML prediction of unobserved corners (accurate on average, no guarantee), and scenario compression in commercial tools. ML gate sizers improve solution quality but do not prune candidates with a stated error bound.
- **The gap:** none of these lets the engineer choose an acceptable miss rate and have the pruner provably stay under it. Verification runs need that property; average-error statistics do not provide it.

**Research question:** can conformal calibration turn a learned timing predictor into a pruner with a user-chosen bound on missed violations (corners) or lost best moves (ECO), how much STA work does it save at each bound, and does the guarantee survive transfer to a design it was not calibrated on?

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

**Target use:** the signoff-quality STA runs repeated during the closure loop (for example after each ECO round), which today run either every scene or a dominant subset with no bound on misses. The final tapeout run still runs every scene. Scenes run in parallel on a farm, so savings are reported as compute, not wall-clock.

## Proposed solution

One method, two applications: a learned predictor ranks expensive evaluations, conformal calibration sets the pruning threshold so the miss rate stays below a user-chosen α, and only the retained evaluations are run. Setup and hold each get their own α (α_setup, α_hold), because a hold escape after silicon fails at every frequency, while a setup escape can be binned.

### Part A (core): corner pruning with guaranteed violation recall

Run STA at two anchor scenes, A = {`fast_cb`, `slow_rcw`}. For every endpoint e, every other scene c and each check, a model predicts slack ŝ_c(e).

**Calibration (class-conditional split conformal, per check).** On calibration runs where every scene was run, take the n endpoint–scene pairs that truly violate (slack below guard band g). Set the threshold at their conformal quantile of predicted slack:

```latex
\hat{\tau} = \hat{s}_{(k)}, \quad k = \left\lceil (1-\alpha)(n+1) \right\rceil
\quad\Rightarrow\quad
\Pr\!\left(\hat{s}_c(e) \le \hat{\tau} \;\middle|\; s_c(e) < g\right) \ge 1-\alpha
```

where ŝ_(k) is the k-th smallest predicted slack among calibration violators. A pair is flagged if ŝ_c(e) ≤ τ̂.

**Decision.** The decision unit is the scene, because loading the design, the SPEF and `update_timing` take over 99% of a scene's runtime and are shared by both checks. A scene runs if it is an anchor or if any endpoint is flagged by either check; otherwise it is skipped. Guarantee per check: at least 1−α of violating pairs are flagged (pair recall). Violation recall, the share of violations in scenes that run, can only be higher, because a run scene catches every violation in it, flagged or not.

**Two calibration modes.**

- **New design:** calibrate on other designs. Violation recall stays ≥ 99.7%, but only because flagged endpoints pull whole scenes in: pair recall, the guaranteed quantity, fails on designs whose violators differ from the calibration designs (aes, dynamic_node), and savings vary strongly with which runs land in calibration.
- **Design with a few full runs:** calibrate on those runs. Pair recall then tracks 1−α within about one point, so α means what it says.

Exchangeability holds across runs, not across pairs within a run, so expect a shortfall of about one point against 1−α; state it, or use a run-clustered calibration if it matters.

**Inputs (per endpoint, per check):**

- **Main (F1):** slack, arrival and required time at both anchors. These come from the standard scene output, so no extra STA queries are needed.
- **Ablation (F2):** worst hold path per startpoint class (input port, other register, same register) at each anchor, with capture clock delay, CRPR credit and hold time. Helps with a single anchor; did not help with two.
- **Not implemented (ablation candidates):** data-path cell vs wire delay, stage count, cell mix, slew and load, clock-path makeup. Expected to matter with real multi-corner extraction more than with scaled RC corners.

**Model:** LightGBM, one model per target scene and check, predicting the change from the lower anchor slack, with extra weight on near-critical pairs. Kahng-style linear regression is the accuracy baseline. Any gradient-boosted tree model would do; the conformal step is model-agnostic, so a worse model gives a looser threshold and fewer skipped scenes, never a broken guarantee.

### Part B (stretch, gated): ECO candidate pruning with best-move retention

Inside a greedy setup fixer (worst endpoint first, enumerate resize moves on its path), a model predicts each candidate's slack gain ĝ(m). Only candidates within λ of the top prediction are verified with incremental STA:

```latex
K_\lambda = \{\, m : \hat{g}(m) \ge \max_{m'} \hat{g}(m') - \lambda \,\}, \qquad
\lambda_i = \max_{m'} \hat{g}(m') - \hat{g}(m_i^\star)
```

where m*_i is the STA-measured best move in calibration instance i. λ̂ is the conformal quantile of the λ_i, giving Pr(m* ∈ K) ≥ 1−α under exchangeability.

**The interesting part:** exchangeability is strained here, because candidates change as repair progresses. Measure coverage across early, middle and late repair iterations, and compare static calibration against adaptive conformal inference if coverage drifts.

&#91;flow: anchor STA → predict slack at other scenes → conformal threshold per check (α_setup, α_hold) → run flagged scenes → report misses\]

## Experimental setup

Signoff-style STA over PVT × RC scenes on ASAP7, chosen at Gate 1. The method consumes only STA outputs, so it transfers to commercial STA unchanged.

| Item | Choice | Note |
| --- | --- | --- |
| Flow | OpenROAD-flow-scripts, standalone OpenSTA per scene | Fully scriptable; every scene timed by phase |
| PDK | ASAP7 (7nm predictive) | Three PVT corners: SS 0.63 V 100 C, TT 0.70 V 25 C, FF 0.77 V 0 C |
| Scenes | 3 PVT × 4 RC = 12 | RC corners `cw`, `rcw`, `cb`, `rcb` extracted separately by OpenRCX with per-layer rules: a geometric ±3σ model of line width (±2.7 nm on every layer), metal thickness (±10%) and dielectric height (±5%), so thin lower metals vary more and coupling and ground C move differently. Prototype results used R and C scaled from one SPEF |
| Derates | Cells ±5.8% / ±5.0% / ±4.4% at SS / TT / FF; nets ±3% at every scene, early/late. Prototype results used flat ±5% cells | Cell derates scaled from ±5% at TT by the gate-overdrive ratio (0.70 − V_th)/(V_DD − V_th), alpha-power law, ASAP7 RVT V_th = 0.17 V (every design uses RVT cells only). Nets flat: supply voltage changes gate delay, not wire delay; per-layer wire variation is in the RC corners. CRPR on (OpenSTA default). No clock uncertainty (a flat uncertainty only shifts g). Rationale and sources in references.md |
| Guard bands | g_setup = 0, g_hold = 40 ps | Literature puts post-route hold margin at 20–40 ps and signoff remainder at about 5 ps. Derates cover about 10 ps of that; g covers the unmodelled rest (crosstalk, uncertainty, extraction) |
| Stage | Post-route, extracted SPEF from the ORFS final stage | Signoff-like; per-corner extraction with modelled, not foundry, BEOL variation (limitation) |
| Designs | aes, dynamic_node, ibex, jpeg, riscv32i, ethmac, cva6, swerv_wrapper | Every design is held out in turn; SRAM-pin endpoints dropped in the macro designs |
| Data variety | 61 runs, 4–11 per design: clock targets plus utilization variants | Global placement has no seed; utilization variants stand in for seeds |
| Anchors | `fast_cb` + `slow_cw` | With extracted RC corners, `slow_cw` is the worst setup scene for every near-critical endpoint and `fast_cb` the worst hold scene for 93%. With scaled corners `slow_cw` and `slow_rcw` were near-tied and the prototype used `slow_rcw`; kept there, it cuts riscv32i's target-design savings from 33% to 2% |
| Evaluation | Leave-one-design-out; target-design calibration with k ∈ {1, 2, 3, 5} runs, 20 random splits | Cross-design and within-design calibration measured separately |
| ECO fixer (Part B) | Own greedy fixer, resize moves via `replace_cell` | Same fixer for pruned and unpruned runs |
| Model | Linear regression for new designs (cross-design calibration); LightGBM for target-design calibration | Linear extrapolates better when calibration designs are unseen (13.7 vs 7.9% skipped). LightGBM keeps default parameters: an 18-setting grid with nested leave-one-design-out selection gave 16.2–17.0% skipped, no gain |
| Conformal | Pair-level split conformal per check (Part A); conformal set calibration (Part B) | A few dozen lines of code; no library dependence |

## Step-by-step breakdown

Nine days, Oct 22–30, with go/no-go gates before any modeling and before starting Part B. Status as of Oct 27.

1. **Flow bring-up (Oct 22–24). Done.** aes, dynamic_node, ibex and jpeg on ASAP7 at calibrated clock targets; riscv32i and ethmac added Oct 23, cva6 and swerv_wrapper (with SRAM macros) Oct 24.
2. **Gate 1: is there anything to prune? (Oct 22). Passed.** With derates and g_hold = 40, the hold physics rule (`fast_rcb`) catches 14 of 635 violating endpoints in aes and 0 of 213 in dynamic_node. Setup's worst scene is always one of two slow scenes, but 34–45% of setup violations sit in other scenes.
3. **Dataset generation (Oct 23–25). Done.** 61 runs over eight designs × 12 derated scenes, per-endpoint setup and hold slack with the worst path's startpoint class, runtime per phase.
4. **Models and calibration (Oct 24–25). Done.** `scripts/corner_prune.py`: LightGBM and linear predictors, pair-level calibration per check, cross-design calibration (split by run or by design) and target-design calibration, per-launch-class (Mondrian) calibration and start-class features as options.
5. **Evaluation (Oct 25–27). Done.** Cross-design and target-design (k ∈ {1, 2, 3, 5}) results on all eight designs, pair recall by launch class, LightGBM vs linear (linear for new designs, LightGBM for target-design calibration), LightGBM tuning (no gain over defaults), baselines (`scripts/prune_baselines.py`, `corner_prune.py --margins`), α sweep per check, net runtime accounting and the trade-off figures (`scripts/prune_figure.py`).
6. **Re-time with layer-dependent RC corners and corner-dependent derates (Oct 26–27). Done.** All 61 runs re-timed overnight with `scripts/retime.sh`. Nominal re-extraction matches `6_final.spef`; ceilings are unchanged; the setup anchor moves to `slow_cw`. The linear-model RMSE check was dropped.
   - **RC corners:** per-corner OpenRCX rules files written from the stock ASAP7 `rcx_patterns.rules` with per-layer, per-type factors (thin lower metals vary more; coupling and ground C move differently), extracted from `6_final.odb` behind `RCX_CORNERS=1` in `scripts/corner_sta.sh` so the scaled corners stay reproducible. Checks: nominal re-extraction matches `6_final.spef`, WNS ordering across corners is plausible, cross-corner slack is less linear (linear-model RMSE before and after). Main risk: justifying the per-layer factors.
   - **Derates:** per PVT corner (larger at SS 0.63 V, smaller at FF 0.77 V) in `scripts/tcl/derate.tcl`, with the rationale recorded.
   - Rerun `corner_prune.py` cross and target with both models; check whether dominant scenes, ceilings and the anchor choice change.
7. **Miss analysis in STA terms (Oct 28).** For missed pairs (violating, not flagged) and wasted pairs (flagged in clean scenes), break the worst path into input delay, data-path delay, launch and capture clock latency, CRPR credit and setup/hold time at each anchor and the target scene, with OpenSTA queries kept out of the timed scene run. Tie port-launched hold misses to the fixed input delay against growing slow-corner capture latency. One figure by startpoint class and corner. About half a day.
8. **Ablations and figures (Oct 28).** F2 vs F1, one vs two anchors, guard band g, calibration-set size, near-critical weighting.
   - **Near-critical weighting:** weight 1 vs 10 on pairs within 50 ps of g, LightGBM and linear, cross (`--cal-split design`) and target modes, compared on scenes skipped at equal α with pair recall checked against 1−α. The weight is untuned and has no literature source, so this is its justification. If weight 1 does as well, drop the weighting. Needs a `--near-weight` flag in `corner_prune.py`; run on the re-timed data with anchors `fast_cb` + `slow_cw`.
9. **Writeup (Oct 29–30).** Final document and slides; update results, the RC-corner and derate rows of the setup table, and the limitations from the re-timed data. Deadline Oct 30, 11:59 PM.

Steps 5 and 7–9 hold about 3.5 days of work in 3. If the re-extraction slips past Oct 27, the scaled-RC results stay the main result and re-extraction is reported as a check on the designs it finished.

## Baselines and comparison metrics

**Part A variants:**

1. **Run all scenes:** ground truth and runtime ceiling.
2. **Physics rule:** the two anchors only (`slow_cw` for setup, `fast_cb` for hold).
3. **Dominant-scene heuristic:** keep every scene that was some violating endpoint's worst, learned from other designs (cross-design) or from other runs of the same design (same-design history).
4. **Point predictor + fixed margin:** same predictions with an empirical margin over g for both checks (Kahng / patent-style). Sweeping the margin and sweeping α give different curves, because conformal sets each check's threshold separately and runs every scene when calibration has too few violators for the bound. The comparison is whether a chosen point meets its recall target and how sensitive savings are to choosing it.
5. **Conformal pruner (proposed):** same predictor, conformal threshold per check.
6. **Oracle ceiling:** skip exactly the scenes with no violations.

**Part B variants:** no pruning; fixed top-k; analytical first-order gain estimate (cell delay change plus driver resistance × added input capacitance) with the same conformal step; learned gain predictor with conformal step.

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Pair recall | Fraction of violating (endpoint, scene) pairs flagged | The guaranteed quantity; ≥ 1−α |
| Violation recall | Fraction of violating pairs in scenes that run | What verification needs; ≥ pair recall |
| Endpoint recall | Fraction of violating endpoints seen in at least one scene that runs | What fixing needs; the heuristic's home metric |
| Worst-scene recall | Fraction of violating endpoints whose worst scene runs | Fixing against a non-worst scene under-fixes |
| Scenes skipped | Fraction of all 12 scenes not run (setup ∪ hold flags, anchors counted as run) | The payoff, as compute |
| Net runtime | Compute saved minus anchor runs, feature extraction, inference and calibration | Honest accounting |
| Coverage on new design | Pair and violation recall per held-out design, vs. number of target-design calibration runs | Tests exchangeability |
| Miss distribution | Misses by startpoint class, slack range, scene | Average coverage can hide clustered failures |
| Best-move retention (B) | Fraction of repair steps where the STA-best move survived pruning | The Part B guarantee |
| STA calls and final WNS/TNS (B) | Incremental timing updates per repair; final timing vs. unpruned fixer | Savings at equal quality |

**Primary claim tested:** for verification runs that need near-complete violation recall, the conformal pruner keeps violation recall ≥ 99% for both checks with a stated bound, and captures 39–77% of the available compute savings on a new design and 28–98% with five past runs (re-timed data, α = 1%). The dominance heuristic and the physics rule skip more but miss many violations and cannot be tuned toward full recall. The heuristic is not beaten on endpoint or worst-scene recall, and the writeup says so.

## Results on the re-timed data (Oct 27)

Per-PVT derates, OpenRCX RC corners, anchors `fast_cb` + `slow_cw`, g_setup = 0, g_hold = 40, α = 1% per check unless stated. "New design" is cross-design calibration split by design with the linear model (5 splits); "with history" is target-design calibration on k = 5 runs with LightGBM (20 splits, the six designs with more than five runs). Compute saved is net of the anchors and model inference, from measured per-scene STA runtimes. Figures: `work/figures/tradeoff.png`, `threshold.png`.

- **Pruner vs heuristics:**

  | Method | Compute saved | Violations caught (setup / hold) |
  | --- | --- | --- |
  | Conformal pruner, new design | 14% (oracle 22%) | 100 / 100%; worst split 99.8% |
  | Conformal pruner, with history | 16% (oracle 29%) | 100 / 100% in every split |
  | Physics rule (anchors only) | 83% | 29–52% / 18–28% |
  | Dominant scenes, other designs | 50% | 47–57% / 53–100% |
  | Dominant scenes, past runs of the design | 58–83% | 30–52% / 25–91% |

  The heuristics' extra savings come from skipping scenes with violations: cva6, ethmac and swerv_wrapper have no clean scene, yet the heuristics skip 50–83% of their scenes. They still reach about 100% endpoint recall.
- **Per design, share of the oracle's savings captured:** new design aes 39%, dynamic_node 71%, ibex 77%, jpeg 55%, riscv32i 77%; with history aes 32%, dynamic_node 28%, ibex 94%, jpeg 79%, riscv32i 98%. cva6, ethmac and swerv_wrapper have nothing to save and the pruner skips nothing.
- **Pair recall:** with history it averages about 98% (aes 91–92%). On a new design it varies by design (ibex setup 83%, dynamic_node hold 78%), so the bound holds only with target-design calibration.
- **α sweep:** savings rise from 14 to 20% (new design) and 16 to 21% (with history) between α = 1% and 20%, while violation recall stays ≥ 99.1% in every split. Loosening α_hold moves savings about 5 points; α_setup about 1, because `slow_cw` is the worst setup scene for every endpoint.
- **Fixed margin:** the same predictions with no margin (flag predicted slack below g) save 17% (new design) and 24% (with history), more than conformal at α = 1%, but a 10 ps margin drops savings to about 5%. Conformal's median hold threshold lands within 2 ps of g; the gap comes from designs whose calibration runs hold too few hold violators for the bound (mostly dynamic_node), where conformal runs every scene and the 0 ps margin prunes and misses violations (99.1% violation recall in its worst split).
- **Runtime:** a full 12-scene STA takes a median 70 s per run (43–649 s); the two anchors are 17% of it. Inference per run is 0.01% of STA with the linear model and 1.2% with LightGBM (upper bound, measured with six designs in parallel). One-time model fit: 1.2 s linear, about 106 s LightGBM; calibration under 0.1 s.
- **Anchor choice:** with OpenRCX corners `slow_cw` is the worst setup scene for every near-critical endpoint; keeping `slow_rcw` leaves 79% of violating setup pairs below both anchors and cuts riscv32i's savings with history from 33% to 2%.
- **LightGBM tuning:** 18 settings (num_leaves, n_estimators, min_child_samples) with nested leave-one-design-out selection give 16.2–17.0% scenes skipped at k = 5, the same as the defaults.

## Results to date (prototype, Oct 23)

Prototype scripts live outside the repo; numbers below are from derated STA, g_setup = 0, g_hold = 40.

- **Derates:** hold slack drops by a median of 7–12 ps per design, up to 42 ps. Self-loops lose least, because CRPR cancels their clock pessimism; port-launched and long-branch register paths lose most.
- **Prediction is easy with two anchors:** linear regression reaches 1.4–1.5 ps RMSE on near-critical hold pairs. Largely by construction: scaled RC corners make cross-corner slack nearly linear.
- **One anchor:** `fast_cb` alone cannot see slow-corner port paths (4% hold recall on aes). `slow_rcw` alone plus F2 holds recall but skips less than two anchors with F1.
- **Main configuration, cross-design, α = 1% per check, 5 random fit/calibration splits:** 34 ± 1 / 46 ± 11 / 13 ± 12 / 6 ± 4% of scenes skipped (aes / dynamic_node / ibex / jpeg) against ceilings of 43 / 55 / 27 / 15% (anchors always run). Violation recall is 100% in every split. Pair recall misses its target on aes (setup 81%, hold 54%) and dynamic_node (hold 68 ± 34%). An earlier single split gave 35 / 52 / 28 / 10% and was a favourable draw.
- **Misses cluster by startpoint class and sit near the guard band:** port-launched paths are 8% of violating hold pairs but 53% of unflagged ones, and every unflagged hold violator in aes and dynamic_node is port-launched. 84% of unflagged hold violators are within 10 ps of g. Only 0.2% of unflagged violators fall in a skipped scene.
- **α_hold = 0.1%** needs about 1,000 violating calibration pairs. With target-design calibration only jpeg and aes (k = 5) have enough; elsewhere it runs every scene, and on aes it still under-covers (98.7%).
- **Heuristics:** the same-design dominance heuristic skips 58–83% with 54–65% setup and 56–82% hold violation recall; the physics rule skips 83% at 20–65%. Both reach about 100% endpoint and worst-scene recall.
- **Cross-design α does not predict violation recall:** at α = 50%, hold violation recall is still ≥ 99.8%.
- **Target-design calibration:** pair recall tracks 1−α within about one point on ibex, jpeg and dynamic_node; violation recall stays 96–100%. aes runs span two regimes (port-path hold at tight clocks, none at loose clocks), so a few calibration runs under-cover (setup pair recall 84% at α = 1% with k = 1). Designs with few violators (dynamic_node hold) fall back to running every scene at small α.

## Risks and limitations

| Risk | Mitigation |
| --- | --- |
| Savings capped by the ceiling (15–55% of scenes are clean) | Report savings relative to the ceiling; more corners would raise it, but more scaled RC corners would inflate savings artificially |
| Prediction looks trivial: with extracted RC corners one slow scene is the worst setup scene for every endpoint | State it; the comparison is violations caught per scene, where the heuristics miss about half; put the contribution in the guarantee, anchor choice and transfer analysis |
| Too few violations for calibration in some designs | g_hold = 40; fall back to cross-design calibration; report per design |
| STA runtime per scene is small (2–8 s) | Report compute fractions and scaling with corner count; keep anchor-side extraction to the standard outputs (F2's per-class query costs about 1.8 s per anchor) |
| Part B not reached | Part A stands alone; Part B becomes a short preliminary section |

**Limitations to state up front:**

- ASAP7 is predictive with only three PVT corners and no LVF/POCV data, so derates are textbook values, not foundry tables.
- Per-corner derates are scaled from a textbook TT value by an overdrive model of V_th-driven variation only. Variation that does not scale with overdrive (gate length, intra-cell parasitics) would make the true voltage dependence weaker, so the SS/FF spread is an upper bound on the voltage effect. Temperature lowers V_th at SS 100 C, which partly offsets the process shift. Foundry derate tables bundle more than V_th variation and do not always follow voltage monotonically.
- RC corners come from per-layer factors of a geometric model, not foundry rule decks. ASAP7 publishes no BEOL variation, so line-width and thickness magnitudes are taken from IRDS/ITRS roadmap targets and the dielectric-height value is assumed. Every parameter sits at ±3σ together, which is pessimistic against statistical corners.
- Non-trivial hold dominance comes mainly from ORFS's I/O constraint template (input delay = 20% of the clock period) combined with derates. It is real STA behaviour, but is presented as I/O-launched hold paths, not temperature inversion.
- The guarantee is marginal (average over pairs), not per-path. It assumes exchangeability, which holds across runs rather than across pairs within a run, and breaks across designs.
- Few designs; generalization claims stay modest.

## Future work

- **Risk-controlled hold-cost prediction for setup repair.** Setup fixes in the slow corner speed up cells that short paths share, consuming fast-corner hold margin that hold repair later pays back with buffers. The calibration machinery used here extends directly: alongside predicted setup gain, each candidate move would carry a conformal upper bound on the fast-corner hold slack it consumes, so moves are penalized only when the bound indicates likely new hold violations. The corner pruner decides which slow and fast corners need full analysis. This requires a flow that models useful skew and scan-path hold fixing realistically, so it is left to evaluation in an industrial setting.
- **Signoff extraction corners.** Replace the modelled per-layer RC factors with foundry extraction rule decks per RC corner.
- **Adaptive calibration across designs.** Weighted or adaptive conformal methods to keep the guarantee valid on new designs with little calibration data, including pooling cross-design and target-design calibration data.
- **Endpoint-level guarantee.** Bound missed endpoints instead of missed pairs, to compete with the dominance heuristic on its own metric.

## Approaches considered and rejected

- **Ripple-aware ECO pruning (predict net path Δslack including driver loading):** driver loading is already handled by sizers and by incremental STA; a first-order formula captures most of it.
- **Predictive NDR / layer assignment:** auto NDR and timing-driven layer assignment already exist commercially and in research (TILA, CPLA, MiniDelay); per-net labels ignore joint congestion, and router DRC behavior does not transfer across tools.
- **Run-level conformal risk control (calibrate the per-run miss fraction directly):** skips more, but breaks across designs (ibex hold violation recall 41% at α = 10%) and cannot go below α ≈ 7% with 13–15 calibration runs.
- **Scene-level conformal (score = lowest predicted slack in a scene):** fails its guarantee by up to 13–15 points with target-design calibration (2–25 violating calibration scenes), and skips more than pair-level only by losing violation recall.
- **`fast_cb` as the only anchor:** misses slow-corner port-path hold violations.
- **Per-class startpoint features as the default:** extra STA query cost; helped only in the one-anchor configuration. Kept as an ablation.
- **XGBoost:** not compared; equivalent on data of this size, and the guarantee does not depend on the model.
