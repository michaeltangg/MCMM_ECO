#!/usr/bin/env bash
# Re-time every run with per-corner derates (DERATE=pvt) and OpenRCX RC corners
# (RCX_CORNERS=1), then rerun Part A pruning on the new scenes. Meant to run
# unattended:
#
#   caffeinate -i scripts/retime.sh > work/logs/retime.log 2>&1 &
#
# Runs are the <design>_<variant> directories in work/corners_derate/. Stages:
# per-corner rules, extraction (EXTRACT_JOBS runs at once, default 6),
# corner_sta.sh one run at a time (JOBS scenes at once, default 6), then
# corner_prune.py cross and target with both models into
# work/prune/corners_derate_pvt_rcx/. Pruning is skipped if any run failed.
set -uo pipefail

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/env.sh"
fi
cd "$PROJECT_ROOT"
export DERATE=pvt RCX_CORNERS=1 JOBS=${JOBS:-6}
corners=corners_derate_pvt_rcx

stamp() {
  date "+%F %T"
}
split_run() {  # <design>_<variant> -> "<design> <variant>"
  local d=${1%_p*}
  echo "$d ${1#"$d"_}"
}

runs=($(ls "$WORK_HOME/corners_derate"))
failed=0

echo "$(stamp) rules"
python -I scripts/rcx_corner_rules.py "$WORK_HOME/rcx" > /dev/null || exit 1

echo "$(stamp) extraction: ${#runs[@]} runs, ${EXTRACT_JOBS:-6} at once"
for run in "${runs[@]}"; do
  split_run "$run"
done | xargs -P "${EXTRACT_JOBS:-6}" -n 2 scripts/rcx_spef.sh || failed=1

echo "$(stamp) sta"
for run in "${runs[@]}"; do
  scripts/corner_sta.sh $(split_run "$run") | grep -v " ok$"
  [[ ${PIPESTATUS[0]} == 0 ]] || { echo "$run FAILED"; failed=1; }
done

if (( failed )); then
  echo "$(stamp) failures above; skipping corner_prune"
  exit 1
fi

for args in "cross" "cross --model linear" \
            "cross --cal-split design" "cross --cal-split design --model linear" \
            "target" "target --model linear"; do
  echo "$(stamp) corner_prune $args"
  .venv/bin/python scripts/corner_prune.py $args --corners $corners || failed=1
done
echo "$(stamp) done"
exit $failed
