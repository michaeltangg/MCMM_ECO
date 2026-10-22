#!/usr/bin/env bash
# Gate 1: hold repair with and without prior setup repair, from every
# post-CTS checkpoint in flow/clock_targets.mk.
#
#   scripts/gate1.sh [design[:period] ...]
#
# Defaults to all designs and all their clock targets. JOBS (default 6) sets
# how many OpenROAD runs go in parallel. VARIANT_PREFIX (default "p") selects
# which checkpoints (<prefix><period>) to use. Results land in work/gate1/.
set -euo pipefail

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/env.sh"
fi

targets_file="$PROJECT_ROOT/flow/clock_targets.mk"
jobs=${JOBS:-6}
prefix=${VARIANT_PREFIX:-p}

clock_targets() {
  sed -nE "s/^CLOCK_TARGETS_$1[[:space:]]*=[[:space:]]*//p" "$targets_file"
}

specs=("$@")
if [[ ${#specs[@]} -eq 0 ]]; then
  specs=($(sed -nE 's/^CLOCK_TARGETS_([A-Za-z0-9_]+).*/\1/p' "$targets_file"))
fi

runs=()
for spec in "${specs[@]}"; do
  design=${spec%%:*}
  if [[ $spec == *:* ]]; then
    periods=${spec#*:}
  else
    periods=$(clock_targets "$design")
  fi
  if [[ -z $periods ]]; then
    echo "no clock targets for '$design' in $targets_file" >&2
    exit 1
  fi
  for period in $periods; do
    for mode in hold_only setup_then_hold; do
      runs+=("$design $period $mode")
    done
  done
done

mkdir -p "$WORK_HOME/gate1"

run_one() {
  local design=$1 period=$2 mode=$3
  local variant="$prefix$period"
  local odb="$WORK_HOME/results/asap7/$design/$variant/4_cts.odb"
  if [[ ! -f $odb ]]; then
    echo "$design $variant $mode: missing $odb (run scripts/run_flow.sh $design $period)"
    return 1
  fi
  local args=(
    -C "$FLOW_HOME"
    DESIGN_CONFIG="$PROJECT_ROOT/flow/designs/asap7/$design/config.mk"
    FLOW_VARIANT="$variant"
    RESERVE_SLVT=0
    RESERVE_LVT=0
    GATE1_MODE="$mode"
    RUN_LOG_NAME_STEM="gate1_$mode"
    run
    RUN_SCRIPT="$PROJECT_ROOT/scripts/tcl/gate1.tcl"
  )
  local start=$SECONDS
  if make -s "${args[@]}" > "$WORK_HOME/gate1/${design}_${variant}_${mode}.log" 2>&1; then
    echo "$design $variant $mode ok $((SECONDS - start))s"
  else
    echo "$design $variant $mode FAILED (see work/gate1/${design}_${variant}_${mode}.log)"
    return 1
  fi
}

failed=0
running=0
for r in "${runs[@]}"; do
  run_one $r &
  running=$((running + 1))
  if (( running >= jobs )); then
    wait -n || failed=1
    running=$((running - 1))
  fi
done
while (( running > 0 )); do
  wait -n || failed=1
  running=$((running - 1))
done
exit $failed
