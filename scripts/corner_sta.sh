#!/usr/bin/env bash
# Run single-scene STA at every PVT x RC corner of a post-route design.
#
#   scripts/corner_sta.sh <design> <variant>      # e.g. ibex p2150, ibex p2150_u35
#
# Builds the scaled RC SPEFs (scripts/scale_spef.py) next to 6_final.spef if
# they are missing or stale, then runs scripts/tcl/corner_sta.tcl in
# standalone OpenSTA once per (PVT, RC) scene. Results land in
# work/corners/<design>_<variant>/<pvt>_<rc>{_endpoints.csv,.json,.log}.
#
# DERATE=1 applies the flat OCV derates in scripts/tcl/derate.tcl and writes to
# work/corners_derate/ instead, so derated and underated results sit side by
# side. DERATE=pvt scales the cell derate by PVT corner instead (same file)
# and writes to work/corners_derate_pvt/.
# RCX_CORNERS=1 uses OpenRCX SPEFs extracted per RC corner with per-layer rules
# (scripts/rcx_spef.sh) instead of the scaled ones, and adds _rcx to the
# results directory (e.g. work/corners_derate_pvt_rcx/).
# RC_CORNERS (default "cw rcw cb rcb") picks the RC corners; "nom" is the
# unscaled 6_final.spef. JOBS (default 4) sets how many scenes run at once;
# each is single-threaded, so keep JOBS below the free core count for honest
# per-scene runtimes.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <design> <variant>" >&2
  exit 1
fi

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/env.sh"
fi

design=$1
variant=$2
pvt_corners="slow typical fast"
rc_corners=${RC_CORNERS:-cw rcw cb rcb}
jobs=${JOBS:-4}

config="$PROJECT_ROOT/flow/designs/asap7/$design/config.mk"
results="$WORK_HOME/results/asap7/$design/$variant"
spef="$results/6_final.spef"
if [[ ! -f $spef ]]; then
  echo "missing $spef (run scripts/run_flow.sh)" >&2
  exit 1
fi

spef_tag=
if [[ ${RCX_CORNERS:-0} == 1 ]]; then
  spef_tag=rcx_
  "$PROJECT_ROOT/scripts/rcx_spef.sh" "$design" "$variant"
else
  for rc in $rc_corners; do
    if [[ $rc != nom && ! $results/6_final_$rc.spef -nt $spef ]]; then
      python -I "$PROJECT_ROOT/scripts/scale_spef.py" "$spef"
      break
    fi
  done
fi

# One make call for every variable we need: "<VAR>: <value>" per line.
vars=$(make -s -C "$FLOW_HOME" DESIGN_CONFIG="$config" FLOW_VARIANT="$variant" \
  print-DESIGN_NAME print-SLOW_LIB_FILES print-TYPICAL_LIB_FILES print-FAST_LIB_FILES)
var() {
  sed -n "s/^$1: //p" <<< "$vars"
}

corners_dir=corners
derate=
case ${DERATE:-0} in
  0) ;;
  1) corners_dir=corners_derate ;;
  pvt) corners_dir=corners_derate_pvt ;;
  *) echo "DERATE must be 0, 1 or pvt" >&2; exit 1 ;;
esac
[[ ${DERATE:-0} != 0 ]] && derate="$PROJECT_ROOT/scripts/tcl/derate.tcl"
[[ -n $spef_tag ]] && corners_dir+=_rcx
out_dir="$WORK_HOME/$corners_dir/${design}_$variant"
mkdir -p "$out_dir"

run_scene() {
  local pvt=$1 rc=$2
  local scene_spef="$results/6_final_$spef_tag$rc.spef"
  [[ $rc == nom ]] && scene_spef=$spef
  local upper
  upper=$(tr a-z A-Z <<< "$pvt")
  local prefix="$out_dir/${pvt}_$rc"
  local derate_pvt=
  [[ ${DERATE:-0} == pvt ]] && derate_pvt=$pvt
  if CORNER_DERATE_PVT="$derate_pvt" CORNER_LIBS="$(var "${upper}_LIB_FILES")" CORNER_NETLIST="$results/6_final.v" \
     CORNER_SDC="$results/6_final.sdc" CORNER_SPEF="$scene_spef" \
     CORNER_TOP="$(var DESIGN_NAME)" CORNER_OUT="$prefix" CORNER_DERATE="$derate" \
     "$OPENSTA_EXE" -no_init -exit "$PROJECT_ROOT/scripts/tcl/corner_sta.tcl" \
     > "$prefix.log" 2>&1; then
    echo "$design $variant ${pvt}_$rc ok"
  else
    echo "$design $variant ${pvt}_$rc FAILED (see $prefix.log)"
    return 1
  fi
}

failed=0
running=0
for pvt in $pvt_corners; do
  for rc in $rc_corners; do
    run_scene "$pvt" "$rc" &
    running=$((running + 1))
    if (( running >= jobs )); then
      wait -n || failed=1
      running=$((running - 1))
    fi
  done
done
while (( running > 0 )); do
  wait -n || failed=1
  running=$((running - 1))
done
exit $failed
