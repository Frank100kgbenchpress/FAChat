# src/protocol.py
"""
Construcción y parseo del header LinkChat.

Header (25 bytes):
- version: 1 byte
- type:    1 byte
- flags:   1 byte
- seq:     4 bytes (uint32, network order)
- id:     16 bytes (transfer id, UUID bytes or zeros)
- payload_len: 2 bytes (uint16, network order)
"""
import struct
import uuid

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
    """Genera id de 16 bytes (UUID4)."""
    return uuid.uuid4().bytes

def build_header(msg_type: int, payload: bytes, seq: int = 0, file_id: bytes = None, flags: int = 0) -> bytes:
    """
    Construye header + payload.
    - file_id: 16 bytes; si None se usan 16 ceros.
    - payload_len: se ajusta automáticamente (<= 0xFFFF).
    """
    if file_id is None:
        file_id = b'\x00' * 16
    else:
        if len(file_id) != 16:
            raise ValueError("file_id debe tener exactamente 16 bytes")

    payload_len = len(payload)
    if payload_len > 0xFFFF:
        raise ValueError("payload demasiado grande para un solo paquete (usa fragmentación)")

    header = struct.pack("!BBB", VERSION, msg_type, flags)
    header += struct.pack("!I", seq)
    header += file_id
    header += struct.pack("!H", payload_len)
    return header + payload

def parse_header(data: bytes) -> dict:
    """
    Parsea data (header + payload) y devuelve dict:
    {version, type, flags, seq, id (bytes), payload_len, payload (bytes)}
    """
    if len(data) < HEADER_LEN:
        raise ValueError("data demasiado corta para contener header")

    version = data[0]
    msg_type = data[1]
    flags = data[2]
    seq = struct.unpack("!I", data[3:7])[0]
    file_id = data[7:23]
    payload_len = struct.unpack("!H", data[23:25])[0]

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
