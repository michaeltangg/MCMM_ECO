# Sourced by ORFS load_design in every stage via LAYER_PARASITICS_FILE,
# after liberty, design and SDC are loaded (floorplan.tcl has no other hook
# before its repair_timing, and it ignores DONT_USE_CELLS).

source $::env(PLATFORM_DIR)/setRC.tcl

# Reserve SLVT (and optionally LVT) for post-CTS repair.
if { [env_var_equals RESERVE_SLVT 1] } {
  set_dont_use [get_lib_cells */*_ASAP7_75t_SL]
}
if { [env_var_equals RESERVE_LVT 1] } {
  set_dont_use [get_lib_cells */*_ASAP7_75t_L]
}
