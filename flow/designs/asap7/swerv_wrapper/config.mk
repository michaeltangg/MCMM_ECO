# Stock ORFS ASAP7 config + project MCMM overrides.
include $(FLOW_HOME)/designs/asap7/swerv_wrapper/config.mk
include $(PROJECT_ROOT)/flow/common.mk

# Stock uses CCS, which ASAP7 ships only at FF; the three-corner lists are NLDM.
export LIB_MODEL = NLDM
