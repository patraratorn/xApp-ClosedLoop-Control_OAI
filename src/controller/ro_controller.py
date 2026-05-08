import zmq
import json
import time

context = zmq.Context()
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://127.0.0.1:5555")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")

print("RO Controller (PROOF EDITION) is RUNNING...")

try:
    while True:
        message = sub_socket.recv_string()
        data = json.loads(message)
        meas_name = data.get("meas_name", "")
        value = float(data.get("value", 0))
        
        print(f"[PROOF 2.1] Python Received KPM: {meas_name} = {value}")
        
        # Always trigger for proof purposes if DummyPRB is received
        if meas_name == "DummyPRB":
            print(f"[PROOF 2.2] Brain Decided: Resource usage high! Sending Control Command...")
            command = {
                "action": "reduce_power",
                "target_ue": 1,
                "reason": "proof_of_concept"
            }
            pub_socket.send_string(json.dumps(command))
            print(f"[PROOF 2.3] ZMQ Command Sent back to C xApp: {command}")
            time.sleep(5) # Slow down for visibility

except KeyboardInterrupt:
    print("Stopping...")
finally:
    sub_socket.close()
    pub_socket.close()
    context.term()
