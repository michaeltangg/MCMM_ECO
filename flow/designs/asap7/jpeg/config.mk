# Stock ORFS ASAP7 config + project MCMM/multi-Vt overrides.
include $(FLOW_HOME)/designs/asap7/jpeg/config.mk
include $(PROJECT_ROOT)/flow/common.mk

# Stock jpeg maps for area (ABC_AREA=1), which leaves slow logic for the
# floorplan repair to Vt-swap. Speed mapping, like dynamic_node and ibex.
export ABC_AREA = 0
