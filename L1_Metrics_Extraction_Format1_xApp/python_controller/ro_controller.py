import zmq
import json
import time
from datetime import datetime

# ==========================================
# 1. SETUP ZMQ SOCKETS
# ==========================================
context = zmq.Context()

# Subscriber Socket (Receives KPM Data from C xApp)
print("Connecting to RO xApp Publisher (Port 5555)...")
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://127.0.0.1:5555")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Publisher Socket (Sends Control Commands to C xApp)
print("Starting Control Publisher (Port 5556)...")
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")

print("RO Controller is RUNNING. Waiting for KPM messages...")

# ==========================================
# 2. THRESHOLD & LOGIC STATE
# ==========================================
PRB_THRESHOLD = 1       # Trigger if PRB usage exceeds 1% (For Simulation Test)
THP_MIN_THRESHOLD = 1.0  # Trigger if DL Throughput drops below 1.0 kbps

# Keep track of latest metrics
latest_data = {
    "DL_Throughput": 0.0,
    "PRB_DL": 0,
    "RSRP": 0.0,
    "SINR": 0.0
}

try:
    while True:
        # Receive Data
        message = sub_socket.recv_string()
        
        try:
            data = json.loads(message)
            meas_name = data.get("meas_name", "")
            raw_value = float(data.get("value", 0))
            
            # Convert 32-bit unsigned representation back to signed (for RSRP/SINR)
            if raw_value > 2147483647:
                value = raw_value - 4294967296
            else:
                value = raw_value
            
            # Print everything we receive so we know it's alive
            print(f"[DEBUG] Received -> {meas_name}: {value}")
            
            # Update State
            if "DRB.UEThpDl" in meas_name:
                latest_data["DL_Throughput"] = value
            elif "RRU.PrbTotDl" in meas_name:
                latest_data["PRB_DL"] = value
            elif "DRB.UE.RSRP" in meas_name:
                latest_data["RSRP"] = value
            elif "DRB.UE.SINR" in meas_name:
                latest_data["SINR"] = value
                
            # ==========================================
            # 3. CLOSED-LOOP CONTROL LOGIC
            # ==========================================
            # Check PRB Usage
            if latest_data["PRB_DL"] > PRB_THRESHOLD:
                print(f"[!] ALERT: High PRB Usage detected ({latest_data['PRB_DL']}%)!")
                
                # Create Control Command
                command = {
                    "action": "reduce_power",
                    "target_ue": 1,
                    "reason": "high_prb"
                }
                
                # Send Command via ZMQ (Port 5556)
                pub_socket.send_string(json.dumps(command))
                print(f"[>] Sent Control Command: {command}")
                
                # Brief sleep to prevent spamming commands
                time.sleep(2)

        except json.JSONDecodeError:
            print(f"[RAW DATA] {message}")
        except Exception as e:
            print(f"[ERROR] {e}")

except KeyboardInterrupt:
    print("\nDisconnecting...")
finally:
    sub_socket.close()
    pub_socket.close()
    context.term()
