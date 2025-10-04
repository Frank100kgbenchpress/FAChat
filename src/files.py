# src/files.py
"""
Transferencia de archivos para LinkChat (stop-and-wait con ACKs).

Incluye prints de depuración para traza de chunks/ACKs.
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
    Socket temporal AF_PACKET (ETH_P_ALL) con timeout.
    Devuelve True si se recibió ACK, False si agotó reintentos.
    """
    for attempt in range(1, retries + 1):
        send_frame(dest_mac, frame_bytes)
        print(f"[send_ack] enviado seq={seq} attempt={attempt} dest={dest_mac} file_id={file_id.hex()}")
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
        try:
            s.bind((INTERFACE, 0))
            s.settimeout(timeout)
            start = time.time()
            while True:
                try:
                    raw, _ = s.recvfrom(65535)
                except socket.timeout:
                    # timeout interno, salimos para reintentar
                    break
                if len(raw) < 14:
                    continue
                try:
                    pkt_type = struct.unpack("!H", raw[12:14])[0]
                except Exception:
                    continue
                # filtrar por nuestro ethertype
                if pkt_type != ETH_P_LINKCHAT:
                    continue
                data = raw[14:]
                # intento parse header
                try:
                    info = parse_header(data)
                except Exception:
                    # no es un paquete nuestro (o header corrupto)
                    continue
                # debug: mostrar paquetes recibidos por socket temporal
                if info["type"] == ACK:
                    print(f"[send_ack] socket temporal recibió ACK id={info['id'].hex()} seq={info['seq']}")
                if info["type"] == ACK and info["id"] == file_id and info["seq"] == seq:
                    print(f"[send_ack] ACK CORRECTO recibido seq={seq} (attempt={attempt})")
                    return True
                if (time.time() - start) >= timeout:
                    break
        finally:
            try:
                s.close()
            except Exception:
                pass
        print(f"[send_ack] no ACK para seq={seq} en attempt={attempt}, reintentando...")
    print(f"[send_ack] agotados {retries} intentos para seq={seq}")
    return False


def send_file(dest_mac: str, path: str, use_ack: bool = True, retries: int = 5, timeout: float = 1.0) -> None:
    """
    Envía un archivo con STOP-AND-WAIT.
    """
    if not dest_mac:
        dest_mac = BROADCAST_MAC
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    filesize = os.path.getsize(path)
    filename_bytes = os.path.basename(path).encode("utf-8")

    file_id = new_file_id()

    meta = filename_bytes.decode("utf-8", errors="replace") + "|" + str(filesize)
    pkt_start = build_header(FILE_START, meta.encode("utf-8"), seq=0, file_id=file_id)
    print(f"[send] FILE_START file_id={file_id.hex()} name={filename_bytes.decode()} size={filesize}")
    send_frame(dest_mac, pkt_start)
    time.sleep(0.05)

    seq = 1
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            print(f"[send] preparando seq={seq} len={len(chunk)}")
            pkt = build_header(FILE_CHUNK, chunk, seq=seq, file_id=file_id)
            if use_ack:
                ok = _send_and_wait_ack(dest_mac, pkt, file_id, seq, retries=retries, timeout=timeout)
                if not ok:
                    raise TimeoutError(f"No ACK para seq={seq} después de {retries} intentos")
            else:
                send_frame(dest_mac, pkt)
            seq += 1

    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(65536), b""):
            sha256.update(b)
    pkt_end = build_header(FILE_END, sha256.hexdigest().encode("utf-8"), seq=seq, file_id=file_id)
    print(f"[send] FILE_END file_id={file_id.hex()} seq={seq} sha256={sha256.hexdigest()}")
    send_frame(dest_mac, pkt_end)


