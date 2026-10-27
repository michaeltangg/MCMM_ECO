# References

Sources used in [Project_Outline_Risk_Controlled_Pruning.md](Project_Outline_Risk_Controlled_Pruning.md) and the claim each one supports. Add new sources under the matching section; "Used in" names the outline section that cites it.

## Multi-corner timing prediction

**Kahng et al., "Unobserved Corner" Prediction, DATE 2019.** <https://ieeexplore.ieee.org/abstract/document/8715102>
- Claim: ML prediction of unobserved corners is accurate on average but gives no bound on missed violations. Linear regression predicts 48 unobserved corners from 10 observed with <0.5% relative RMSE on a 1M-instance 16nm design.
- Also: source of the linear-regression accuracy baseline and the point predictor + fixed margin baseline.
- Used in: Problem, Related work, Proposed solution (Model), Baselines.

**ML multi-corner timing prediction, Electronics 2022.** <https://www.mdpi.com/2079-9292/11/10/1571>
- Claim: dominant (observed) corner combinations can be chosen for high prediction accuracy, again with accuracy statistics rather than a guarantee.
- Used in: Related work.

## Industrial corner and scenario reduction

**Synopsys patent: signoff-safe multi-corner reduction.** <https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12675622>
- Claim: industry uses a learned safety check (one model judges whether prediction error is under a threshold, a second predicts slack), which is not a distribution-free bound.
- Also: basis for the point predictor + fixed margin baseline ("patent-style").
- Used in: Related work, Baselines.

**Synopsys scenario reduction via corner dominance (US8707241).** <https://patents.google.com/patent/US8707241>
- Claim: dominance-based scenario reduction is rule-based (drops scenarios dominated by another corner in the same mode) with no per-path learning.
- Used in: Problem ("dominance relations (heuristic)"), Related work.

**Synopsys Adaptive Scenario Compression (Semiconductor Engineering).** <https://semiengineering.com/predictable-design-optimization-and-closure-with-adaptive-scenario-compression/>
- Claim: commercial tools compress many scenarios into fewer views, with no stated miss bound.
- Used in: Problem ("scenario compression in commercial tools"), Related work.

**Cadence MMMC view pruning patent.** <https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10133842>
- Claim: per-node analysis-view pruning in commercial tools uses heuristic dominance.
- Used in: Related work.

## Prediction model

**Ke et al., "LightGBM: A Highly Efficient Gradient Boosting Decision Tree," NeurIPS 2017.** <https://papers.nips.cc/paper/6907-lightgbm-a-highly-efficient-gradient-boosting-decision-tree>
- Claim: names the model used (a gradient-boosted decision tree implementation built for speed on large data). It supports only the choice of tool. The LightGBM settings (500 trees, learning rate 0.05), the near-critical weighting (10× within 50 ps of g) and the change-from-lower-anchor target are untuned design choices with no literature source.
- Used in: Proposed solution (Model), Experimental setup (Model row).

## Conformal methods

**Lei, G'Sell, Rinaldo, Tibshirani & Wasserman, "Distribution-Free Predictive Inference for Regression," JASA 113(523):1094–1111, 2018.** <https://doi.org/10.1080/01621459.2017.1307116> (preprint: <https://arxiv.org/abs/1604.04173>)
- Claim: split conformal gives finite-sample marginal coverage "using any estimator of the regression function", with no distributional assumptions beyond exchangeability. This is why the conformal step works with any model: LightGBM or linear, weighted or not.
- Used in: Proposed solution (Model: "the conformal step is model-agnostic"), Experimental setup (Conformal row).

**Angelopoulos & Bates, "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification," arXiv 2107.07511, 2021.** <https://arxiv.org/abs/2107.07511>
- Claim: the guarantee holds "no matter what (possibly incorrect) model is used" (Sec. 1). If the scores rank poorly, the guarantee still holds but the sets are useless, which supports "a worse model gives a looser threshold … never a broken guarantee." Sec. 1 gives the ⌈(n+1)(1−α)⌉ quantile used for τ̂. Sec. 4.2 ("Class-Conditional Conformal Prediction") calibrates each class separately, which is the basis for calibrating only on true violators (the guarantee is conditional on s_c(e) < g), per check, and for the per-launch-class (Mondrian) option.
- Used in: Proposed solution (Calibration, Model), Step 4 (per-launch-class calibration).

