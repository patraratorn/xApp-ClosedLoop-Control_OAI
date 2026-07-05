#!/bin/bash
# Telemetry Recorder Launcher Script
# Developed for Mr. Beam's O-RAN 5G SA RIS Control Project

echo "=== Starting O-RAN L1 Telemetry Recorder ==="

# Define paths
RECORDER="/home/beam/openairinterface5g/cmake_targets/ran_build/build/common/utils/T/tracer/record"
T_MESSAGES="/home/beam/openairinterface5g/common/utils/T/T_messages.txt"
OUTPUT_FILE="/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw"

# Clean up old log file
rm -f "$OUTPUT_FILE"

# Execute
exec "$RECORDER" \
  -d "$T_MESSAGES" \
  -o "$OUTPUT_FILE" \
  -on GNB_PHY_SRS_ESTIMATES_RIS \
  -on GNB_PHY_L1_METRICS_RIS
