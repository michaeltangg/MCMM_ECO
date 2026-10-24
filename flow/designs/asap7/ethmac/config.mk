# Stock ORFS ASAP7 config + project MCMM overrides.
include $(FLOW_HOME)/designs/asap7/ethmac/config.mk
include $(PROJECT_ROOT)/flow/common.mk

# tx/rx clocks scale with clk_period (see constraint.sdc).
export SDC_FILE = $(PROJECT_ROOT)/flow/designs/$(PLATFORM)/ethmac/constraint.sdc
