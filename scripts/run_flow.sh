#!/usr/bin/env bash
# Run ORFS on ASAP7 through finish (post-route, extracted SPEF) with MCMM corners.
#
#   scripts/run_flow.sh <design> [period_ps] [extra make args...]
#
# Without period_ps the design's own SDC is used (FLOW_VARIANT=base).
# With period_ps a copy of that SDC with `set clk_period` rewritten is used
# (FLOW_VARIANT=p<period_ps>), so each clock target gets its own results tree.
# UTIL=<pct> (with period_ps) overrides CORE_UTILIZATION and appends _u<pct> to
# the variant: global placement has no seed, so utilization variants stand in
# for placement seeds.
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
  sed -E "s/^(set[[:space:]]+clk_period[[:space:]]+)[0-9.]+/\1$period/" "$base_sdc" > "$sdc.tmp"
  if ! grep -qE "^set[[:space:]]+clk_period[[:space:]]+$period\b" "$sdc.tmp"; then
    echo "failed to set clk_period in $sdc.tmp (from $base_sdc)" >&2
    exit 1
  fi
  # Replace only on change: the SDC is a make prerequisite of synthesis, so a
  # fresh mtime would rerun the whole flow.
  if cmp -s "$sdc.tmp" "$sdc"; then
    rm "$sdc.tmp"
  else
    mv "$sdc.tmp" "$sdc"
  fi
  variant="p$period"
  if [[ -n ${UTIL:-} ]]; then
    variant+="_u$UTIL"
    make_args+=(CORE_UTILIZATION="$UTIL")
  fi
  make_args+=(FLOW_VARIANT="$variant" SDC_FILE="$sdc" ABC_CLOCK_PERIOD_IN_PS="$period")
elif [[ -n ${UTIL:-} ]]; then
  echo "UTIL needs period_ps" >&2
  exit 1
fi
make_args+=("$@")

results=$(orfs_make -s print-RESULTS_DIR | sed 's/^RESULTS_DIR: //')
logs=$(orfs_make -s print-LOG_DIR | sed 's/^LOG_DIR: //')

echo "[run_flow] $design ${period:+@ ${period}ps }-> $results"
# The final report writes 6_final.{odb,v,spef}; GDS (KLayout) isn't needed.
orfs_make "$logs/6_report.log" "$results/6_final.sdc"
echo "[run_flow] done: $results/6_final.odb, $results/6_final.spef"
