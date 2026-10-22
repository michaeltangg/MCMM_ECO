# Inspect a post-CTS checkpoint under all MCMM corners.
#
# Run through ORFS so the full flow environment is set:
#   make -C $FLOW_HOME DESIGN_CONFIG=... [FLOW_VARIANT=...] run \
#     RUN_SCRIPT=$PROJECT_ROOT/scripts/tcl/check_mcmm.tcl
#
# Writes $WORK_HOME/reports/<design>_<variant>_mcmm.json with per-corner
# setup/hold WNS, TNS and violator counts, a Vt census and a replace_cell
# round-trip check. Slack values are in ps.

source $::env(SCRIPTS_DIR)/load.tcl
load_design 4_cts.odb 4_cts.sdc
estimate_parasitics -placement

source [file join [file dirname [info script]] lib mcmm_util.tcl]

# Vt-swap one cell on the worst slow-corner setup path and back, checking
# that timing updates and is restored exactly.
array set alt_vt {R L L R SL L}

proc replace_cell_roundtrip { } {
  global alt_vt
  set s [sta::find_scene slow]
  # One path per path group is returned; take the worst.
  set path_end [lindex [find_timing_paths -path_delay max -scenes slow \
                          -group_path_count 1 -sort_by_slack] 0]
  set inst ""
  foreach pin [[$path_end path] pins] {
    set cand [$pin instance]
    set master [get_property $cand ref_name]
    set vt [vt_of $master]
    # Data-path cells only: skip flops and CTS buffers/loads.
    if { $vt != "other" && ![string match DFF* $master]
         && ![string match clk* [get_full_name $cand]] } {
      set target [regsub "_${vt}\$" $master "_$alt_vt($vt)"]
      if { [get_lib_cells -quiet */$target] != "" } {
        set inst $cand
        break
      }
    }
  }
  if { $inst == "" } {
    return [list ok false reason "\"no swappable combinational cell on worst path\""]
  }
  set name [get_full_name $inst]
  set before [sta::worst_slack_scene $s max]
  replace_cell $inst $target
  estimate_parasitics -placement
  set swapped [sta::worst_slack_scene $s max]
  replace_cell $inst $master
  estimate_parasitics -placement
  set restored [sta::worst_slack_scene $s max]
  set ok [expr { $swapped != $before && abs($restored - $before) < 1e-15 }]
  return [list ok [expr { $ok ? "true" : "false" }] inst "\"$name\"" \
    from "\"$master\"" to "\"$target\"" \
    slow_wns_before [ps $before] slow_wns_swapped [ps $swapped] \
    slow_wns_restored [ps $restored]]
}

set corners {}
foreach scene [sta::scenes] {
  lappend corners $scene [json_obj [scene_metrics $scene]]
}

array set vt_count {R 0 L 0 SL 0 other 0}
foreach inst [get_cells *] {
  incr vt_count([vt_of [get_property $inst ref_name]])
}

set clk [lindex [all_clocks] 0]
set summary [list \
  design "\"$::env(DESIGN_NICKNAME)\"" \
  variant "\"$::env(FLOW_VARIANT)\"" \
  clock_period_ps [get_property $clk period] \
  instances [llength [get_cells *]] \
  design_area_um2 [format %.3f [expr { [rsz::design_area] * 1e12 }]] \
  corners [json_obj $corners] \
  vt_census [json_obj [array get vt_count]] \
  replace_cell_roundtrip [json_obj [replace_cell_roundtrip]]]

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
puts "vt: [array get vt_count]"
puts "wrote $out"
