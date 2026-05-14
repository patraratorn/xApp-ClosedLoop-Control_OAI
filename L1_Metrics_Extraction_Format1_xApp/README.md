# L1 Metrics Extraction xApp (Format 1)

This folder contains the complete configuration and source code for extracting Layer 1 (L1) metrics from an OpenAirInterface (OAI) gNB using the E2SM-KPM Service Model, bypassing NSSAI slice filtering by utilizing **Format 1 Action Definition**.

This specific implementation was created to solve the issue of the gNB not passing NSSAI filter criteria when the UE Registration is rejected by the AMF.

## Directory Structure

*   **`c_xapp/xapp_kpm_moni.c`**: The C-based xApp (running on FlexRIC). It subscribes to 4 key metrics using KPM Format 1 (Unconditional reporting):
    *   `DRB.UE.RSRP` (Signal Strength)
    *   `DRB.UE.SNR` (Signal Quality/Clarity)
    *   `DRB.UE.TA` (Timing Advance / Distance Estimation)
    *   `DRB.UE.BeamIdx` (Spatial Information)
*   **`python_controller/ro_controller.py`**: The Python AI Controller. It receives data from the C-xApp via ZMQ, handles the 32-bit unsigned to signed integer conversion (fixing the 4-billion RSRP bug), and formats the data for Closed-Loop AI control of the RIS.
*   **`configs/gnb.conf`**: The OAI gNB configuration file. Placed here as a reference for enabling multi-beam (`ssb_PositionsInBurst_Bitmap`) and correct AMF/PLMN settings (MCC=001, MNC=01, TAC=1).
*   **`configs/nr-ue.conf`**: The OAI nrUE configuration file. Uses the modern `pdu_sessions` format with DNN `internet` and Slice `1.ffffff`.

## Key Features
- **NSSAI Bypass**: Uses Format 1 to ensure data flows even if the UE is not fully registered or authenticated by the core network.
- **Signed Integer Handling**: The Python script correctly parses negative values for RSRP.
- **Ready for RIS AI**: Provides Distance (TA), Clarity (SNR), and Strength (RSRP) as the foundation for Reinforcement Learning algorithms to control the RIS Phase Shift.