# Clock targets (ps) for the post-route corner-pruning dataset, with stock
# ORFS timing repair. Run each with:
#   scripts/run_flow.sh <design> <period>             (variant p<period>)
#   UTIL=<pct> scripts/run_flow.sh <design> <period>  (variant p<period>_u<pct>)
#
# Slow-corner setup WNS at nominal RC, as % of period (stock utilization):
#   aes           500 -54.4  600 -31.5  700 -11.5  800 -1.2  850 +1.8  900 +2.6
#   dynamic_node  930 -34.3 1000 -26.4 1100 -17.4 1150 -12.8 1200 -8.0
#                1250  -6.1 1350  +1.8
#   ibex         1700 -25.8 1900 -11.6 2100  -2.7 2125  -1.1 2150 -0.5 2200 +0.5
#   jpeg         1100  -6.5 1125  -2.3 1135  -1.5 1150  -0.5 1200 +2.3 1300 +2.6
#
# Near closure (-3% .. 0%) is where the slow RC corners separate. dynamic_node
# never enters that band: its violations collapse to a few deep paths.
# Utilization variants (stock aes/dynamic_node/ibex 40, jpeg 70):
#   dynamic_node 1150, 1200 at 35, 45; ibex 2100, 2150 at 35, 45;
#   jpeg 1125, 1150 at 60, 65.

CLOCK_TARGETS_aes          = 500 600 700 800 850 900
CLOCK_TARGETS_dynamic_node = 930 1000 1100 1150 1200 1250 1350
CLOCK_TARGETS_ibex         = 1700 1900 2100 2125 2150 2200
CLOCK_TARGETS_jpeg         = 1100 1125 1135 1150 1200 1300
