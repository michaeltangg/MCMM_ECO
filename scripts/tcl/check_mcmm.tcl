# Inspect a post-route design under all MCMM corners.
#
# Run through ORFS so the full flow environment is set:
#   make -C $FLOW_HOME DESIGN_CONFIG=... [FLOW_VARIANT=...] run \
#     RUN_SCRIPT=$PROJECT_ROOT/scripts/tcl/check_mcmm.tcl
#
# Writes $WORK_HOME/reports/<design>_<variant>_mcmm.json with per-corner
# setup/hold WNS, TNS and violator counts. Slack values are in ps.

source $::env(SCRIPTS_DIR)/load.tcl
load_design 6_final.odb 6_final.sdc
set_propagated_clock [all_clocks]
read_spef $::env(RESULTS_DIR)/6_final.spef

source [file join [file dirname [info script]] lib mcmm_util.tcl]

set corners {}
foreach scene [sta::scenes] {
  lappend corners $scene [json_obj [scene_metrics $scene]]
}

set clk [lindex [all_clocks] 0]
set summary [list \
  design "\"$::env(DESIGN_NICKNAME)\"" \
  variant "\"$::env(FLOW_VARIANT)\"" \
  clock_period_ps [get_property $clk period] \
  instances [llength [get_cells *]] \
  design_area_um2 [format %.3f [expr { [rsz::design_area] * 1e12 }]] \
  corners [json_obj $corners]]

set out_dir [file join $::env(WORK_HOME) reports]
file mkdir $out_dir
set out [file join $out_dir "$::env(DESIGN_NICKNAME)_$::env(FLOW_VARIANT)_mcmm.json"]
set f [open $out w]
puts $f [json_obj $summary]
close $f

puts "\n=== MCMM summary: $::env(DESIGN_NICKNAME) / $::env(FLOW_VARIANT) ==="
foreach {scene metrics} $corners {
  puts [format "%-8s %s" $scene $metrics]
}
puts "wrote $out"
