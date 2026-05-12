import zmq
import json
import time
import struct
import random # For simulating AI decisions in this PoC

# --- CONFIGURATION ---
ZMQ_KPM_ADDR = "tcp://127.0.0.1:5555" # Receive KPM from C xApp

# 1. Setup ZMQ Receiver
context = zmq.Context()
kpm_receiver = context.socket(zmq.SUB)
kpm_receiver.connect(ZMQ_KPM_ADDR)
kpm_receiver.setsockopt_string(zmq.SUBSCRIBE, "")

print("RIS-FPGA COMMANDER (PYTHON) is RUNNING...")
print(f"Hybrid Architecture: AI calculates Beam Direction, FPGA calculates Phase Shift.")
print("Waiting for KPM Data from gNB...")

# --- AI Logic (Commander) ---
def decide_beam_direction(throughput, prb):
    """
    Simplified AI Logic:
    Determines the best beam direction based on network conditions.
    """
    if throughput < 1.0 or prb > 80:
        # Network is congested or signal is bad.
        # AI decides to steer the beam to a known secondary path (e.g., 45 degrees)
        return 45, 1 # 45 degrees, Mode 1 (Auto Recovery)
    elif throughput > 50.0:
        # Network is excellent. Steer beam to primary path (e.g., 0 degrees / LOS)
        return 0, 1 # 0 degrees, Mode 1 (Auto Optimal)
    else:
        # Normal conditions. Keep sweeping or hold current.
        # For PoC, randomly sweep between -15 and 15 degrees.
        return random.choice([-15, 0, 15]), 2 # Mode 2 (Scanning)

# --- FPGA Encoder ---
def encode_fpga_payload(control_mode, beam_direction, update_timing_ms):
    """
    Packs the Commander's decision into the Byte Stream for the FPGA.
    Format: [Header][Mode][Beam_Dir][Timing][Footer]
    """
    header = 0xAA
    footer = 0x55
    
    # Handle negative degrees for beam direction (convert to signed byte)
    # Using 'b' for signed char (-128 to 127), 'B' for unsigned, 'H' for unsigned short
    try:
        payload = struct.pack(">BbHbB", 
                              header, 
                              control_mode & 0xFF, 
                              beam_direction, # Signed 16-bit to allow negative angles if needed by FPGA
                              update_timing_ms & 0xFF, # Simplified timing to 1 byte for this example (0-255 ms)
                              footer)
        return payload
    except Exception as e:
        print(f"Encoding Error: {e}")
        return None

# --- Main Loop ---
try:
    while True:
        # 1. Receive Network State (Layer 1 KPM)
        message = kpm_receiver.recv_string()
        try:
            data = json.loads(message)
            ue_id = data.get("ue_id", 0)
            thp = data.get("DRB.UEThpDl", 0.0)
            prb = data.get("RRU.PrbTotDl", 0.0)
            
            print(f"\n[NETWORK STATE] UE: {ue_id} | Throughput: {thp} kbps | PRB: {prb}%")
            
            # 2. AI Decision (The Commander)
            beam_dir, ctrl_mode = decide_beam_direction(thp, prb)
            update_time = 100 # Tell FPGA to hold this beam for 100ms
            
            print(f">>> [AI DECISION] Steering Beam to {beam_dir}° (Mode {ctrl_mode})")
            
            # 3. Generate FPGA Payload
            fpga_bytes = encode_fpga_payload(ctrl_mode, beam_dir, update_time)
            
            if fpga_bytes:
                print(f"[OUT to FPGA] BYTE STREAM: {fpga_bytes.hex().upper()}")
                # TODO: send_to_serial(fpga_bytes) or send_to_udp(fpga_bytes)
                
        except json.JSONDecodeError:
            print("Error: Invalid JSON")

except KeyboardInterrupt:
    print("\nCommander stopping...")
finally:
    kpm_receiver.close()
    context.term()
