# src/files.py
"""
Transferencia de archivos para LinkChat (stop-and-wait con ACKs).

Funciones públicas:
- send_file(dest_mac, path, use_ack=True, retries=5, timeout=1.0)
- start_file_loop(user_callback)  # callback(src_mac, filepath, status_str)
- stop_file_loop()
- receive_file_blocking() -> (src_mac, path)

Requiere:
- protocol.build_header / parse_header y tipos FILE_START, FILE_CHUNK, FILE_END, ACK
- ethernet.send_frame, ethernet.start_recv_loop, ethernet.stop_recv_loop
"""
import os
import hashlib
import threading
import time
import socket
import struct
from typing import Callable, Optional, Dict, Tuple

from protocol import build_header, parse_header, FILE_START, FILE_CHUNK, FILE_END, ACK, new_file_id
from ethernet import send_frame, start_recv_loop, stop_recv_loop, ETH_P_LINKCHAT, INTERFACE

CHUNK_SIZE = 1200
BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"

# recepción en progreso
_in_progress: Dict[bytes, Dict] = {}
_lock = threading.Lock()
_user_cb: Optional[Callable[[str, str, str], None]] = None
_recv_started = False


def _safe_meta_decode(payload: bytes) -> Tuple[str, int]:
    """payload: b'filename|filesize'"""
    try:
        txt = payload.decode("utf-8", errors="replace")
        name, size_s = txt.split("|", 1)
        return name, int(size_s)
    except Exception:
        return "received_file", 0


def _send_and_wait_ack(dest_mac: str, frame_bytes: bytes, file_id: bytes, seq: int,
                       retries: int = 5, timeout: float = 1.0) -> bool:
    """
    Envía frame_bytes (ya construido) a dest_mac y espera ACK(file_id, seq).
    Usa un socket AF_PACKET temporal para escuchar ACKs (ETH_P_ALL) con timeout.
    Devuelve True si se recibió ACK, False si agotó reintentos.
    """
    # enviar
    for attempt in range(1, retries + 1):
        send_frame(dest_mac, frame_bytes)
        # Crear socket temporal para escuchar ACKs (no usamos recv_one global para no interferir)
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
        try:
            s.bind((INTERFACE, 0))
            s.settimeout(timeout)
            start = time.time()
            while True:
                try:
                    raw, _ = s.recvfrom(65535)
                except socket.timeout:
                    break
                if len(raw) < 14:
                    continue
                try:
                    pkt_type = struct.unpack("!H", raw[12:14])[0]
                except Exception:
                    continue
                if pkt_type != ETH_P_LINKCHAT:
                    continue
                # data after ethernet header
                data = raw[14:]
                try:
                    info = parse_header(data)
                except Exception:
                    continue
                if info["type"] == ACK and info["id"] == file_id and info["seq"] == seq:
                    # ACK recibido
                    return True
                # else: seguir esperando hasta timeout
                if (time.time() - start) >= timeout:
                    break
        finally:
            try:
                s.close()
            except Exception:
                pass
        # si no llegó ACK, reintentar
    return False


def send_file(dest_mac: str, path: str, use_ack: bool = True, retries: int = 5, timeout: float = 1.0) -> None:
    """
    Envía un archivo con STOP-AND-WAIT.
    - dest_mac: mac destino (usa BROADCAST_MAC para testing en la misma máquina)
    - use_ack: si True espera ACK por cada chunk
    - retries, timeout: parámetros para reintentos de ACK
    """
    if not dest_mac:
        dest_mac = BROADCAST_MAC
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    filesize = os.path.getsize(path)
    filename_bytes = os.path.basename(path).encode("utf-8")

    # generar file_id de 16 bytes (UUID)
    file_id = new_file_id()

    # FILE_START con metadata "name|size"
    meta = filename_bytes.decode("utf-8", errors="replace") + "|" + str(filesize)
    pkt_start = build_header(FILE_START, meta.encode("utf-8"), seq=0, file_id=file_id)
    send_frame(dest_mac, pkt_start)
    # opcional: esperar pequeña pausa
    time.sleep(0.05)

    seq = 1
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            pkt = build_header(FILE_CHUNK, chunk, seq=seq, file_id=file_id)
            if use_ack:
                ok = _send_and_wait_ack(dest_mac, pkt, file_id, seq, retries=retries, timeout=timeout)
                if not ok:
                    raise TimeoutError(f"No ACK para seq={seq} después de {retries} intentos")
            else:
                send_frame(dest_mac, pkt)
            seq += 1

    # calcular hash y enviar FILE_END con hash hex
    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(65536), b""):
            sha256.update(b)
    pkt_end = build_header(FILE_END, sha256.hexdigest().encode("utf-8"), seq=seq, file_id=file_id)
    # enviar FILE_END (no requerimos ACK del end)
    send_frame(dest_mac, pkt_end)


