# send_test.py
import socket, struct
INTERFACE = "wlp2s0"   # AJUSTA
DEST_MAC = b"\xff\xff\xff\xff\xff\xff"
# usa la MAC real de la interfaz obténla con cat /sys/.../address si quieres
SRC_MAC = bytes.fromhex("12:34:56:78:9a:bc".replace(":", ""))
ETH_TYPE = struct.pack("!H", 0x1234)
payload = b"PRUEBA_UNICA_LINKCHAT"
frame = DEST_MAC + SRC_MAC + ETH_TYPE + payload

s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
s.bind((INTERFACE, 0))
s.send(frame)
print("[send_test] trama enviada")
