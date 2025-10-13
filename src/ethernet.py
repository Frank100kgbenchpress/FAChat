import socket
import struct
import threading
import time
import os
from typing import Callable, Optional, Dict, List


# --- CONFIGURACIÓN AUTOMÁTICA DE INTERFAZ ---
def detect_interface() -> str:
    """
    Detecta la interfaz correcta según el entorno:
      - Si está corriendo dentro de Docker → usa 'eth0'
      - Si está corriendo en un sistema real → usa 'wlo1' o 'enp...' según disponibilidad
    """
    # Si existe /.dockerenv, estamos dentro de un contenedor Docker
    if os.path.exists("/.dockerenv"):
        print("Interfaz eth0")
        return "eth0"

    # En máquina real: tratar de detectar automáticamente una interfaz válida
    candidates = ["wlo1", "wlx", "enp3s0", "eth0", "enp1s0", "wlp2s0"]
    for iface in candidates:
        print(f"Buscando interfaz {iface}")
        path = f"/sys/class/net/{iface}"
        if os.path.exists(path):
            print(f"Encontrado interfaz,{iface}")
            return iface
    print("No encontro ninguna interfaz")
    # Si no se encuentra ninguna válida, lanzar error
    raise RuntimeError("No se pudo detectar una interfaz de red válida.")


# Asignar la interfaz automáticamente
INTERFACE = detect_interface()
ETH_P_LINKCHAT = 0x1234  # EtherType a usar

# sockets/estado globales
_send_sock: Optional[socket.socket] = None
_recv_sock: Optional[socket.socket] = None
_recv_thread: Optional[threading.Thread] = None
_recv_running = False

# Nuevo: Sistema de múltiples callbacks por canal
_channel_callbacks: Dict[int, List[Callable]] = {}


def register_channel_callback(channel: int, callback: Callable[[str, bytes], None]):
    """Registrar callback para un canal específico"""
    if channel not in _channel_callbacks:
        _channel_callbacks[channel] = []
    _channel_callbacks[channel].append(callback)


def _mac_str_to_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def get_interface_mac(interface: str) -> bytes:
    """Obtiene la MAC de la interfaz leyendo /sys/class/net/<interface>/address."""
    path = f"/sys/class/net/{interface}/address"
    try:
        with open(path, "r") as f:
            mac_str = f.read().strip()
        return bytes.fromhex(mac_str.replace(":", ""))
    except FileNotFoundError:
        raise RuntimeError(f"Interfaz {interface} no encontrada (revisa INTERFACE).")
    except Exception as e:
        raise RuntimeError(f"Error leyendo MAC desde {path}: {e}")


def _ensure_send_socket():
    global _send_sock
    if _send_sock is None:
        _send_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        _send_sock.bind((INTERFACE, 0))


def send_frame(dest_mac: str, payload: bytes, eth_type: int = ETH_P_LINKCHAT) -> None:
    """Envía una trama Ethernet: dest(6) + src(6) + eth_type(2) + payload."""
    _ensure_send_socket()

    dest = _mac_str_to_bytes(dest_mac)
    try:
        src = get_interface_mac(INTERFACE)
    except Exception as e:
        print(f"[ethernet] error obteniendo MAC de {INTERFACE}: {e}")
        raise

    eth_type_bytes = struct.pack("!H", eth_type)
    frame = dest + src + eth_type_bytes + payload

    try:
        sent = _send_sock.send(frame)
        print(f"[ethernet] enviado {sent} bytes a {dest_mac} via {INTERFACE}")
    except PermissionError:
        print("[ethernet] permiso denegado: ejecuta con sudo")
        raise
    except Exception as e:
        print(f"[ethernet] error enviando: {e}")
        raise


def _ensure_recv_socket(eth_type: int = ETH_P_LINKCHAT):
    global _recv_sock
    if _recv_sock is None:
        _recv_sock = socket.socket(
            socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003)
        )
        _recv_sock.bind((INTERFACE, 0))


def recv_one(eth_type: int = ETH_P_LINKCHAT) -> tuple[str, bytes]:
    print("recv_one")
    """Bloqueante: espera y devuelve (src_mac_str, payload) del primer paquete con eth_type."""
    _ensure_recv_socket(eth_type)
    while True:
        raw, _ = _recv_sock.recvfrom(65535)
        if len(raw) < 14:
            continue
        try:
            pkt_eth_type = struct.unpack("!H", raw[12:14])[0]
        except Exception:
            continue
        if pkt_eth_type != eth_type:
            continue
        src = raw[6:12]
        payload = raw[14:]
        src_mac_str = ":".join(f"{b:02x}" for b in src)
        return src_mac_str, payload


def _recv_loop(callback: Callable[[str, bytes], None], eth_type: int):
    """Loop que corre en hilo: recibe paquetes y routea por canal."""
    global _recv_running
    _ensure_recv_socket(eth_type)
    _recv_running = True

    from protocol import parse_header

    try:
        while _recv_running:
            try:
                raw, _ = _recv_sock.recvfrom(65535)
            except OSError:
                break
            if len(raw) < 14:
                continue
            try:
                pkt_eth_type = struct.unpack("!H", raw[12:14])[0]
            except Exception:
                continue
            if pkt_eth_type != eth_type:
                continue
            src = raw[6:12]
            payload = raw[14:]
            src_mac_str = ":".join(f"{b:02x}" for b in src)

            try:
                # Intentar parsear header para routing por canal
                info = parse_header(payload)
                channel = info["channel"]

                # Llamar callbacks específicos del canal
                if channel in _channel_callbacks:
                    for cb in _channel_callbacks[channel]:
                        cb(src_mac_str, payload)

                # También llamar callback general
                callback(src_mac_str, payload)

            except Exception:
                # Si no se puede parsear, solo callback general
                callback(src_mac_str, payload)

    finally:
        _recv_running = False


def start_recv_loop(
    callback: Callable[[str, bytes], None], eth_type: int = ETH_P_LINKCHAT
) -> None:
    """Lanza un hilo en background que llama callback(src_mac, payload) por cada paquete."""
    print("Recibiendo mensajes")
    global _recv_thread, _recv_running
    if _recv_thread and _recv_thread.is_alive():
        return
    _recv_thread = threading.Thread(
        target=_recv_loop, args=(callback, eth_type), daemon=True
    )
    _recv_thread.start()

    # esperar confirmación de inicio
    wait = 0.0
    while wait < 2.0:
        if _recv_running:
            return
        time.sleep(0.02)
        wait += 0.02


def stop_recv_loop():
    """Detiene el loop de recepción"""
    global _recv_running, _recv_sock, _recv_thread
    _recv_running = False
    try:
        if _recv_sock:
            _recv_sock.close()
    except Exception:
        pass
    _recv_sock = None

    try:
        if _recv_thread and _recv_thread.is_alive():
            _recv_thread.join(timeout=1.0)
    except Exception:
        pass
