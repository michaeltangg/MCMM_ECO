#!/usr/bin/env bash
# Build OpenRCX RC-corner SPEFs for a post-route design.
#
#   scripts/rcx_spef.sh <design> <variant>
#
# Writes 6_final_rcx_<rc>.spef next to 6_final.spef for every RC corner in
# RC_CORNERS (default "cw rcw cb rcb"; "nom" is skipped), extracted from
# 6_final.odb with the per-corner rules in $WORK_HOME/rcx/ (written by
# scripts/rcx_corner_rules.py if missing or stale). Only corners whose SPEF is
# missing or older than the odb or its rules file are extracted, all in one
# openroad session; the log goes to rcx_extract.log next to the SPEFs.
# Called by corner_sta.sh with RCX_CORNERS=1.
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
rc_corners=${RC_CORNERS:-cw rcw cb rcb}
results="$WORK_HOME/results/asap7/$design/$variant"
odb="$results/6_final.odb"
rules_dir="$WORK_HOME/rcx"
rules_script="$PROJECT_ROOT/scripts/rcx_corner_rules.py"
if [[ ! -f $odb ]]; then
  echo "missing $odb (run scripts/run_flow.sh)" >&2
  exit 1
fi

for rc in $rc_corners; do
  if [[ $rc != nom && ! $rules_dir/$rc.rules -nt $rules_script ]]; then
    python -I "$rules_script" "$rules_dir" > /dev/null
    break
  fi
done

todo=()
for rc in $rc_corners; do
  [[ $rc == nom ]] && continue
  out="$results/6_final_rcx_$rc.spef"
  if [[ ! $out -nt $odb || ! $out -nt $rules_dir/$rc.rules ]]; then
    todo+=("$rc" "$rules_dir/$rc.rules")
  fi
done
(( ${#todo[@]} )) || exit 0

if RCX_ODB="$odb" RCX_RULES="${todo[*]}" RCX_OUT="$results/6_final_rcx" \
   "$OPENROAD_EXE" -no_init -exit "$PROJECT_ROOT/scripts/tcl/rcx_extract.tcl" \
   > "$results/rcx_extract.log" 2>&1; then
  echo "$design $variant rcx $(grep '^rcx ' "$results/rcx_extract.log" | tr '\n' ' ')"
else
  echo "$design $variant rcx FAILED (see $results/rcx_extract.log)"
  exit 1
fi