def _file_recv_internal(src_mac: str, raw_payload: bytes):
    """
    Callback interno: parsea header y maneja FILE_START / FILE_CHUNK / FILE_END.
    """
    global _user_cb
    try:
        info = parse_header(raw_payload)
    except Exception:
        # paquete no parseable
        return

    typ = info["type"]
    fid = info["id"]
    payload = info["payload"]
    seq = info["seq"]

    # convertir fid a hex para debug
    fid_hex = fid.hex()

    with _lock:
        if typ == FILE_START:
            # reinicio si ya estaba
            if fid in _in_progress:
                try:
                    _in_progress[fid]["handle"].close()
                except Exception:
                    pass
                _in_progress.pop(fid, None)

            fname, expected = _safe_meta_decode(payload)
            outname = f"recv_{fname}"
            if os.path.exists(outname):
                base, ext = os.path.splitext(outname)
                i = 1
                while os.path.exists(f"{base}_{i}{ext}"):
                    i += 1
                outname = f"{base}_{i}{ext}"
            try:
                fh = open(outname, "wb")
            except Exception as e:
                print(f"[recv] ERROR al abrir {outname}: {e}")
                return
            _in_progress[fid] = {
                "path": outname,
                "handle": fh,
                "expected": expected,
                "received": 0
            }
            print(f"[recv] FILE_START from={src_mac} file_id={fid_hex} name={fname} expected={expected} -> out={outname}")
            if _user_cb:
                _user_cb(src_mac, outname, "started")

        elif typ == FILE_CHUNK:
            if fid not in _in_progress:
                print(f"[recv] FILE_CHUNK recibido para file_id={fid_hex} pero no hay metadata; ignorando")
                return
            entry = _in_progress[fid]
            try:
                entry["handle"].write(payload)
                entry["received"] += len(payload)
                print(f"[recv] FILE_CHUNK from={src_mac} file_id={fid_hex} seq={seq} len={len(payload)} total_received={entry['received']}/{entry['expected']}")
                # chequeo básico de orden (stop-and-wait debería mantener orden)
                # expected_seq aproximado:
                expected_seq = (entry["received"] - len(payload)) // CHUNK_SIZE + 1
                if seq != expected_seq and entry["expected"] > 0:
                    # Este chequeo es heurístico, imprime advertencia si detecta desorden
                    print(f"[recv][WARN] posible desorden: esperado_seq~{expected_seq} recibido_seq={seq} (file_id={fid_hex})")
                # si ya recibimos todo lo esperado, cerrar
                if entry["expected"] and entry["received"] >= entry["expected"]:
                    try:
                        entry["handle"].close()
                    except Exception:
                        pass
                    if _user_cb:
                        _user_cb(src_mac, entry["path"], "completed")
                    _in_progress.pop(fid, None)
            except Exception as e:
                print(f"[recv] ERROR escribiendo chunk seq={seq} file_id={fid_hex}: {e}")
                if _user_cb:
                    _user_cb(src_mac, entry.get("path", "unknown"), f"error:{e}")
                return
            # enviar ACK para este seq
            try:
                ack_pkt = build_header(ACK, b"", seq=seq, file_id=fid)
                send_frame(src_mac, ack_pkt)
                print(f"[recv] enviado ACK seq={seq} file_id={fid_hex} a {src_mac}")
            except Exception as e:
                print(f"[recv] error enviando ACK seq={seq} file_id={fid_hex}: {e}")

        elif typ == FILE_END:
            if fid not in _in_progress:
                print(f"[recv] FILE_END recibido para file_id={fid_hex} pero no hay entrada en progreso")
                return
            entry = _in_progress[fid]
            try:
                entry["handle"].close()
            except Exception:
                pass
            # calcular hash local y comparar
            remote_hash = payload.decode("utf-8", errors="replace")
            local_path = entry["path"]
            local_size = 0
            try:
                local_size = os.path.getsize(local_path)
            except Exception:
                pass
            sha256 = hashlib.sha256()
            try:
                with open(local_path, "rb") as fh:
                    for b in iter(lambda: fh.read(65536), b""):
                        sha256.update(b)
                local_hash = sha256.hexdigest()
            except Exception as e:
                local_hash = None
                print(f"[recv] ERROR calculando hash local: {e}")

            status = "finished"
            if remote_hash and local_hash and remote_hash != local_hash:
                status = f"finished_hash_mismatch remote={remote_hash} local={local_hash}"
                print(f"[recv] HASH MISMATCH file_id={fid_hex} remote={remote_hash} local={local_hash}")
            else:
                print(f"[recv] FILE_END file_id={fid_hex} local_size={local_size} expected={entry.get('expected')} local_hash={local_hash}")

            if _user_cb:
                _user_cb(src_mac, entry["path"], status)
            _in_progress.pop(fid, None)


def start_file_loop(user_callback: Callable[[str, str, str], None]) -> None:
    global _user_cb, _recv_started
    _user_cb = user_callback
    if not _recv_started:
        start_recv_loop(_file_recv_internal)
        _recv_started = True


def stop_file_loop() -> None:
    global _user_cb, _recv_started
    stop_recv_loop()
    _user_cb = None
    _recv_started = False
    with _lock:
        for fid, entry in list(_in_progress.items()):
            try:
                entry["handle"].close()
            except Exception:
                pass
            _in_progress.pop(fid, None)


def receive_file_blocking() -> Tuple[Optional[str], Optional[str]]:
    event = threading.Event()
    result = {"src": None, "path": None}

    def cb(src_mac, path, status):
        if status.startswith("finished") or status == "completed":
            result["src"] = src_mac
            result["path"] = path
            event.set()

    start_file_loop(cb)
    event.wait()
    stop_file_loop()
    return result["src"], result["path"]

