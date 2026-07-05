#!/bin/bash
# nrUE Simulator Launcher Script
# Developed for Mr. Beam's O-RAN 5G SA RIS Control Project

echo "=== Starting O-RAN 5G SA nrUE (rfsimulator) ==="

UE_CONF="/home/beam/oai-cn5g-fed/docker-compose/ran-conf/nr-ue.conf"
UE_EXEC="/home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-uesoftmodem"

# Execute nr-uesoftmodem with sudo using the provided password
echo 'bbEEam167' | sudo -S stdbuf -oL -eL "$UE_EXEC" \
  -O "$UE_CONF" \
  --rfsim --rfsimulator.serveraddr 127.0.0.1 -C 3319680000 -r 106 --numerology 1 --band 78 --ssb 516 --thread-pool -1,-1 -E
