# Sourced by ORFS load_design in every stage via LAYER_PARASITICS_FILE,
# after liberty, design and SDC are loaded (floorplan.tcl has no other hook
# before its repair_timing, and it ignores DONT_USE_CELLS).

source $::env(PLATFORM_DIR)/setRC.tcl

# Reserve SLVT for post-CTS repair: pre-CTS optimization may only use RVT/LVT.
if { [env_var_equals RESERVE_SLVT 1] } {
  set_dont_use [get_lib_cells */*_ASAP7_75t_SL]
}
