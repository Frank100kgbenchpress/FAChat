import os
# from typing import Optional

from protocol import build_header, new_file_id, FILE_START, FILE_END, FILE_CHANNEL
from ethernet import send_frame
from files import send_file


def _send_dir_marker(dest_mac: str, relpath: str) -> None:
    """
    Envía un marcador DIR:<relpath>|0 como FILE_START para que el receptor cree directorios.
    """
    file_id = new_file_id()
    meta = f"DIR:{relpath}|0".encode("utf-8")
    pkt = build_header(FILE_START, meta, channel=FILE_CHANNEL, seq=0, file_id=file_id)
    send_frame(dest_mac, pkt)
    # opcional: enviar FILE_END breve para "cerrar" marker
    pkt_end = build_header(FILE_END, b"", channel=FILE_CHANNEL, seq=0, file_id=file_id)
    send_frame(dest_mac, pkt_end)


def send_folder(
    dest_mac: str,
    folder_path: str,
    *,
    use_ack: bool = True,
    retries: int = 5,
    timeout: float = 1.0,
) -> None:
    """
    Envía una carpeta recursivamente:
      - envía marker para carpeta raíz y subcarpetas (DIR:...)
      - envía cada archivo con remote_name relativo a la raíz (e.g. "miCarpeta/sub/archivo.txt")
    """
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(folder_path)

    folder_path = os.path.abspath(folder_path)
    base = os.path.basename(folder_path.rstrip("/"))

    # enviar marker para la carpeta raíz
    _send_dir_marker(dest_mac, base)

    for root, dirs, files in os.walk(folder_path):
        rel_root = os.path.relpath(root, folder_path)
        if rel_root == ".":
            rel_dir = base
        else:
            rel_dir = os.path.join(base, rel_root)

        # crear marcadores para subdirectorios
        for d in dirs:
            relpath = os.path.join(rel_dir, d).replace(os.path.sep, "/")
            _send_dir_marker(dest_mac, relpath)

        # enviar archivos
        for f in files:
            abs_path = os.path.join(root, f)
            remote_rel = os.path.join(rel_dir, f).replace(os.path.sep, "/")
            send_file(
                dest_mac,
                abs_path,
                use_ack=use_ack,
                retries=retries,
                timeout=timeout,
                remote_name=remote_rel,
            )
