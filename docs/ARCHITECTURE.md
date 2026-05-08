# O-RAN Closed-Loop Control Architecture

This project demonstrates a real-time closed-loop control system using O-RAN standard interfaces.

## Components:
1. **OAI gNB (Simulation Mode)**: The base station supporting E2 Agent with E2SM-KPM and E2SM-RC Service Models.
2. **Near-RT RIC (FlexRIC)**: The controller that manages E2 nodes and hosts xApps.
3. **C xApp (ZMQ Bridge)**: Acts as the "Actuator". It translates ZMQ commands into E2SM-RC Control Requests.
4. **Python Controller (Decision Logic)**: Acts as the "Brain". It processes metrics and sends control actions via ZMQ.

## Data Flow:
[gNB] --(E2SM-KPM)--> [FlexRIC] --(Indication)--> [C xApp] --(ZMQ:5555)--> [Python Brain]
                                                                        |
[gNB] <--(E2SM-RC)--- [FlexRIC] <---(Control)---- [C xApp] <---(ZMQ:5556)-- [Python Brain]
