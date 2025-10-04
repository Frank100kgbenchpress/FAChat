# src/protocol.py
from ethernet import send_frame, start_recv_loop, stop_recv_loop, recv_one
import struct
import hashlib
import struct
import uuid

DEST_MAC = "ff:ff:ff:ff:ff:ff"  # Broadcast para pruebas
ETH_TYPE_MSG = 0x1234
ETH_TYPE_FILE = 0x1235
# src/protocol.py
"""
Construcción y parseo del header LinkChat.

Header (25 bytes total):
- version:     1 byte
- type:        1 byte
- flags:       1 byte
- seq:         4 bytes (uint32, network order)
- id:         16 bytes (transfer id, UUID bytes or zeros)
- payload_len: 2 bytes (uint16, network order)

Funciones principales:
- new_file_id() -> bytes(16)
- build_header(msg_type, payload, seq=0, file_id=None, flags=0) -> bytes (header+payload)
- parse_header(data: bytes) -> dict con campos: version,type,flags,seq,id,payload_len,payload
"""


# Tipos de mensaje
MSG = 0x01
FILE_START = 0x02
FILE_CHUNK = 0x03
FILE_END = 0x04
ACK = 0x05
DISCOVER = 0x06
DISCOVER_RESP = 0x07

VERSION = 1
HEADER_LEN = 25  # 1 + 1 + 1 + 4 + 16 + 2


def new_file_id() -> bytes:
    """Genera un identificador de 16 bytes (UUID4)."""
    return uuid.uuid4().bytes


def build_header(msg_type: int, payload: bytes, seq: int = 0, file_id: bytes = None, flags: int = 0) -> bytes:
    """
    Construye header + payload.
    - msg_type: uno de los tipos (MSG, FILE_START, ...)
    - payload: bytes del contenido
    - seq: número de secuencia (uint32)
    - file_id: 16 bytes (si None se usan 16 ceros)
    - flags: 1 byte de flags
    Retorna bytes = header(25 bytes) + payload
    """
    if file_id is None:
        file_id = b'\x00' * 16
    else:
        if len(file_id) != 16:
            raise ValueError("file_id debe tener exactamente 16 bytes")

    payload_len = len(payload)
    if payload_len > 0xFFFF:
        raise ValueError("payload demasiado grande para un solo paquete (usa fragmentación)")

    # empaquetar: version(1), type(1), flags(1)
    header = struct.pack("!BBB", VERSION, msg_type, flags)
    # seq (4 bytes, network order)
    header += struct.pack("!I", seq)
    # file_id (16 bytes)
    header += file_id
    # payload_len (2 bytes)
    header += struct.pack("!H", payload_len)

    return header + payload


def parse_header(data: bytes) -> dict:
    """
    Parsea data (header + payload) y devuelve un dict con:
    { version, type, flags, seq, id (bytes 16), payload_len, payload (bytes) }
    Lanza ValueError si data es más corto que HEADER_LEN o inconsistencias.
    """
    if len(data) < HEADER_LEN:
        raise ValueError("data demasiado corta para contener header")

    version = data[0]
    msg_type = data[1]
    flags = data[2]
    seq = struct.unpack("!I", data[3:7])[0]
    file_id = data[7:23]
    payload_len = struct.unpack("!H", data[23:25])[0]

    # extraer payload seguro (si payload_len excede lo que queda, se devuelve lo que haya)
    payload = data[25:25 + payload_len]

    return {
        "version": version,
        "type": msg_type,
        "flags": flags,
        "seq": seq,
        "id": file_id,
        "payload_len": payload_len,
        "payload": payload
    }


# ----------------- MENSAJES -----------------
def send_message(text: str):
    send_frame(DEST_MAC, text.encode("utf-8"), eth_type=ETH_TYPE_MSG)

def start_message_listener(callback):
    def on_packet(src_mac, payload):
        try:
            msg = payload.decode("utf-8", errors="ignore")
        except Exception:
            msg = str(payload)
        callback(src_mac, msg)

    start_recv_loop(on_packet, eth_type=ETH_TYPE_MSG)

def stop_message_listener():
    stop_recv_loop()

# ----------------- ARCHIVOS -----------------
def send_file(path: str):
    import os
    filesize = os.path.getsize(path)
    print(f"[file] Enviando '{path}' ({filesize} bytes)...")

    # enviar tamaño
    send_frame(DEST_MAC, struct.pack("!Q", filesize), eth_type=ETH_TYPE_FILE)

    # enviar bloques
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            send_frame(DEST_MAC, chunk, eth_type=ETH_TYPE_FILE)

    print("[file] Envío completado.")

def recv_file(outfile: str = "recv_file.txt"):
    print("[file] Esperando archivo...")

    # recibir tamaño
    src, payload = recv_one(eth_type=ETH_TYPE_FILE)
    filesize = struct.unpack("!Q", payload[:8])[0]
    print(f"[file] Tamaño esperado: {filesize} bytes")

    received = 0
    with open(outfile, "wb") as f:
        while received < filesize:
            src, payload = recv_one(eth_type=ETH_TYPE_FILE)
            f.write(payload)
            received += len(payload)
            print(f"[file] Progreso: {received}/{filesize} bytes", end="\r")

    with open(outfile, "rb") as f:
        data = f.read()
    sha256 = hashlib.sha256(data).hexdigest()
    print(f"\n[file] Archivo guardado en {outfile}")
    print(f"[file] SHA256: {sha256}")
