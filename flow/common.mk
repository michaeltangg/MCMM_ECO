# Shared MCMM settings, included at the end of every design config.
# Design configs are parsed before platforms/asap7/config.mk, so these win
# over the platform's `?=` defaults.

# Three PVT corners read by scripts/read_liberty.tcl:
#   define_corners $CORNERS; read_liberty -corner <c> $<UPPER(c)>_LIB_FILES
# Recursive '=' so the platform lists (set later) are used.
export CORNERS           = slow typical fast
export SLOW_LIB_FILES    = $(WC_NLDM_LIB_FILES)
export TYPICAL_LIB_FILES = $(TC_NLDM_LIB_FILES)
export FAST_LIB_FILES    = $(BC_NLDM_LIB_FILES)

# Single-corner LIB_FILES (yosys/ABC) use the slow corner: setup-driven synthesis.
export CORNER = WC

# setRC.tcl plus a gui::show stub for the final report (see load_hook.tcl).
export LAYER_PARASITICS_FILE = $(PROJECT_ROOT)/flow/load_hook.tcl

# eqy and kepler LEC are not part of this flow.
export EQUIVALENCE_CHECK = 0
export LEC_CHECK         = 0

# Flat netlist keeps endpoint names and instance handling in the ECO fixer simple.
export OPENROAD_HIERARCHICAL = 0
# Arithmetic-operator swapping keeps adders as hierarchical modules and
# requires OPENROAD_HIERARCHICAL; ibex/dynamic_node enable it upstream.
# ORFS tests for non-empty, so it must be empty rather than 0.
export SWAP_ARITH_OPERATORS =
