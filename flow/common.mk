# Shared MCMM + multi-Vt settings, included at the end of every design config.
# Design configs are parsed before platforms/asap7/config.mk, so these win
# over the platform's `?=` defaults.

# Three analysis corners read by scripts/read_liberty.tcl:
#   define_corners $CORNERS; read_liberty -corner <c> $<UPPER(c)>_LIB_FILES
# Recursive '=' so the platform lists (set later, incl. OTHER_VT) are used.
export CORNERS           = slow typical fast
export SLOW_LIB_FILES    = $(WC_NLDM_LIB_FILES)
export TYPICAL_LIB_FILES = $(TC_NLDM_LIB_FILES)
export FAST_LIB_FILES    = $(BC_NLDM_LIB_FILES)

# Single-corner LIB_FILES (yosys/ABC) use the slow corner: setup-driven synthesis.
export CORNER = WC

# All Vt flavors from floorplan onward. scripts/run_flow.sh overrides this to
# RVT for the yosys step so ABC doesn't map everything to SLVT.
export ASAP7_USE_VT ?= RVT LVT SLVT

# SLVT stays out of every stage up to the checkpoint (applied in load_hook.tcl).
# RESERVE_LVT=1 also keeps LVT out (RVT-only before CTS).
# Pass RESERVE_SLVT=0 RESERVE_LVT=0 when loading the checkpoint for post-CTS repair.
export RESERVE_SLVT ?= 1
export RESERVE_LVT  ?= 0
export LAYER_PARASITICS_FILE = $(PROJECT_ROOT)/flow/load_hook.tcl

# 4_cts.odb is the experiment checkpoint: post-CTS, setup and hold unrepaired.
export SKIP_CTS_REPAIR_TIMING = 1

# eqy and kepler LEC are not part of this flow.
export EQUIVALENCE_CHECK = 0
export LEC_CHECK         = 0

# Flat netlist keeps instance handling in the setup fixer simple.
export OPENROAD_HIERARCHICAL = 0
# Arithmetic-operator swapping keeps adders as hierarchical modules and
# requires OPENROAD_HIERARCHICAL; ibex/dynamic_node enable it upstream.
# ORFS tests for non-empty, so it must be empty rather than 0.
export SWAP_ARITH_OPERATORS =
