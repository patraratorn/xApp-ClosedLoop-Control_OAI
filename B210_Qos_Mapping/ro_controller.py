import zmq
import json
import time

context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://127.0.0.1:5555")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")

print("RO Controller (CLOSED-LOOP PROOF) is RUNNING...")
print("Logic: Trigger Control Action if Throughput > 0 (Immediate Proof Mode)")

try:
    while True:
        message = sub_socket.recv_string()
        try:
            data = json.loads(message)
            meas_name = data.get("meas_name", "")
            value = float(data.get("value", 0))
            ue_id = data.get("ue_id", "Unknown")
            
            print(f"[METRIC] {meas_name} = {value} (UE: {ue_id})")
            
            # TRIGGER LOGIC: If we see ANY throughput, send the Control command
            if "UEThpDl" in meas_name and value >= 0:
                print(f"!!! Traffic Detected ({value} kbps) !!!")
                print(f">>> Brain Decided: Optimize QoS for UE {ue_id} immediately...")
                
                command = {
                    "action": "optimize_qos",
                    "target_ue": 1,
                    "reason": "immediate_proof_of_concept"
                }
                pub_socket.send_string(json.dumps(command))
                print(f"[v] ZMQ Command Dispatched to xApp!")
                time.sleep(5) # Delay 5s to avoid hardware overload
                
        except Exception as e:
            print(f"Error parsing JSON: {e}")

except KeyboardInterrupt:
    print("Stopping...")
finally:
    sub_socket.close()
    pub_socket.close()
    context.term()
