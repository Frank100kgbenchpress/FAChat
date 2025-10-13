# src/files.py
import os
import hashlib
import threading
import time
import socket
import struct
from typing import Callable, Optional, Dict, Tuple

from protocol import (
    build_header,
    parse_header,
    FILE_START,
    FILE_CHUNK,
    FILE_END,
    ACK,
    new_file_id,
    FILE_CHANNEL,
)
from ethernet import (
    send_frame,
    start_recv_loop,
    stop_recv_loop,
    ETH_P_LINKCHAT,
    INTERFACE,
)

CHUNK_SIZE = 1000
BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"

# recepción en progreso
_in_progress: Dict[bytes, Dict] = {}
_lock = threading.Lock()
_user_cb: Optional[Callable[[str, str, str], None]] = None
_recv_started = False
_ack_sock: Optional[socket.socket] = None


def _safe_meta_decode(payload: bytes) -> Tuple[str, int]:
    """payload: b'filename|filesize'"""
    try:
        txt = payload.decode("utf-8", errors="replace")
        name, size_s = txt.split("|", 1)
        return name, int(size_s)
    except Exception:
        return "received_file", 0


def _get_ack_socket(timeout: float) -> socket.socket:
    global _ack_sock
    if _ack_sock is None:
        _ack_sock = socket.socket(
            socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003)
        )
        _ack_sock.bind((INTERFACE, 0))
    _ack_sock.settimeout(timeout)
    return _ack_sock


def _send_and_wait_ack(
    dest_mac: str,
    frame_bytes: bytes,
    file_id: bytes,
    seq: int,
    retries: int = 5,
    timeout: float = 1.0,
) -> bool:
    dest_bytes = bytes.fromhex(dest_mac.replace(":", ""))
    for attempt in range(1, retries + 1):
        s = _get_ack_socket(timeout)
        send_frame(dest_mac, frame_bytes)
        start = time.time()
        while True:
            try:
                raw, _ = s.recvfrom(65535)
            except socket.timeout:
                break
            if len(raw) < 14:
                continue
            pkt_type = struct.unpack("!H", raw[12:14])[0]
            if pkt_type != ETH_P_LINKCHAT:
                continue
            if raw[6:12] != dest_bytes:
                continue
            try:
                info = parse_header(raw[14:])
            except Exception:
                continue
            if info["type"] == ACK and info["id"] == file_id and info["seq"] == seq:
                return True
            if (time.time() - start) >= timeout:
                break
    return False


def send_file(
    dest_mac: str,
    path: str,
    use_ack: bool = True,
    retries: int = 5,
    timeout: float = 1.0,
) -> None:
    """
    Envía un archivo con STOP-AND-WAIT por canal FILE_CHANNEL.
    """
    print(f"send_file hacai {dest_mac} en {path}")
    if not dest_mac:
        dest_mac = BROADCAST_MAC
    if not os.path.isfile(path):
        print("FileNotFound")
        raise FileNotFoundError(path)

    filesize = os.path.getsize(path)
    filename_bytes = os.path.basename(path).encode("utf-8")

    file_id = new_file_id()

    meta = filename_bytes.decode("utf-8", errors="replace") + "|" + str(filesize)
    pkt_start = build_header(
        FILE_START, meta.encode("utf-8"), channel=FILE_CHANNEL, seq=0, file_id=file_id
    )
    send_frame(dest_mac, pkt_start)
    time.sleep(0.05)

    seq = 1
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            pkt = build_header(
                FILE_CHUNK, chunk, channel=FILE_CHANNEL, seq=seq, file_id=file_id
            )
            if use_ack:
                ok = _send_and_wait_ack(
                    dest_mac, pkt, file_id, seq, retries=retries, timeout=timeout
                )
                if not ok:
                    raise TimeoutError(
                        f"No ACK para seq={seq} después de {retries} intentos"
                    )
            else:
                send_frame(dest_mac, pkt)
            seq += 1

    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(65536), b""):
            sha256.update(b)
    pkt_end = build_header(
        FILE_END,
        sha256.hexdigest().encode("utf-8"),
        channel=FILE_CHANNEL,
        seq=seq,
        file_id=file_id,
    )
    send_frame(dest_mac, pkt_end)


def _file_recv_internal(src_mac: str, raw_payload: bytes):
    """
    Callback interno: parsea header y maneja FILE_START / FILE_CHUNK / FILE_END.
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
                return
            _in_progress[fid] = {
                "path": outname,
                "handle": fh,
                "expected": expected,
                "received": 0,
            }
            if _user_cb:
                _user_cb(src_mac, outname, "started")

        elif typ == FILE_CHUNK:
            if fid not in _in_progress:
                return
            entry = _in_progress[fid]
            try:
                entry["handle"].write(payload)
                entry["received"] += len(payload)
                if entry["expected"] and entry["received"] >= entry["expected"]:
                    try:
                        entry["handle"].close()
                    except Exception:
                        pass
                    if _user_cb:
                        _user_cb(src_mac, entry["path"], "completed")
                    _in_progress.pop(fid, None)
            except Exception as e:
                if _user_cb:
                    _user_cb(src_mac, entry.get("path", "unknown"), f"error:{e}")
                return
            # enviar ACK para este seq
            try:
                ack_pkt = build_header(
                    ACK, b"", channel=FILE_CHANNEL, seq=seq, file_id=fid
                )
                send_frame(src_mac, ack_pkt)
            except Exception:
                pass

        elif typ == FILE_END:
            if fid not in _in_progress:
                return
            entry = _in_progress[fid]
            try:
                entry["handle"].close()
            except Exception:
                pass
            remote_hash = payload.decode("utf-8", errors="replace")
            local_path = entry["path"]
            sha256 = hashlib.sha256()
            try:
                with open(local_path, "rb") as fh:
                    for b in iter(lambda: fh.read(65536), b""):
                        sha256.update(b)
                local_hash = sha256.hexdigest()
            except Exception:
                local_hash = None

            status = "finished"
            if remote_hash and local_hash and remote_hash != local_hash:
                status = "finished_hash_mismatch"

            if _user_cb:
                _user_cb(src_mac, entry["path"], status)
            _in_progress.pop(fid, None)


def start_file_loop(user_callback: Callable[[str, str, str], None]) -> None:
    global _user_cb, _recv_started
    _user_cb = user_callback

    if not _recv_started:
        # Registrar callback para FILE_CHANNEL
        from ethernet import register_channel_callback

        register_channel_callback(FILE_CHANNEL, _file_recv_internal)

        # Iniciar recv_loop solo una vez
        start_recv_loop(lambda src, payload: None)
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
