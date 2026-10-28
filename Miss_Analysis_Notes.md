# Miss Analysis Notes (step 7, slim)

Oct 27, 2026. Re-timed data (per-PVT derates, OpenRCX RC corners), anchors `fast_cb` + `slow_cw`, g_setup = 0, g_hold = 40 ps, α = 1% per check.

Two configurations, as in the main results:

- **New design:** cross-design calibration split by design, linear model, 8 designs × 5 splits.
- **With history:** target-design calibration on k = 5 runs, LightGBM, 6 designs × 20 splits.

A **miss** is a violating (endpoint, scene) pair the pruner did not flag. A **wasted pair** is a flagged pair in a scene with no violations; it makes a clean scene run. Counts are summed over splits. Reproduce with `corner_prune.py ... --pairs` and `scripts/prune_misses.py`.

## What the data shows

**1. Misses almost never cost a violation.** 0.01% (new design) and 0.00% (with history) of missed pairs sit in a skipped scene. Every other missed pair is in a scene that runs because another pair flagged it, so the violation is still reported.

**2. With history, hold misses are the guarantee working as designed.** The miss rate is about 1% (the α), spread evenly: 0.6–1.3% in every design, 1.2% port-launched vs 1.0% register-launched. 99% of missed hold pairs are within 5 ps below g, and the median prediction error is 0.1 ps. These are coin-flip pairs at the guard band, which a 99% bound is allowed to miss.

**3. Setup misses are a transfer problem, concentrated in two scenes.** 77% (with history) to 95% (new design) of setup misses are at `slow_cb` and `slow_rcw`, the slow scenes that move away from the `slow_cw` anchor. The model predicts too much recovery: the median predicted slack is 49 ps (new design) and 85 ps (with history) above the true slack. Missed paths lose a median 67–73 ps of arrival time from `slow_cw` to the missed scene, against 33–39 ps for all setup violators, so they are the paths most sensitive to the RC corner. By design:

| | Setup miss rate |
| --- | --- |
| New design | ibex 17%, jpeg 15%, dynamic_node 10%, others ≤ 5% |
| With history | aes 14%, others 1–2.4% |

Calibrating on the design's own runs cuts the overall setup miss rate from 6.9% to 1.9% (the with-history set excludes cva6 and swerv_wrapper, which have too few runs, but both had near-zero setup misses as new designs). The remaining aes misses come from its two run regimes (tight clocks vs loose clocks), already noted in the outline.

**4. New-design hold misses are one design.** cva6 accounts for 94% of them, with a 28% miss rate against 0–7% elsewhere except dynamic_node (22%, but only 443 pairs). All are within 10 ps of g, with a median prediction error of +4 ps: a small optimistic offset for one design, right at the guard band.

**5. The prototype's port-path finding no longer holds.** On the Oct 23 prototype data, port-launched paths were 8% of violating hold pairs but 53% of unflagged ones. Now they are under-represented among new-design misses (2.6% of violators, 1.0% of misses) and proportionate with history (4.8% vs 5.5%). Several things changed at once (per-PVT derates, extracted RC corners, the `slow_cw` anchor, splitting by design), and the slim analysis does not isolate which one removed it.

**6. Port paths now cost savings instead of recall.** On a new design, 85% of wasted pairs are port-launched hold paths 5–50 ps above g, mostly at the fast and typical scenes. The model is pessimistic on them for designs it hasn't seen. With history, wasted pairs are mostly register-launched hold pairs 5–50 ps above g (some further) at the fast and typical scenes: the uncertainty band around g that a 99% bound has to cover.

## What was cut, and the theory for it

The slim analysis has each path's total arrival and required time at every scene. The full version would split those totals into components with per-path OpenSTA `report_checks` queries on the missed endpoints, at the base anchor and the missed scene:

- **Arrival (launch side):** input delay (SDC, for port paths) or launch clock latency (for register paths), plus data-path cell delay and wire delay.
- **Required (capture side):** capture clock latency, minus the library setup time or plus the hold time, adjusted by the CRPR credit.

Each component's validation check: the components must sum to the reported slack.

### How each component moves across corners (textbook STA)

| Component | PVT corner (SS / TT / FF) | RC corner (cw / rcw / cb / rcb) |
| --- | --- | --- |
| Input delay | Fixed: a constant from the SDC, the same at every scene (ORFS sets 20% of the clock period) | Fixed |
| Launch and capture clock latency | Scales with cell speed, larger at SS | Scales with clock-net RC; small on short clock nets |
| CRPR credit | Removes the latency shared by the launch and capture clock paths; grows with the shared latency, so larger at SS | Same |
| Data-path cell delay | Scales strongly with voltage and temperature (derated ±4.4–5.8%) | Through load C and input slew |
| Data-path wire delay | Weak | Strong; R and C move separately per corner and per layer |
| Library setup/hold time | Corner-dependent, slew-dependent | Through slew only |

