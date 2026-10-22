# Calibrated clock targets (ps) for the post-CTS experiment checkpoints.
# Run each with: scripts/run_flow.sh <design> <period>   (variant p<period>)
#
# Calibrated with SLVT reserved pre-CTS, RVT-only synthesis, jpeg ABC_AREA=0.
# The ORFS default periods (dynamic_node n/a, ibex 1000, jpeg 680) were tuned
# for the FF corner and are far from closure at SS, so targets are relative to
# what closes at SS, not tighter than the ORFS defaults.
#
# Measured at 4_cts.odb (slow-corner setup; hold WNS slow/typical/fast):
#   design        period  setup WNS (%)    setup viol  hold WNS s/t/f        hold viol
#   dynamic_node   930    -193.6 (-20.8%)  327         -12.9 / +29.9 / +44.0  1
#   dynamic_node  1000    -181.6 (-18.2%)  279          +1.3 / +44.2 / +44.6  0
#   dynamic_node  1100    -139.0 (-12.6%)  233         +20.6 / +63.9 / +46.2  0
#   ibex          1700    -443.4 (-26.1%)  1171        +76.3 / +51.5 / +35.0  0
#   ibex          1900    -317.5 (-16.7%)  755         +78.6 / +52.8 / +35.9  0
#   ibex          2100    -249.5 (-11.9%)  594         +74.2 / +49.6 / +31.9  0
#   jpeg          1100    -116.8 (-10.6%)  415         -31.6 / +17.4 / +22.3  5
#   jpeg          1200    -167.3 (-13.9%)  396         -37.8 / +11.4 / +14.1  7
#   jpeg          1300     -62.7  (-4.8%)  67          +14.1 / +46.3 / +30.7  0

CLOCK_TARGETS_dynamic_node = 930 1000 1100
CLOCK_TARGETS_ibex         = 1700 1900 2100
CLOCK_TARGETS_jpeg         = 1100 1200 1300
