# OpenRCX extraction of a post-route design at one or more RC corners, one
# rules file per corner. Run in openroad by scripts/corner_sta.sh (RCX_CORNERS=1):
#
#   RCX_ODB    6_final.odb
#   RCX_RULES  list of <rc> <rules file> pairs
#   RCX_OUT    output prefix: writes <prefix>_<rc>.spef
#
# Same extraction settings as ORFS's final_report.tcl, so the stock rules file
# reproduces 6_final.spef.

read_db $::env(RCX_ODB)
define_process_corner -ext_model_index 0 X

foreach {rc rules} $::env(RCX_RULES) {
  set t0 [clock milliseconds]
  extract_parasitics -ext_model_file $rules
  write_spef $::env(RCX_OUT)_$rc.spef
  puts [format "rcx %s %.1f s" $rc [expr { ([clock milliseconds] - $t0) / 1000.0 }]]
}