**Liang, Zhu & Barber, "Conformal prediction after data-dependent model selection," arXiv 2408.07066 (v4, Apr 2026; preprint, no journal reference).** <https://arxiv.org/abs/2408.07066> · code: <https://github.com/RuitingL/ModSel-CP>
- Claim: picking a model with the same calibration set used to calibrate it loses coverage through selection bias (abstract). On real data with 400 models, n = 500 and 90% target coverage, naive selection covers 88.1%, while ModSel-CP covers 89.9% at width 14.18, against 14.01 for the best single model.
- Fix: ModSel-CP restores finite-sample coverage without another split by treating all n+1 points symmetrically, a special case of full conformal (App. A.2). Thm. 3.2 gives a closed form: competing set M = {λ : L(λ, q̂₋(λ)) ≤ L(λ̂, q̂(λ̂))}, where q̂₋ is one order statistic below q̂. Thm. 3.2 sandwiches the set between a ≤ and a < version, which coincide only when losses don't tie.
- Conditions: models are pretrained (independent of calibration data). The loss is non-decreasing in the threshold, symmetric in the points, and a function of features only, not labels (footnote 3).
- Use here: supports choosing linear vs LightGBM by a fixed rule (design seen in fit or not) rather than by calibration results. It is also the method to use if the model is ever chosen per design from calibration results.
- Used in: model-choice rule (proposed; not yet in the outline).

**Yang & Kuchibhotla, "Selection and Aggregation of Conformal Prediction Sets," JASA 120(549):435–447, 2025.** <https://doi.org/10.1080/01621459.2024.2344700> (preprint: <https://arxiv.org/abs/2104.13871>)
- Claim: picking the smallest split-conformal set among K models with no correction has i.i.d. coverage ≥ (1 + 1/n)(1 − α) − (√(log(2K)/2) + 1/3)/√n (Thm. 1). With K = 2 at α = 1%, the bound allows a coverage loss of up to 10.7 points at n = 100, 7.8 at n = 200 and 3.6 at n = 1000. That is far above α, so picking "whichever skips more" cannot be defended.
- Fix: selecting on one split and calibrating on another restores exact coverage under exchangeability (Thm. 3), at the cost of sample size.
- Used in: model-choice rule (proposed; not yet in the outline).

**Conformalized Vmin prediction, DATE 2024.** <https://arxiv.org/html/2406.18536v1>
- Claim: conformal prediction (conformalized quantile regression with a coverage guarantee) has been applied in hardware test/manufacturing, but not to STA.
- Used in: Related work.

**Diffusion Mutation Kernels, arXiv 2608.27649.** <https://arxiv.org/pdf/2608.27649>
- Claim: conformal risk control has been used to prune candidates with a winner-preservation guarantee in circuit/physical design search; closest method precedent for Part B.
- Used in: Related work.

**Certified candidate-set pruning, EMNLP 2022.** <https://arxiv.org/pdf/2205.09638>
- Claim: conformal candidate pruning with error control exists outside EDA.
- Used in: Related work.

**Conformal HW-NAS filters, arXiv 2610.03127.** <https://arxiv.org/pdf/2610.03127>
- Claim: exchangeability breaks inside an adaptive search loop, the caveat that applies directly to Part B's ECO loop.
- Used in: Related work, Part B ("exchangeability is strained here").

## ML gate sizing and STA

**RL-Sizer, DAC 2021.** <https://gtcad.gatech.edu/www/papers/dac21-3.pdf>
- Claim: learned gate sizers improve solution quality but do not prune candidates with a stated error bound.
- Used in: Problem, Related work.

**Lu et al. (NVIDIA), "LEGO-Size: LLM-Enhanced GPU-Optimized Signoff-Accurate Differentiable VLSI Gate Sizing in Advanced Nodes," ISPD 2025, pp. 152–162.** <https://doi.org/10.1145/3698364.3705351> (slides: <https://ispd.cc/ispd2026/slides/2025/protected/10_2_slides.pdf>)
- Claim: same as RL-Sizer (differentiable sizing; quality, not guaranteed pruning).
- Used in: Problem, Related work.

**TimeBoost.** <https://www.sciencedirect.com/science/article/pii/S1434841125002110>
- Claim: ML (XGBoost selecting an STA method per stage) is used to speed up STA, without guaranteed candidate pruning.
- Used in: Related work.

## Derates

Per-corner cell derates (`DERATE=pvt`): ±5.8% / ±5.0% / ±4.4% at SS 0.63 V / TT 0.70 V / FF 0.77 V, nets ±3% at every corner. The voltage scaling is derived, not taken from foundry tables, and is a modelling choice.

