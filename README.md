# Risk-controlled pruning for timing closure

See [Project_Outline_Risk_Controlled_Pruning.md](Project_Outline_Risk_Controlled_Pruning.md) for the research plan. The earlier predictive hold-cost study (negative Gate 1 result) is archived on `main`.

## Environment

OpenROAD-flow-scripts (ORFS) on ASAP7, run through `finish` (post-route, OpenRCX-extracted SPEF) with three PVT corners loaded.

| Piece | Version / location |
| --- | --- |
| ORFS scripts | `third_party/OpenROAD-flow-scripts` @ `7421007` (clone, no submodules) |
| OpenROAD / OpenSTA | `26Q1-1207-g6fa7950acd` / 3.0, prebuilt arm64 in `$ORFS_TOOLS` |
| Yosys | 0.62 with `slang` plugin, prebuilt in `$ORFS_TOOLS` |
| Python | `.venv` (3.14), see `requirements.txt` |

| Corner | Liberty | VDD | Temp |
| --- | --- | --- | --- |
| `slow` | SS | 0.63 V | 100 C |
| `typical` | TT | 0.70 V | 25 C |
| `fast` | FF | 0.77 V | 0 C |

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
scripts/run_flow.sh <design> [period_ps]      # designs: dynamic_node, jpeg, ibex, aes, riscv32i, ethmac
```

- Stock ORFS timing repair runs in every stage. Tight clocks leave residual violations.
- Outputs land in `work/results/asap7/<design>/<variant>/`: `6_final.{odb,v,sdc,spef}`.
- The flow stops after the final report (which runs OpenRCX and writes the SPEF). GDS merge is skipped, so KLayout isn't needed. [flow/load_hook.tcl](flow/load_hook.tcl) stubs `gui::show`, which the prebuilt OpenROAD lacks in batch mode.
- With `period_ps`, the design's SDC is copied with `clk_period` rewritten, and results go to the `p<period_ps>` variant. Without it, the variant is `base`.
- `UTIL=<pct> scripts/run_flow.sh <design> <period_ps>` overrides `CORE_UTILIZATION` (variant `p<period_ps>_u<pct>`). Global placement has no seed, so utilization variants stand in for placement seeds.

Inspect a finished design under all corners:

```sh
make -C $FLOW_HOME DESIGN_CONFIG=$PROJECT_ROOT/flow/designs/asap7/<design>/config.mk \
  [FLOW_VARIANT=p<period>] run RUN_SCRIPT=$PROJECT_ROOT/scripts/tcl/check_mcmm.tcl
```

This writes per-corner setup and hold WNS, TNS and violator counts (in ps) to `work/reports/<design>_<variant>_mcmm.json`.

PVT x RC corner analysis and the Gate 1 check:

```sh
scripts/corner_sta.sh <design> <variant>                # 3 PVT x 4 RC scenes, e.g. ibex p2150
RC_CORNERS="nom cw rcw cb rcb" scripts/corner_sta.sh ...  # also unscaled RC
DERATE=1 scripts/corner_sta.sh <design> <variant>       # flat OCV derates
.venv/bin/python scripts/gate1_dominance.py <design>_<variant> [--guard 50] [--corners corners_derate]
```

Per-scene results go to `work/corners/<design>_<variant>/`. The `slow_nom` scene reproduces ORFS's slow-corner WNS/TNS exactly. With `DERATE=1`, the flat OCV derates in [scripts/tcl/derate.tcl](scripts/tcl/derate.tcl) (cells ±5%, nets ±3%, same at every scene) are applied and results go to `work/corners_derate/<design>_<variant>/` instead.

## Layout

| Path | Contents |
| --- | --- |
| `flow/common.mk` | MCMM corners and flat-netlist settings; included by every design config |
| `flow/designs/asap7/<design>/` | Design configs (stock ORFS config + `common.mk`; dynamic_node is a new ASAP7 port) |
| `flow/clock_targets.mk` | Calibrated clock periods per design, with measured slow-corner WNS |
| `scripts/run_flow.sh` | Flow wrapper |
| `scripts/tcl/check_mcmm.tcl` | Per-corner timing summary |
| `scripts/scale_spef.py` | Scaled RC-corner SPEFs (`cw`, `rcw`, `cb`, `rcb`) from `6_final.spef` |
| `scripts/corner_sta.sh`, `scripts/tcl/corner_sta.tcl` | Standalone OpenSTA per (PVT, RC) scene: per-endpoint setup/hold slack and runtime |
| `scripts/tcl/derate.tcl` | Flat OCV derates for `DERATE=1` corner STA |
| `scripts/gate1_dominance.py` | Gate 1: worst-scene distribution, physics-rule catch rate, greedy cover |
| `scripts/tcl/lib/mcmm_util.tcl` | Shared STA helpers |
| `work/` | ORFS `WORK_HOME`: logs, results, reports (ignored) |

## Notes for the experiments

- OpenSTA 3.0 calls corners "scenes". Use `sta::find_scene slow`, `sta::worst_slack_scene <scene> max|min`, `sta::total_negative_slack_scene_cmd`, and `report_checks -scenes <name>`. Values from the `sta::` functions are in seconds.
- `sta::endpoint_violation_count` ignores the active scene. Count violators per corner with `report_checks -scenes`.
- ORFS extracts one SPEF (`6_final.spef`) at a single process corner. RC corners are to be built by scaling R and C from it.

Deviations from stock ORFS configs, to disclose:

- `OPENROAD_HIERARCHICAL=0` with `SWAP_ARITH_OPERATORS` cleared (ibex, dynamic_node and riscv32i enable both upstream).
- dynamic_node uses the standard ASAP7 SDC template instead of the nangate45 per-port I/O delays.
- riscv32i's dmem SRAM (`fakeram7_256x32`) has a TT-only Liberty model, read unchanged at every PVT corner. Its 168 input pins never violate, and no endpoint's worst path launches from it (checked at 1950 ps).
- ethmac's tx/rx clocks are 0.8 × `clk_period` instead of a fixed 300 ps, so a clock sweep moves all three domains.
