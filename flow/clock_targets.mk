# Clock targets (ps) for the post-route corner-pruning dataset.
# Run each with: scripts/run_flow.sh <design> <period>   (variant p<period>)
#
# Not yet calibrated for the post-route flow with stock timing repair on.
# The periods below were calibrated at post-CTS with repair off (SS corner,
# hold-cost study) and are only starting points; aes has none yet.

CLOCK_TARGETS_ibex = 1700 1900 2100
CLOCK_TARGETS_jpeg = 1100 1200 1300
