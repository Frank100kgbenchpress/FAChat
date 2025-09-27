# src/messaging.py
"""
Mensajería sobre LinkChat (usa protocol + ethernet).
Exporta:
- send_message(dest_mac, text)
- receive_message_blocking() -> (src_mac, text)
- start_message_loop(user_callback) -> background callback(src_mac, text)
- stop_message_loop()
"""
from protocol import build_header, parse_header, MSG
from ethernet import send_frame, recv_one, start_recv_loop, stop_recv_loop
from typing import Callable, Optional

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"

def send_message(dest_mac: str, text: str, seq: int = 0) -> None:
    if not dest_mac:
        dest_mac = BROADCAST_MAC
    payload = text.encode("utf-8")
    pkt = build_header(MSG, payload, seq=seq)
    send_frame(dest_mac, pkt)

def receive_message_blocking() -> tuple[str, str]:
    """
    Bloqueante: espera y devuelve (src_mac, text) si llega un MSG.
    """
    while True:
        src_mac, raw = recv_one()
        try:
            info = parse_header(raw)
        except Exception:
            continue
        if info["type"] == MSG:
            text = info["payload"].decode("utf-8", errors="replace")
            return src_mac, text

# Background loop
_message_loop_callback: Optional[Callable[[str, str], None]] = None

def _internal_cb(src_mac: str, raw_payload: bytes):
    global _message_loop_callback
    if _message_loop_callback is None:
        return
    try:
        info = parse_header(raw_payload)
    except Exception:
        return
    if info["type"] != MSG:
        return
    text = info["payload"].decode("utf-8", errors="replace")
    try:
        _message_loop_callback(src_mac, text)
    except Exception as e:
        print(f"[messaging] error en callback del usuario: {e}")

def start_message_loop(user_callback: Callable[[str, str], None]) -> None:
    global _message_loop_callback
    _message_loop_callback = user_callback
    start_recv_loop(_internal_cb)

def stop_message_loop() -> None:
    stop_recv_loop()