### Theory for each finding

**Setup misses at `slow_cb` / `slow_rcw` (finding 3).** Between the `slow_cw` anchor and `slow_cb` or `slow_rcw`, PVT is fixed, so only wire R and C change. With the per-layer model, `cw` has the most C and the least R, `rcw` the most R with less coupling C, and `cb` the least C. A path's arrival drops from cw to cb in proportion to how much of its delay is C-driven (gate loads and short wires) and rises in proportion to how much is R-driven (long wires on the thin lower metals, where R varies most). The anchors give only the total arrival, not this split. A model trained on other designs learns an average split. Designs whose critical paths are more R-heavy (long lower-metal routes) recover less than predicted when C drops, which is the optimistic error seen on ibex and jpeg. A target-design history fixes most of it (6.9% → 1.9% setup misses) because the calibration runs share the design's wire mix. Remedies, untested: a per-path wire-delay fraction or net RC at the anchor as a feature, or a third anchor at `slow_rcw` for setup.

**cva6 hold offset (finding 4).** In a hold check, the clock latency shared between launch and capture is cancelled by CRPR, so what moves hold slack across corners is the data path and the unshared clock latency. cva6 is one of the two designs with SRAM macros and its clock tree differs from the training designs', so its unshared capture latency may well be longer. Unshared capture latency grows from FF to TT, which shrinks hold slack at typical scenes by a few picoseconds more than the training designs predict. That fits a +4 ps optimistic offset concentrated near g. The decomposition would confirm it by showing a larger unshared capture latency change on cva6's missed paths. Untested.

**Port paths (findings 5 and 6).** For a register-to-register hold path, launch and capture clock latency both scale with the corner and mostly cancel, so hold is worst at the fast corner. For a port-launched path the launch side is the fixed input delay, which doesn't scale, while capture latency does. Going from FF to SS, capture latency grows and nothing on the launch side offsets it, so hold slack can be worst at a slow corner. This explains why slow scenes are the worst hold scene for part of aes's endpoints, and why the prototype under-predicted port paths when its only slow anchor was `slow_rcw` with mostly register-path training data. The new data shows the opposite error on new designs (pessimistic, wasted rather than missed). One possible reading: with `slow_cw` as an anchor, port paths often get their base from the slow anchor while register paths get theirs from `fast_cb`, so a model trained mostly on fast-based register paths over-corrects when extrapolating from a slow base. The decomposition would test this by comparing the capture-latency change of wasted port pairs with the model's prediction. This is the weakest of the explanations here.

**Hold misses with history (finding 2).** These need no mechanism. A conformal threshold set to catch 99% of violators misses about 1% of them. They fall where predictions are least certain, which is within a few picoseconds of g. Noise sources at that scale: slew-dependent hold times, how derates apply to short paths, and extraction differences on short nets.

### Would the misses transfer to real designs?

This is the question the full decomposition answers best, and the likely one from engineers.

- **Port-path effects depend on the I/O constraints.** ORFS's template uses one input delay for every corner. Production I/O constraints are budgeted per corner and model external clock latency, so the port-path behaviour here is partly an artifact of the setup. That is already a stated limitation. Since port paths now cost savings rather than recall, the artifact makes the results conservative, not optimistic.
- **The setup transfer error is inherent.** Any design whose wire mix differs from the training designs will show it. The mitigation is the one already in the method: calibrate on the design's own runs where they exist, and on new designs treat the bound as best-effort (the violation-level result still held at ≥ 99.8%).
- **The near-g hold misses are inherent and harmless.** They are the bound working as intended.

## Talking points

- "When the pruner misses a pair, the violation is still reported 99.99% of the time, because another endpoint already makes that scene run."
- "With a few past runs, misses are about 1% and sit within 5 ps of the guard band: exactly the trade the 99% bound promises."
- "On a brand-new design, the main error is setup timing at RC corners away from the anchor, on designs whose wire mix differs from the training set. Calibrating on a few of the design's own runs cuts the setup miss rate from about 7% to 2%."
- "Port-launched paths, which drove misses in the prototype, now only cost some savings. Their behaviour depends on how I/O constraints are written, which is a known limitation of the ORFS setup."
- If asked about root cause per component: "We have the arrival and required totals, which point to the capture side for hold and to RC sensitivity for setup. A per-component OpenSTA breakdown would confirm it; it's about half a day and is the next step for a full writeup."
