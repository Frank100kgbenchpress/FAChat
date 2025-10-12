# src/protocol.py
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

# Canales para routing
CHAT_CHANNEL = 0x01
FILE_CHANNEL = 0x02
DISCOVERY_CHANNEL = 0x03

VERSION = 1
HEADER_LEN = 25  # 1 + 1 + 1 + 4 + 16 + 2


def new_file_id() -> bytes:
    """Genera un identificador de 16 bytes (UUID4)."""
    return uuid.uuid4().bytes


def build_header(
    msg_type: int,
    payload: bytes,
    channel: int = CHAT_CHANNEL,
    seq: int = 0,
    file_id: bytes = None,
) -> bytes:
    """
    Construye header + payload.
    - msg_type: uno de los tipos (MSG, FILE_START, ...)
    - payload: bytes del contenido
    - channel: canal para routing (CHAT_CHANNEL, FILE_CHANNEL, ...)
    - seq: número de secuencia (uint32)
    - file_id: 16 bytes (si None se usan 16 ceros)
    Retorna bytes = header(25 bytes) + payload
    """
    if file_id is None:
        file_id = b"\x00" * 16
    else:
        if len(file_id) != 16:
            raise ValueError("file_id debe tener exactamente 16 bytes")

    payload_len = len(payload)
    if payload_len > 0xFFFF:
        raise ValueError("payload demasiado grande para un solo paquete")

    # empaquetar: version(1), type(1), channel(1)
    header = struct.pack("!BBB", VERSION, msg_type, channel)
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
    { version, type, channel, seq, id (bytes 16), payload_len, payload (bytes) }
    """
    if len(data) < HEADER_LEN:
        raise ValueError("data demasiado corta para contener header")

    version = data[0]
    msg_type = data[1]
    channel = data[2]  # Nuevo: canal extraído del byte de flags
    seq = struct.unpack("!I", data[3:7])[0]
    file_id = data[7:23]
    payload_len = struct.unpack("!H", data[23:25])[0]

    payload = data[25 : 25 + payload_len]

    return {
        "version": version,
        "type": msg_type,
        "channel": channel,
        "seq": seq,
        "id": file_id,
        "payload_len": payload_len,
        "payload": payload,
    }
