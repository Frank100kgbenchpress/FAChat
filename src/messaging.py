# src/messaging.py
from ethernet import send_frame, recv_one
from protocol import build_header, parse_header, MSG

def send_message(dest_mac: str, text: str):
    payload = text.encode('utf-8')
    pkt = build_header(MSG, payload, seq=0)
    send_frame(dest_mac, pkt)

def receive_message_blocking():
    src_mac, raw = recv_one()  # recv_one ya filtra por EtherType y devuelve payload bytes
    info = parse_header(raw)
    if info['type'] == MSG:
        text = info['payload'].decode('utf-8', errors='ignore')
        return src_mac, text
    return src_mac, None