def _file_recv_internal(src_mac: str, raw_payload: bytes):
    """
    Callback interno: parsea header y maneja FILE_START / FILE_CHUNK / FILE_END.
    Envía ACKs por cada chunk (si corresponde).
    """
    global _user_cb
    try:
        info = parse_header(raw_payload)
    except Exception:
        return

    typ = info["type"]
    fid = info["id"]
    payload = info["payload"]
    seq = info["seq"]

    with _lock:
        if typ == FILE_START:
            fname, expected = _safe_meta_decode(payload)
            outname = f"recv_{fname}"
            if os.path.exists(outname):
                base, ext = os.path.splitext(outname)
                i = 1
                while os.path.exists(f"{base}_{i}{ext}"):
                    i += 1
                outname = f"{base}_{i}{ext}"
            fh = open(outname, "wb")
            _in_progress[fid] = {"path": outname, "handle": fh, "expected": expected, "received": 0}
            if _user_cb:
                _user_cb(src_mac, outname, "started")

        elif typ == FILE_CHUNK:
            if fid not in _in_progress:
                # sin metadata -> ignorar
                return
            entry = _in_progress[fid]
            try:
                entry["handle"].write(payload)
                entry["received"] += len(payload)
            except Exception as e:
                if _user_cb:
                    _user_cb(src_mac, entry.get("path", "unknown"), f"error:{e}")
                return
            # enviar ACK para este seq
            try:
                ack_pkt = build_header(ACK, b"", seq=seq, file_id=fid)
                send_frame(src_mac, ack_pkt)
            except Exception:
                pass
            if _user_cb:
                _user_cb(src_mac, entry["path"], f"chunk:{seq}")

        elif typ == FILE_END:
            if fid not in _in_progress:
                return
            entry = _in_progress.pop(fid)
            try:
                entry["handle"].close()
            except Exception:
                pass
            remote_hash = payload.decode("utf-8", errors="replace")
            # calcular sha local
            sha256 = hashlib.sha256()
            with open(entry["path"], "rb") as fh:
                for b in iter(lambda: fh.read(65536), b""):
                    sha256.update(b)
            local_hash = sha256.hexdigest()
            status = "finished"
            if remote_hash and remote_hash != local_hash:
                status = f"finished_hash_mismatch remote={remote_hash} local={local_hash}"
            if _user_cb:
                _user_cb(src_mac, entry["path"], status)


def start_file_loop(user_callback: Callable[[str, str, str], None]) -> None:
    """
    Inicia recepción de archivos en background. callback(src_mac, path, status).
    """
    global _user_cb, _recv_started
    _user_cb = user_callback
    if not _recv_started:
        start_recv_loop(_file_recv_internal)
        _recv_started = True


def stop_file_loop() -> None:
    """
    Detiene loop y limpia recursos.
    """
    global _user_cb, _recv_started
    stop_recv_loop()
    _user_cb = None
    _recv_started = False
    # cerrar y limpiar handles si quedan
    with _lock:
        for fid, entry in list(_in_progress.items()):
            try:
                entry["handle"].close()
            except Exception:
                pass
            _in_progress.pop(fid, None)


def receive_file_blocking() -> Tuple[Optional[str], Optional[str]]:
    """
    Bloqueante: espera a que termine un archivo y devuelve (src_mac, path).
    Implementado con evento y callback temporal.
    """
    event = threading.Event()
    result = {"src": None, "path": None}

    def cb(src_mac, path, status):
        if status.startswith("finished"):
            result["src"] = src_mac
            result["path"] = path
            event.set()

    start_file_loop(cb)
    event.wait()
    stop_file_loop()
    return result["src"], result["path"]
