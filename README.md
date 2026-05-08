# O-RAN E2SM-RC Closed-Loop Control (PoC)

Successfully implemented an end-to-end closed-loop control system using OAI gNB, FlexRIC, and a custom ZMQ-based AI controller.

## Key Achievements
- **Stable E2SM-RC Implementation**: Resolved gNB Segmentation Faults by providing fully populated RAN parameters for QoS Flow Mapping.
- **Bi-directional Control Loop**: Proven data path from Python (Decision) to gNB (Execution) with CONTROL ACKNOWLEDGE.
- **Simulation Ready**: Optimized for rfsimulator environment.

## Quick Start
1. **Setup Environment**: sudo ./scripts/setup_bridge.sh
2. **Run RIC**: ./nearRT-RIC
3. **Run gNB**: sudo ./nr-softmodem -O ./configs/gnb.rfsim.conf --rfsim --rfsimulator.serveraddr server
4. **Run xApp**: Compile and run src/xapp/xapp_kpm_moni.c
5. **Trigger Control**: python3 src/controller/ro_controller.py

## Evidence of Success
\`\`\`
[gNB Side]
QoS flow mapping configuration
DRB ID 5 
List of QoS Flows to be modified in DRB
qfi = 10, dir 1 
[E2-AGENT]: CONTROL ACKNOWLEDGE tx
\`\`\`
