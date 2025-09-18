"""
Raw Ethernet functions (send/receive) for LinkChat
Requiere permisos de superusuario (sudo).
"""

import socket
import struct
import fcntl
import struct
# Ajusta esta interfaz a la de tu máquina (ej. "enp0s3", "eth0", "wlp2s0")
INTERFACE = "wlp2s0"

def send_frame(dest_mac: str, payload: bytes, eth_type: int = 0x1234) -> None:
    """
    Envía una trama Ethernet con un payload al destino indicado.
    dest_mac: "AA:BB:CC:DD:EE:FF"
    payload: bytes
    eth_type: 2 bytes (por defecto 0x1234 para LinkChat)
    """
    # Convertir MAC destino
    dest_mac_bytes = bytes.fromhex(dest_mac.replace(":", ""))

    # Obtener la MAC origen de la interfaz
    src_mac_bytes = get_interface_mac(INTERFACE)

    # Empaquetar cabecera Ethernet: [dest][src][eth_type]
    eth_header = dest_mac_bytes + src_mac_bytes + struct.pack("!H", eth_type)

    # Trama completa
    frame = eth_header + payload

    # Crear socket RAW
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    sock.bind((INTERFACE, 0))
    sock.send(frame)
    sock.close()
    print(f"[+] Trama enviada a {dest_mac}")


def recv_frame() -> tuple[str, bytes]:
    """
    Recibe una trama Ethernet.
    Retorna (mac_origen_str, payload)
    """
    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(3))

    raw_data, addr = sock.recvfrom(65535)

    # Parsear cabecera Ethernet (14 bytes: dest 6, src 6, eth_type 2)
    dest_mac = raw_data[0:6]
    src_mac = raw_data[6:12]
    eth_type = struct.unpack("!H", raw_data[12:14])[0]
    payload = raw_data[14:]

    src_mac_str = ":".join(f"{b:02x}" for b in src_mac)

    return src_mac_str, payload


def get_interface_mac(interface: str) -> bytes:
    """
    Obtiene la MAC de la interfaz en forma de bytes.
    """
    
    SIOCGIFHWADDR = 0x8927

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(sock.fileno(), SIOCGIFHWADDR,
                       struct.pack("256s", interface[:15].encode("utf-8")))
    return info[18:24]  # MAC address
