# Predictive Hold Soft Costs for MCMM Setup Repair

Oct 21, 2026 · @Michael

## Problem

Setup repair in the slow corner speeds up cells that short paths also pass through, consuming fast-corner hold margin that hold repair later pays back with buffers. Setup fixers choose moves without pricing that downstream cost.

- **Mechanism:** an upsize or low-Vt swap that cuts delay on a long path also cuts delay on every short path through the same cell. In the fast corner, those short paths lose hold slack or go negative.
- **Cost:** each induced hold violation is repaired with delay buffers, adding area, leakage and routing pressure, and sometimes another setup–hold iteration.
- **How flows handle it today:** either as a hard constraint (reject setup moves that create hold violations) or reactively (fix hold afterward, re-optimizing setup to make room, as in Cadence Tempus's setup-during-hold-fixing mode).
- **The gap:** neither approach estimates the induced hold cost of a setup move as a continuous quantity at the moment the move is chosen. A hard filter rejects good tradeoffs and ignores margin erosion; reactive repair pays for conflicts after creating them.

**Research question:** does a learned estimate of induced hold cost, used as a soft penalty in setup move selection, reduce total repair cost (area, leakage, hold buffers) at equal setup WNS compared with hold-blind, hard-constraint and reactive approaches?

## Related work and positioning

The setup–hold coupling is well known and handled as a constraint or by reactive repair; no work found predicts the induced hold cost of individual setup moves with ML.

| Work | What it does | Gap relative to this project |
| --- | --- | --- |
| [Kim & Du, TCAD 1998](https://experts.umn.edu/en/publications/performance-optimization-by-gate-sizing-and-path-sensitization/) | Sizes gates on long and short paths; gate selection prevents long-path fixes from shrinking the shortest path | Hard rule, single corner, ISCAS'85 scale |
| [Min-area retiming + min-delay padding, 2004](https://unpaywall.org/10.1145%2F1013948.1013949) | Polynomial-time retiming under both setup and hold constraints | Retiming, not ECO sizing; constraint-based |
| [AMD, ISQED 2015](https://isqed.org/English/Archives/2015/Technical_Sessions/342.html) | Multi-corner Vt assignment under signoff timing with hold mitigation | Leakage-recovery direction; heuristic, not predictive |
| [PrimeTime fix\_eco\_timing](https://www.techdesignforums.com/practice/?p=6624) | Preserves setup margin during hold fixing; some setup methods documented as hold-safe | Margin/constraint guarding; default sizing behavior on hold not documented in sources found |
| Cadence Tempus setup-during-hold-fixing mode | Re-optimizes setup to make room for blocked hold fixes | Reactive: resolves conflicts after creating them (parameter name and doc source to confirm) |
| NVIDIA TransSizer, LEGO-Size, INSTA | Learned or differentiable gate sizing and fast GPU timing evaluation | Optimize sizing quality and speed; not the setup-to-hold cost crossing stages |

**Positioning:** this project isolates one decision inside setup repair, which candidate move to apply, and asks whether pricing its induced hold cost beats guarding hold with a hard filter or repairing it afterward.

## Proposed solution

A learned model predicts the hold cost each candidate setup move will induce in the fast corner, and the setup fixer subtracts that cost when ranking moves. Incremental STA still verifies every committed move.

**Move score** used by the setup fixer for candidate move m:

```latex
\text{score}(m) = \Delta S_{\text{setup}}^{\text{slow}}(m) - \lambda \, \hat{H}(m) - \mu \, \Delta A(m)
```

where the first term is the setup slack gained in the slow corner, Ĥ(m) is the predicted induced hold cost (hold-buffer area equivalent), ΔA(m) is the move's own area or leakage change, and λ, μ are swept weights.

**Inputs (per candidate move):**

- Move: cell master before and after (drive strength, Vt flavor), from Liberty
- Delay change of the cell per corner, from Liberty table lookup at the cell's current slew and load
- Hold context in the fast corner: hold slack of short paths through the cell, number of hold-critical endpoints in its fanout cone, worst and total slack within a guard band
- Local electrical context: fanout, load capacitance, input slew, side-fanout setup slack

**Output:** Ĥ(m), the predicted hold-repair cost the move will cause, in buffer-area units.

**Labels:** cheap per-move labels from incremental STA (change in fast-corner hold TNS, new hold-violating endpoints, guard-band erosion), converted to buffer cost by a calibration fit from full setup-then-hold runs (buffers inserted per ps of hold deficit).

**Model:** gradient-boosted trees (LightGBM) for the pilot; a GNN over the local fanout cone is an optional upgrade if the trees leave clear headroom.

**Why it could beat simpler options:** a first-order estimate (cell delay change against path slack) misses slew and load propagation, multiple overlapping short paths, buffer quantization and margin that later stages erode. Those are the effects the model is meant to capture.

&#91;embedded content: setup repair loop with learned hold cost · 7 steps, 1 decision\]

The model enters only the scoring step. STA verification and hold repair are identical across variants, so differences in hold buffers come from move choice alone.

## Experimental setup

The pilot runs in OpenROAD-flow-scripts on ASAP7, post-CTS with estimated parasitics, using resizing and Vt swaps only.

| Item | Choice | Note |
| --- | --- | --- |
| Flow | OpenROAD-flow-scripts (Yosys, OpenROAD, OpenSTA) | Open and fully instrumentable: every STA call and move is countable |
| PDK | ASAP7 (7nm predictive) | Multi-Vt libraries and meaningful wire effects; no LVF/POCV, so flat derates only |
| Corners | Slow (setup) and fast (hold), plus typical for reference | Use the slow, typical and fast Liberty sets shipped with ORFS ASAP7; confirm exact names and voltages from the files |
| Vt flavors | RVT, LVT, SLVT | ORFS loads RVT by default; LVT and SLVT must be added explicitly |
| Stage | Post-CTS, estimated parasitics | Avoids ECO routing and extraction; post-route is the deployment target, stated as future work |
| Move set | Cell resizing and Vt swap via `replace_cell` | Cleanly reversible; buffer insertion excluded to avoid legalization |
| Designs | Train on jpeg and dynamic_node; hold out ibex | jpeg and ibex use stock ORFS ASAP7 configs; dynamic_node is ported from the ORFS nangate45 config with the standard ASAP7 SDC template; avoid large fakeram memories |
| Clock targets | Swept tighter than ORFS defaults | Needed to create residual setup violations and setup–hold conflicts; disclosed, with several targets reported |
| Setup fixer | Own greedy fixer: worst endpoint first, enumerate moves on its path, apply best score, update timing | Same fixer for all variants isolates the effect of the cost term |
| Hold repair | OpenROAD `repair_timing -hold` | Identical across variants; its buffer count is the main outcome |

## Step-by-step breakdown

Nine days, with two go/no-go gates placed before any model work so a weak effect is caught early.

1. **Flow bring-up (Oct 22).** ORFS on ASAP7 with slow, typical and fast corners and RVT/LVT/SLVT loaded. Tighten clocks until setup violations remain after placement and CTS.
2. **Gate 1: does the effect exist? (Oct 22).** Run setup repair, then hold repair. Attribute each hold buffer to the setup moves upstream of it. 
3. **Setup fixer (Oct 23).** Greedy fixer with a pluggable cost term; verify it reaches setup WNS comparable to `repair_timing`.
4. **Data generation (Oct 23–24).** For each violating endpoint: enumerate moves, apply each, update timing, record per-corner slack changes and hold labels, undo. Run on all three designs.
5. **Baselines (Oct 25).** Implement hold-blind, hard-constraint, analytical soft cost and reactive iteration.
6. **Gate 2: is there headroom? (Oct 25).** Compare the analytical estimate against the measured labels. If it already ranks moves nearly as well as the labels, report the headroom result instead of training a model.
7. **Model (Oct 26).** Train the LightGBM hold-cost model on jpeg and dynamic_node; calibrate buffer cost from full runs.
8. **Evaluation (Oct 27).** Full setup-then-hold runs for all variants on held-out ibex, swept over λ and clock targets.
9. **Ablations and figures (Oct 28).** Feature ablation, λ sweep, per-design breakdown.
10. **Writeup (Oct 29–30).** Final document and slides; deadline Oct 30, 11:59 PM. Problem, related work and method sections are drafted in parallel from day 1.

## Baselines and comparison metrics

All variants use the same setup fixer and the same hold repair, compared at equal setup WNS, so differences come only from how hold cost is handled.

**Variants:**

1. **Hold-blind:** setup score ignores hold entirely. Lower bound.
2. **Hard constraint:** reject any move that creates a fast-corner hold violation. Mirrors Kim & Du and constraint-style tool behavior. The main baseline to beat.
3. **Analytical soft cost:** penalty from first-order hold slack consumed (cell delay change in the fast corner against short-path slack).
4. **Reactive iteration:** setup repair, hold repair, setup repair again until convergence. Open-source stand-in for Tempus-style reactive resolution.
5. **Learned soft cost (proposed):** penalty from the model's predicted hold cost.
6. **Reference:** OpenROAD `repair_timing` setup then hold, for context only.

| Metric | Definition | Why it matters |
| --- | --- | --- |
| Hold buffers | Number and total area of buffers inserted by hold repair | Direct measure of induced hold cost |
| Total cell area | Area after setup and hold repair | Net PPA cost of closure |
| Leakage power | Total leakage after repair | Vt swaps trade leakage for speed |
| Setup WNS / TNS (slow) | Final setup timing | Held equal across variants; reported to show it |
| Hold WNS / TNS (fast) | Final hold timing | Confirms hold is fully closed |
| STA calls and runtime | Incremental timing updates and wall-clock for the full repair | Execution efficiency, including iteration count for variant 4 |
| Rejected-move regret | Setup gain forgone by moves variant 2 rejects but variant 5 accepts | Shows where a hard filter leaves value |
| Prediction quality | Ranking correlation and top-k agreement of predicted vs measured hold cost | Explains why variant 5 does or does not win |

**Primary claim tested:** variant 5 reaches the same setup WNS with fewer hold buffers and less total area or leakage than variants 2 and 4 on held-out ibex.

## Expected outcomes, risks and limitations

Every outcome yields a reportable result, because the measurement of induced hold cost stands on its own.

| Outcome | What it shows |
| --- | --- |
| Learned cost beats hard constraint and reactive iteration | Pricing hold cost during setup repair is cheaper than guarding or repairing it |
| Learned cost matches analytical cost | First-order estimates suffice; the contribution is the cost formulation and the measurement |
| Hard constraint or reactive iteration is already near best | Existing practice is close to optimal on these designs, quantified against the alternatives |

| Risk | Mitigation |
| --- | --- |
| Setup repair induces few hold buffers on small designs | Gate 1 on day 1; tighter clocks; fallback project ready |
| Too few residual violations at default clocks | Clock sweep, disclosed and reported at several targets |
| Model fails to generalize to held-out ibex | Report it; per-design results and the analytical baseline still stand |
| Own setup fixer is weaker than `repair_timing` | Report `repair_timing` as reference; all claims are relative within one fixer |

**Limitations to state up front:**

- ASAP7 is predictive and has no variation (LVF/POCV) data, so results use flat derates.
- Post-CTS with estimated parasitics, not signoff post-route with extraction.
- Three designs; generalization claims stay modest.
- Move set excludes buffer insertion on the setup side.
