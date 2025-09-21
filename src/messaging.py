# src/messaging.py
"""
Funciones de mensajería usando protocol.py + ethernet.py

Exporta:
- send_message(dest_mac, text)
- receive_message_blocking() -> (src_mac, text)
- start_message_loop(callback) -> callback(src_mac, text) en background
- stop_message_loop()
"""
from protocol import build_header, parse_header, MSG
from ethernet import send_frame, recv_one, start_recv_loop, stop_recv_loop
from typing import Callable, Optional

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"

def send_message(dest_mac: str, text: str, seq: int = 0) -> None:
    """
    Envía un mensaje de texto al destino (dest_mac).
    Si dest_mac es None o vacío, usa broadcast.
    """
    if not dest_mac:
        dest_mac = BROADCAST_MAC
    payload = text.encode("utf-8")
    pkt = build_header(MSG, payload, seq=seq)
    send_frame(dest_mac, pkt)


def receive_message_blocking() -> tuple[str, str]:
    """
    Bloqueante: espera un paquete y devuelve (src_mac, text) si es MSG.
    Si llega otro tipo de paquete, lo ignora y espera el siguiente.
    """
    while True:
        src_mac, raw = recv_one()  # recv_one ya filtra eth_type y devuelve payload (header+payload)
        try:
            info = parse_header(raw)
        except Exception:
            # paquete inválido para nuestro protocolo -> ignorar
            continue
        if info["type"] == MSG:
            text = info["payload"].decode("utf-8", errors="replace")
            return src_mac, text
        # si no es MSG, ignorar y continuar


# background loop helpers
_message_loop_callback: Optional[Callable[[str, str], None]] = None

def _internal_cb(src_mac: str, raw_payload: bytes):
    """
    Callback que adapta la interface de ethernet.start_recv_loop -> parsea header y llama al user callback.
    """
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
        # no queremos que una excepción mate el loop de recepción
        print(f"[messaging] error en callback del usuario: {e}")

def start_message_loop(user_callback: Callable[[str, str], None]) -> None:
    """
    Inicia un hilo background que llama user_callback(src_mac, text) por cada mensaje MSG recibido.
    """
    global _message_loop_callback
    _message_loop_callback = user_callback
    start_recv_loop(_internal_cb)  # start_recv_loop provisto por ethernet.py

def stop_message_loop() -> None:
    """Detiene el loop de mensajes."""
    stop_recv_loop()
