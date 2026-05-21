import zmq
import json
from datetime import datetime

# Initialize ZeroMQ context
context = zmq.Context()

# Set up subscriber socket
print("Connecting to RO xApp Publisher...")
socket = context.socket(zmq.SUB)
socket.connect("tcp://127.0.0.1:5555")  # Connect to the xApp's published port

# Subscribe to all topics (empty string)
socket.setsockopt_string(zmq.SUBSCRIBE, "")

print("Waiting for KPM messages...")

# Dictionary to hold the latest values for display
latest_data = {
    "RSRP": "N/A",
    "DL_Throughput": "0.00 kbps",
    "UL_Throughput": "0.00 kbps",
    "PRB_DL": "0 %",
    "PRB_UL": "0 %"
}

try:
    while True:
        # Receive the message
        message = socket.recv_string()
        
        try:
            # Parse the JSON payload
            data = json.loads(message)
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            meas_name = data.get("meas_name", "")
            value = data.get("value", 0)
            unit = data.get("unit", "")
            
            # Update the latest data dictionary based on the measurement name
            if "DRB.UEThpDl" in meas_name:
                latest_data["DL_Throughput"] = f"{value} {unit}"
            elif "DRB.UEThpUl" in meas_name:
                latest_data["UL_Throughput"] = f"{value} {unit}"
            elif "RRU.PrbTotDl" in meas_name:
                latest_data["PRB_DL"] = f"{value} {unit}"
            elif "RRU.PrbTotUl" in meas_name:
                latest_data["PRB_UL"] = f"{value} {unit}"
            elif "RSRP" in meas_name: # In case RSRP is added later
                latest_data["RSRP"] = f"{value} {unit}"
            
            # Display formatted output for the current message
            print(f"[{timestamp}] Received: {meas_name} = {value} {unit}")
            
            # Write to zmq_telemetry.json for data collection
            try:
                with open("/home/beam/.gemini/tmp/demo/zmq_telemetry.json", "a") as jf:
                    jf.write(json.dumps({"timestamp": timestamp, "meas_name": meas_name, "value": value, "unit": unit}) + "\n")
            except Exception:
                pass
            
            # Optional: Print a summary line every time DL Throughput updates
            if "DRB.UEThpDl" in meas_name:
                print(f" ---> SUMMARY | DL Thp: {latest_data['DL_Throughput']} | UL Thp: {latest_data['UL_Throughput']} | PRB DL: {latest_data['PRB_DL']}")
            
        except json.JSONDecodeError:
            # Fallback if the message is not JSON
            print(f"Received raw data: {message}")

except KeyboardInterrupt:
    print("\nDisconnecting...")
finally:
    socket.close()
    context.term()