- Derivation: under the alpha-power law, delay ∝ V_DD / (V_DD − V_th)^α, so its sensitivity to V_th is α / (V_DD − V_th) and V_th-driven variation gives σ_d/μ_d ≈ α·σ_Vth / (V_DD − V_th). Relative to TT the derate scales by (0.70 − V_th)/(V_DD − V_th); α and σ_Vth cancel. With RVT V_th = 0.17 V the overdrive is 0.46 / 0.53 / 0.60 V and the ratio 1.15 / 1.00 / 0.88. Using Vtlin = 0.19 V instead gives the same rounded values.
- Every design uses RVT cells only (ORFS ASAP7 default, `ASAP7_USE_VT` unset), so the RVT V_th applies to every cell.
- Sensitivity case: a ±30 mV process V_th shift at SS/FF (an assumption, not ASAP7 data) gives ±6.2% at SS and ±4.2% at FF. Exact values could be read from the SS/FF BSIM-CMG model cards.
- Consistency check (own calculation): the ring-oscillator spread below (Indian Institute of Science, 65 nm test chip), 17% at 1.0 V to 29% at 0.8 V, is reproduced by the overdrive ratio for V_th ≈ 0.52 V, plausible for 65 nm.
- Used in: Experimental setup (Derates row), Limitations, `scripts/tcl/derate.tcl`.

**Sakurai & Newton, "Alpha-Power Law MOSFET Model and its Applications to CMOS Inverter Delay and Other Formulas," IEEE JSSC, 1990.** <https://courses.ece.ucsb.edu/ECE225/225-W06Banerjee/Lectures/Lecture3_Ref/alpha.pdf>
- Claim: gate delay ∝ V_DD / (V_DD − V_th)^α; basis of the overdrive scaling.
- Used in: Experimental setup (Derates row).

**Vashishtha, Vangala & Clark, "ASAP7 Predictive Design Kit Development and Cell Design Technology Co-optimization," ICCAD 2017 embedded tutorial.** <https://asap.asu.edu/wp-content/uploads/sites/47/2021/11/iccad17_asu_asap7_171115c.pdf>
- Claim: ASAP7 typical-corner NMOS at 25 C has Vtsat 0.25 / 0.17 / 0.10 / 0.04 V (Vtlin 0.27 / 0.19 / 0.12 / 0.06 V) for SRAM / RVT / LVT / SLVT.
- Used in: Experimental setup (Derates row).

**Clark et al., "ASAP7: A 7-nm finFET predictive process design kit," Microelectronics Journal, 2016.**
- Claim: ASAP7 device flavors and the TT / SS / FF process corners.
- Used in: Experimental setup (PDK, Derates rows).

**Elzeftawi & Tseng, "Addressing Process Variation and Reducing Timing Pessimism at 16nm and Below," Cadence white paper.** <https://www.cadence.com/en_US/home/resources/white-papers/addressing-process-variation-and-reducing-timing-pessimism-at-16nm-and-below-wp.html>
- Claim: standard library margins are adequate when a design runs at or above 3× the transistor threshold voltage (an informal guideline). For RVT, 3 × 0.17 = 0.51 V, below all three ASAP7 supplies, so the voltage scaling should be mild.
- Used in: Experimental setup (Derates row).

**Dreslinski et al., "Near-Threshold Computing: Reclaiming Moore's Law Through Energy Efficient Integrated Circuits," Proc. IEEE 98(2), 2010.** <https://courses.grainger.illinois.edu/CS534/fa2021/reading_list/5a.pdf>
- Claim: performance variation from global process variation rises about 5×, from 30% (1.3×) at nominal voltage to as much as 400% (5×) at 400 mV. Outside the ASAP7 supply range; cited for direction only.
- Used in: Experimental setup (Derates row).

**US Patent 8,224,604, "Gate delay measurement circuit and method of determining a delay of a logic gate" (Indian Institute of Science).** <https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8224604>
- Claim: local ring-oscillator delay spread rises from 17% at 1.0 V to 29% at 0.8 V, measured on the inventors' 65 nm test chip (V_th not stated). Used for the consistency check.
- Used in: Experimental setup (Derates row).

**US Patent 7,174,523, "Variable sigma adjust methodology for static timing" (IBM).** <https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7174523>
- Claim: supply voltage affects gate delay but not wire delay, so net derates stay flat across PVT corners.
- Used in: Experimental setup (Derates row).

**US Patent 8,516,424, "Timing signoff system and method that takes static and dynamic voltage drop into account."** <https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8516424>
- Claim: foundry OCV margins need not follow voltage monotonically; its 40 nm example uses 2% at the worst-case corner and 3.5% at the best-case corner.
- Used in: Limitations.

## BEOL variation (RC corners)

OpenRCX RC corners (`RCX_CORNERS=1`, `scripts/rcx_corner_rules.py`) scale each metal layer's R, coupling C and ground C in the stock ASAP7 rules by a geometric ±3σ model: R ∝ 1/(w·t), coupling C ∝ t/s, ground C ∝ w/h, with s = w nominally. ASAP7 has no BEOL variation data ("Variation modeling is not directly supported by the ASAP7 PDK", Clark et al., MSE 2017), so every magnitude is imported:

