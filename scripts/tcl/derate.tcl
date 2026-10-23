# Flat OCV timing derates for signoff-style STA, sourced by corner_sta.tcl
# when corner_sta.sh runs with DERATE=1. The same values apply at every scene;
# they are textbook defaults, not foundry data and not tuned to a target slack.
#
# Early paths speed up and late paths slow down, on clock and data alike.
# CRPR (on by default in OpenSTA) removes the pessimism on the common clock
# path, so self-loop hold checks only see the derate on their data path.

set_timing_derate -early -cell_delay 0.95
set_timing_derate -late -cell_delay 1.05
set_timing_derate -early -net_delay 0.97
set_timing_derate -late -net_delay 1.03
