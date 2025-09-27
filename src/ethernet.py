# src/ethernet.py
"""
ethernet.py - Helper de bajo nivel para LinkChat.

Funciones expuestas:
- send_frame(dest_mac, payload, eth_type=...)
- recv_one(eth_type=...) -> (src_mac_str, payload)  # bloqueante
- start_recv_loop(callback, eth_type=...)  # callback(src_mac, payload)
- stop_recv_loop()

Nota:
- Ajusta INTERFACE al nombre de tu interfaz (ver con `ip a`).
- Requiere permisos para enviar/recibir tramas raw (sudo) excepto para leer la MAC vía /sys.
"""
import socket
import struct
import threading
import time
from typing import Callable, Optional

# --- CONFIGURA ESTO a la interfaz de tu Mint (ip a para verla) ---
INTERFACE = "wlp2s0"           # <- AJUSTA AQUÍ SI ES NECESARIO
ETH_P_LINKCHAT = 0x1234        # EtherType a usar

# sockets/estado globales
_send_sock: Optional[socket.socket] = None
_recv_sock: Optional[socket.socket] = None
_recv_thread: Optional[threading.Thread] = None
_recv_running = False


def _mac_str_to_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def get_interface_mac(interface: str) -> bytes:
    """
    Obtiene la MAC de la interfaz leyendo /sys/class/net/<interface>/address.
    Devuelve 6 bytes.
    No requiere privilegios especiales.
    """
    path = f"/sys/class/net/{interface}/address"
    try:
        with open(path, "r") as f:
            mac_str = f.read().strip()
        # mac_str tiene formato "aa:bb:cc:dd:ee:ff"
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
        print(f"[ethernet] send socket creado y ligado a {INTERFACE}")


def send_frame(dest_mac: str, payload: bytes, eth_type: int = ETH_P_LINKCHAT) -> None:
    """
    Envía una trama Ethernet: dest(6) + src(6) + eth_type(2) + payload.
    dest_mac: "AA:BB:CC:DD:EE:FF"
    """
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
        print(f"[ethernet] enviado {sent} bytes a {dest_mac} (eth_type={hex(eth_type)})")
    except PermissionError:
        print("[ethernet] permiso denegado: ejecuta con sudo")
        raise
    except Exception as e:
        print(f"[ethernet] error enviando: {e}")
        raise


def _ensure_recv_socket(eth_type: int = ETH_P_LINKCHAT):
    """
    Abre socket AF_PACKET en ETH_P_ALL y filtramos en Python.
    Esto evita problemas con pasar eth_type en la creación del socket.
    """
    global _recv_sock
    if _recv_sock is None:
        # ETH_P_ALL = 0x0003 -> usar ntohs(0x0003) en constructor (convensión común)
        _recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
        _recv_sock.bind((INTERFACE, 0))
        print(f"[ethernet] recv socket creado y ligado a {INTERFACE} (escucha ALL, filtrando por {hex(eth_type)})")


def recv_one(eth_type: int = ETH_P_LINKCHAT) -> tuple[str, bytes]:
    """
    Bloqueante: espera y devuelve (src_mac_str, payload) del primer paquete con eth_type.
    """
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
    """
    Loop que corre en hilo: recibe paquetes y llama callback(src_mac_str, payload).
    """
    global _recv_running
    _ensure_recv_socket(eth_type)
    _recv_running = True
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
                callback(src_mac_str, payload)
            except Exception as e:
                # no queremos que una excepción en el callback termine el loop
                print(f"[ethernet] callback error: {e}")
    finally:
        _recv_running = False


def start_recv_loop(callback: Callable[[str, bytes], None], eth_type: int = ETH_P_LINKCHAT) -> None:
    """
    Lanza un hilo en background que llama callback(src_mac, payload) por cada paquete.
    Espera brevemente hasta confirmar que el loop arrancó.
    """
    global _recv_thread, _recv_running
    if _recv_thread and _recv_thread.is_alive():
        print("[ethernet] recv thread ya activo")
        return
    _recv_thread = threading.Thread(target=_recv_loop, args=(callback, eth_type), daemon=True)
    _recv_thread.start()

    # esperar confirmación de inicio (timeout)
    wait = 0.0
    while wait < 2.0:
        if _recv_running:
            print("[ethernet] recv loop iniciado correctamente")
            return
        time.sleep(0.02)
        wait += 0.02
    print("[ethernet] advertencia: recv loop no confirmó inicio en 2s")


def stop_recv_loop():
    """Detiene el loop de recepción y cierra socket. Espera a que el hilo termine."""
    global _recv_running, _recv_sock, _recv_thread
    _recv_running = False
    try:
        if _recv_sock:
            _recv_sock.close()
    except Exception:
        pass
    _recv_sock = None

    # intentar hacer join del hilo (no bloquear indefinidamente)
    try:
        if _recv_thread and _recv_thread.is_alive():
            _recv_thread.join(timeout=1.0)
    except Exception:
        pass
