# Stock ORFS ASAP7 config + project MCMM overrides.
include $(FLOW_HOME)/designs/asap7/riscv32i/config.mk
include $(PROJECT_ROOT)/flow/common.mk

# The dmem SRAM macro's liberty (fakeram7_256x32) is in ADDITIONAL_LIBS, which
# the per-corner lists leave out. It is characterized at TT only, so the same
# model is read at every PVT corner.
export SLOW_LIB_FILES    += $(ADDITIONAL_LIBS)
export TYPICAL_LIB_FILES += $(ADDITIONAL_LIBS)
export FAST_LIB_FILES    += $(ADDITIONAL_LIBS)
