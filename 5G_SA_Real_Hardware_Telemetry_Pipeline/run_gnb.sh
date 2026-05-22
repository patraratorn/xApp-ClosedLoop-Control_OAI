#!/bin/bash
# gNB Simulator Launcher Script
# Developed for Mr. Beam's O-RAN 5G SA RIS Control Project

echo "=== Starting O-RAN 5G SA gNB (rfsimulator) ==="

GNB_CONF="/home/beam/oai-cn5g-fed/docker-compose/ran-conf/gnb.conf"
GNB_EXEC="/home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem"

# Execute nr-softmodem with sudo using the provided password
echo 'bbEEam167' | sudo -S stdbuf -oL -eL "$GNB_EXEC" \
  -O "$GNB_CONF" \
  --rfsim -E --continuous-tx --T_stdout 0 --telnetsrv
