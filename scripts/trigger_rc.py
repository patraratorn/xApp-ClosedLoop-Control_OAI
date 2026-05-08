import zmq
import json
import time

context = zmq.Context()
pub_socket = context.socket(zmq.PUB)
pub_socket.connect("tcp://127.0.0.1:5556") # Connect instead of bind!

print("Connecting to ZMQ SUB on tcp://127.0.0.1:5556...")
time.sleep(2)

command = {"action": "reduce_power", "target_ue": 1, "reason": "manual_trigger"}
print(f"Sending trigger: {command}")
pub_socket.send_string(json.dumps(command))
print("Trigger sent!")
time.sleep(1)
pub_socket.close()
context.term()
