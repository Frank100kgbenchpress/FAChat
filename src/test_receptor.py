# test_recv_protocol.py
from messaging import receive_message_blocking
src, msg = receive_message_blocking()
print("Recibido de", src, ":", msg)
