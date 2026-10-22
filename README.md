# Predictive hold soft costs for MCMM setup repair

See [Project_Outline.md](Project_Outline.md) for the research plan.

## Environment

OpenROAD-flow-scripts (ORFS) on ASAP7, run to post-CTS with three analysis corners and three Vt flavors loaded.

| Piece | Version / location |
| --- | --- |
| ORFS scripts | `third_party/OpenROAD-flow-scripts` @ `7421007` (clone, no submodules) |
| OpenROAD / OpenSTA | `26Q1-1207-g6fa7950acd` / 3.0, prebuilt arm64 in `$ORFS_TOOLS` |
| Yosys | 0.62 with `slang` plugin, prebuilt in `$ORFS_TOOLS` |
| Python | `.venv` (3.14), see `requirements.txt` |

| Corner | Liberty | VDD | Temp | Role |
| --- | --- | --- | --- | --- |
| `slow` | SS | 0.63 V | 100 C | setup; also the tightest hold corner on dynamic_node and jpeg |
| `typical` | TT | 0.70 V | 25 C | reference |
| `fast` | FF | 0.77 V | 0 C | hold; tightest hold corner on ibex |

Vt is the cell-name suffix: `_R` (RVT), `_L` (LVT), `_SL` (SLVT). A Vt swap is a `replace_cell` between masters that differ only in that suffix.

### One-time host setup (macOS)

```sh
brew install make bash gnu-sed     # ORFS needs GNU make >= 4, bash 5, GNU sed
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
git clone --filter=blob:none https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts third_party/OpenROAD-flow-scripts
git -C third_party/OpenROAD-flow-scripts checkout 7421007
```

The Homebrew formulae whose dylibs OpenROAD links against are pinned (`brew list --pinned`). Don't unpin or upgrade them before the deadline; that would break the prebuilt binary.

### Every shell

```sh
source env.sh
```

This puts GNU tools first on `PATH`, pins `OPENROAD_EXE`, `OPENSTA_EXE` and `YOSYS_EXE` to `$ORFS_TOOLS` (so Homebrew's yosys is never used), sets `FLOW_HOME` and `WORK_HOME=work/`, and activates `.venv`.

## Running the flow

```sh
scripts/run_flow.sh <design> [period_ps]      # designs: dynamic_node, jpeg, ibex
```

- Synthesis runs RVT-only. All three Vts are loaded from `1_synth.odb` onward, which is where LEFs are read.
- SLVT is reserved for post-CTS repair: [flow/load_hook.tcl](flow/load_hook.tcl) sets it `dont_use` in every stage up to CTS, so pre-CTS optimization may only use RVT and LVT. It's applied via `LAYER_PARASITICS_FILE`, because floorplan's repair ignores `DONT_USE_CELLS`. Pass `RESERVE_SLVT=0` when loading a checkpoint for repair that may use SLVT.
- The flow stops at CTS with `SKIP_CTS_REPAIR_TIMING=1`. `work/results/asap7/<design>/<variant>/4_cts.odb` is the experiment checkpoint: post-CTS, with setup and hold unrepaired.
- With `period_ps`, the design's SDC is copied with `clk_period` rewritten, and results go to the `p<period_ps>` variant. Without it, the variant is `base`.

Inspect a checkpoint under all corners:

```sh
make -C $FLOW_HOME DESIGN_CONFIG=$PROJECT_ROOT/flow/designs/asap7/<design>/config.mk \
  [FLOW_VARIANT=p<period>] run RUN_SCRIPT=$PROJECT_ROOT/scripts/tcl/check_mcmm.tcl
```

This writes `work/reports/<design>_<variant>_mcmm.json` with:

- per-corner setup and hold WNS, TNS and violator counts (in ps);
- a Vt census;
- a `replace_cell` round-trip check.

## Layout

| Path | Contents |
| --- | --- |
| `flow/common.mk` | MCMM corners, multi-Vt, CTS-repair skip; included by every design config |
| `flow/designs/asap7/<design>/` | Design configs (stock ORFS config + `common.mk`; dynamic_node is a new ASAP7 port) |
| `flow/clock_targets.mk` | Calibrated clock periods per design |
| `scripts/run_flow.sh` | Flow wrapper |
| `scripts/tcl/check_mcmm.tcl` | Checkpoint inspector |
| `work/` | ORFS `WORK_HOME`: logs, results, reports (ignored) |

## Notes for the experiments

- OpenSTA 3.0 calls corners "scenes". Use `sta::find_scene slow`, `sta::worst_slack_scene <scene> max|min`, `sta::total_negative_slack_scene_cmd`, and `report_checks -scenes <name>`. Values from the `sta::` functions are in seconds.
- `sta::endpoint_violation_count` ignores the active scene. Count violators per corner with `report_checks -scenes`.
- ORFS's floorplan stage runs `repair_timing -setup` with `vt_swap` on the synthesized netlist. With SLVT reserved, checkpoints contain only RVT and LVT. LVT is 0.3–2.5% of cells on dynamic_node and ibex, and 5.5–9% on jpeg, whose multiplier paths need about 1.9 ns at SS.

Deviations from stock ORFS configs, to disclose:

- `OPENROAD_HIERARCHICAL=0` with `SWAP_ARITH_OPERATORS` cleared (ibex and dynamic_node enable both upstream).
- `ABC_AREA=0` for jpeg (stock jpeg is 1), so all three designs synthesize for speed.
- dynamic_node uses the standard ASAP7 SDC template instead of the nangate45 per-port I/O delays.
- Clock targets in [flow/clock_targets.mk](flow/clock_targets.mk) are calibrated at SS, so they're looser than the ORFS defaults, which were tuned for FF.
