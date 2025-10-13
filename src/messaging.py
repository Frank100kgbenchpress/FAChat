# src/messaging.py
from protocol import build_header, parse_header, MSG, CHAT_CHANNEL
from ethernet import send_frame, recv_one, start_recv_loop, stop_recv_loop
from typing import Callable, Optional
import socket
import struct
import time
import os
from ethernet import INTERFACE, ETH_P_LINKCHAT

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"
DISCOVER_REQ = "__LINKCHAT_DISCOVER_REQ__"
DISCOVER_REPLY_PREFIX = "__LINKCHAT_DISCOVER_RPLY__|"


def send_message(dest_mac: str, text: str, seq: int = 0) -> None:
    print("Mandando mensaje")
    if not dest_mac:
        dest_mac = BROADCAST_MAC
    payload = text.encode("utf-8")
    pkt = build_header(MSG, payload, channel=CHAT_CHANNEL, seq=seq)
    send_frame(dest_mac, pkt)


def receive_message_blocking() -> tuple[str, str]:
    """
    Bloqueante: espera y devuelve (src_mac, text) si llega un MSG.
    """
    print("receive_message_blocking")
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
    """
    Procesa mensajes entrantes. Siempre responde a DISCOVER_REQ (unicast reply).
    """
    global _message_loop_callback
    try:
        info = parse_header(raw_payload)
    except Exception:
        return
    if info["type"] != MSG:
        return
    text = info["payload"].decode("utf-8", errors="replace")

    # Auto-responder a petición de discovery (unicast al solicitante)
    if text == DISCOVER_REQ:
        try:
            user = os.environ.get("USER") or os.getlogin()
        except Exception:
            user = "user"
        try:
            host = socket.gethostname()
        except Exception:
            host = "host"
        name = f"{user}@{host}"
        reply = DISCOVER_REPLY_PREFIX + name
        try:
            send_message(src_mac, reply)
        except Exception:
            pass

    # Llamar al callback de mensajes normales si existe
    if _message_loop_callback:
        try:
            _message_loop_callback(src_mac, text)
        except Exception as e:
            print(f"[messaging] error en callback del usuario: {e}")


def start_message_loop(user_callback: Callable[[str, str], None]) -> None:
    print("start_message_loop")
    global _message_loop_callback
    _message_loop_callback = user_callback
    start_recv_loop(_internal_cb)


def stop_message_loop() -> None:
    stop_recv_loop()


def discover_peers(timeout: float = 2.0) -> list:
    """
    Envía petición de discovery (broadcast) y escucha replies durante `timeout` segundos.
    Devuelve lista de (mac, name).
    """
    print("Estoy buscando lso peers")
    peers = {}
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
    try:
        s.bind((INTERFACE, 0))
        s.settimeout(0.5)
        # enviar petición de discovery (broadcast)
        send_message(BROADCAST_MAC, DISCOVER_REQ)
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                raw, _ = s.recvfrom(65535)
            except socket.timeout:
                continue
            if len(raw) < 14:
                continue
            try:
                pkt_type = struct.unpack("!H", raw[12:14])[0]
            except Exception:
                continue
            if pkt_type != ETH_P_LINKCHAT:
                continue
            src_mac_bytes = raw[6:12]
            src_mac = ":".join(f"{b:02x}" for b in src_mac_bytes)
            try:
                info = parse_header(raw[14:])
            except Exception:
                continue
            if info["type"] != MSG:
                continue
            try:
                text = info["payload"].decode("utf-8", errors="replace")
            except Exception:
                continue
            if text.startswith(DISCOVER_REPLY_PREFIX):
                name = text[len(DISCOVER_REPLY_PREFIX) :]
                peers[src_mac] = name
    finally:
        try:
            s.close()
        except Exception:
            pass
    return list(peers.items())


def send_message_to_all(text: str, discover_timeout: float = 2.0) -> list:
    """
    Descubre peers y envía `text` por unicast a cada uno.
    Devuelve lista de MACs a las que se envió.
    """
    sent = []
    try:
        peers = discover_peers(timeout=discover_timeout)
    except Exception:
        peers = []
    for mac, name in peers:
        try:
            send_message(mac, text)
            sent.append(mac)
        except Exception:
            pass
    return sent
