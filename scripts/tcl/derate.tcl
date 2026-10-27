# OCV timing derates for signoff-style STA, sourced by corner_sta.tcl when
# corner_sta.sh runs with DERATE=1 (flat) or DERATE=pvt (cell derate per PVT
# corner, from CORNER_DERATE_PVT). They are textbook defaults, not foundry
# data and not tuned to a target slack.
#
# Flat: cells +-5%, nets +-3% at every scene.
#
# Per PVT corner: the cell derate is scaled from +-5% at TT by the gate
# overdrive ratio (0.70 - Vth) / (VDD - Vth), with Vth = 0.17 V (ASAP7 RVT
# NMOS Vtsat at 25 C; every design uses RVT cells only). Under the alpha-power
# law, Vth-driven delay variation goes as 1 / (VDD - Vth), so alpha and sigma
# Vth cancel in the ratio. Nets stay +-3%: supply voltage changes gate delay,
# not wire delay, and per-layer wire variation belongs to the RC corners.
# Sources and limitations are in references.md (Derates).
#
# Early paths speed up and late paths slow down, on clock and data alike.
# CRPR (on by default in OpenSTA) removes the pessimism on the common clock
# path, so self-loop hold checks only see the derate on their data path.

set cell_derate {slow 0.058 typical 0.050 fast 0.044}
set cell 0.05
if { [info exists ::env(CORNER_DERATE_PVT)] && $::env(CORNER_DERATE_PVT) ne "" } {
  set cell [dict get $cell_derate $::env(CORNER_DERATE_PVT)]
}

set_timing_derate -early -cell_delay [expr { 1 - $cell }]
set_timing_derate -late -cell_delay [expr { 1 + $cell }]
set_timing_derate -early -net_delay 0.97
set_timing_derate -late -net_delay 1.03