- Width: 3σ CD 2.7 nm on every layer (IRDS 2021 metal CD control at 18 nm half pitch; imec's 3 nm from experimental data agrees). Keeping the same absolute CD on M4–M9 is an extrapolation; IRDS's percent-of-CD convention would instead give 15% on every layer and remove the layer dependence. Lower, tighter-pitch metals having larger relative spreads is supported only by older-node data (McGuinness 2008).
- Thickness: ±10% on every layer, the ITRS 2007 erosion thinning target (10% of height). It is one-sided and systematic with sigma unstated, applied here symmetrically. No measured 3σ thickness at ≤16 nm was found.
- Dielectric height: ±5%, no published value found at these nodes (uncited assumption).
- Corner geometry: Chan, Dobre & Kahng's foundry-derived definitions (Cw: W, T max, H min; Cb: the mirror; RCw: W, T, H min; RCb: W, T, H max). In RCw, coupling C falls while ground C changes little; a net fall in total C is an outcome of the model, not a sourced fact.
- All parameters at ±3σ together is pessimistic against statistical corners (Yamada & Oda 2006: a ±20% conventional range shrinks to ±10%; Chan, Dobre & Kahng 2014).
- Resulting factors, M1–M3 / M8–M9: cw R 0.79 / 0.85, coupling C 1.29 / 1.18, ground C 1.21 / 1.12; rcw R 1.31 / 1.19, coupling C 0.78 / 0.84, ground C 0.89 / 0.98. About 2–3× the old uniform ±10% scaling.
- Used in: Experimental setup (Scenes row), Limitations, `scripts/rcx_corner_rules.py`.

**IRDS 2021 Update, Lithography, Table LITH-1 (p. 2).** <https://irds.ieee.org/images/files/pdf/2021/2021IRDS_Litho.pdf>
- Claim: metal CD control (3σ) 2.7 / 2.3 / 1.8 nm at minimum metal half pitch 18 / 15 / 12 nm (2018 "7", 2020 "5", 2022 "3"). Roadmap target; the 2021 text notes the tables were not updated from the prior year. §4.1 gives a CDU specification of 15% of CD (stated for contact holes).
- Used in: BEOL variation (width).

**Karageorgos et al. (imec), "Impact of Interconnect Multiple-Patterning Variability on SRAMs," DATE 2015, pp. 609–612.** <https://past.date-conference.com/proceedings-archive/2015/pdf/0932.pdf>
- Claim: 3σ CD 3 nm for LE3, SADP core and EUV, SADP spacer 1.5 nm, at imec N10 M1, "based on in-house experimental data" (§II.A).
- Used in: BEOL variation (width, agreement).

**ITRS 2007 Edition, Interconnect, Table INTC2b (p. 9).** <https://www.semiconductors.org/wp-content/uploads/2018/08/2007Interconnect.pdf>
- Claim: Cu thinning at minimum pitch due to erosion = 10% × height (4 nm in 2018 at M1 half pitch 18 nm); total M1 resistance variability from CD, erosion and scattering 35% in 2018 (sigma unstated). 2007 projections.
- Used in: BEOL variation (thickness).

**Chan, Dobre & Kahng, "Improved Signoff Methodology with Tightened BEOL Corners," ICCD 2014, pp. 311–316.** <https://vlsicad.ucsd.edu/Publications/Conferences/321/c321.pdf>
- Claim: BEOL corner definitions by W, T, H direction (Table I), extracted from foundry BEOL corners; conventional all-±3σ corners are pessimistic.
- Used in: BEOL variation (corner geometry).

**Yamada & Oda (NEC), "Statistical Corner Conditions of Interconnect Delay (Corner LPE Specifications)," ASP-DAC 2006, pp. 706–711.** <https://www.cecs.uci.edu/~papers/aspdac06/pdf/p706_7C-1.pdf>
- Claim: RCmax sets conductor thicknesses at −3σ; an illustrative ±20% C or R range under conventional corners shrinks to ±10% with statistical corners (90 nm, §VI).
- Used in: BEOL variation (pessimism), Limitations.

**McGuinness (Freescale), "Variations, Margins, & Statistics," ISPD 2008 slides.** <http://www.ispd.cc/slides/2008/S3-1.pdf>
- Claim: capacitance 1σ variation 16% at 75 nm pitch, 12% at 140 nm, 10% at 360 nm (slide 7). Older node; supports larger relative spread on tighter pitch.
- Used in: BEOL variation (layer dependence).

**Clark, Vashishtha, Harris et al., "Design Flows and Collateral for the ASAP7 7nm FinFET Predictive Process Design Kit," MSE 2017.** <https://pages.hmc.edu/harris/research/asap7.pdf>
- Claim: "Variation modeling is not directly supported by the ASAP7 PDK."
- Used in: BEOL variation, Limitations.
