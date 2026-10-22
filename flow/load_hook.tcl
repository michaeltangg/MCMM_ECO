# Sourced by ORFS load_design in every stage via LAYER_PARASITICS_FILE,
# in place of the platform default.

source $::env(PLATFORM_DIR)/setRC.tcl

# The prebuilt OpenROAD reports the GUI as compiled but has no gui::show in
# batch mode, so final_report.tcl's image save fails after writing the SPEF.
# Images aren't needed.
if { [info commands gui::show] == "" } {
  namespace eval gui {}
  proc gui::show { args } {}
}
