#!/usr/bin/env bash
# Run ORFS on ASAP7 through finish (post-route, extracted SPEF) with MCMM corners.
#
#   scripts/run_flow.sh <design> [period_ps] [extra make args...]
#
# Without period_ps the design's own SDC is used (FLOW_VARIANT=base).
# With period_ps a copy of that SDC with `set clk_period` rewritten is used
# (FLOW_VARIANT=p<period_ps>), so each clock target gets its own results tree.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <design> [period_ps] [extra make args...]" >&2
  exit 1
fi

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/env.sh"
fi

design=$1
shift
period=""
if [[ $# -gt 0 && $1 =~ ^[0-9]+$ ]]; then
  period=$1
  shift
fi

config="$PROJECT_ROOT/flow/designs/asap7/$design/config.mk"
if [[ ! -f $config ]]; then
  echo "no config for '$design': $config" >&2
  exit 1
fi

orfs_make() {
  make -C "$FLOW_HOME" DESIGN_CONFIG="$config" "${make_args[@]}" "$@"
}

make_args=()
if [[ -n $period ]]; then
  base_sdc=$(make -s -C "$FLOW_HOME" DESIGN_CONFIG="$config" print-SDC_FILE | sed 's/^SDC_FILE: //')
  sdc="$WORK_HOME/sdc/${design}_${period}.sdc"
  mkdir -p "$(dirname "$sdc")"
  sed -E "s/^(set[[:space:]]+clk_period[[:space:]]+)[0-9.]+/\1$period/" "$base_sdc" > "$sdc"
  if ! grep -qE "^set[[:space:]]+clk_period[[:space:]]+$period\b" "$sdc"; then
    echo "failed to set clk_period in $sdc (from $base_sdc)" >&2
    exit 1
  fi
  make_args+=(FLOW_VARIANT="p$period" SDC_FILE="$sdc" ABC_CLOCK_PERIOD_IN_PS="$period")
fi
make_args+=("$@")

results=$(orfs_make -s print-RESULTS_DIR | sed 's/^RESULTS_DIR: //')

echo "[run_flow] $design ${period:+@ ${period}ps }-> $results"
orfs_make finish
echo "[run_flow] done: $results/6_final.odb, $results/6_final.spef"
