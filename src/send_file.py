#!/usr/bin/env python3
# scripts/test_send_file.py
"""
Emisor para pruebas de files.py
Uso:
sudo python3 scripts/test_send_file.py /ruta/al/archivo [dest_mac]

- Si dest_mac no se indica, usa broadcast ff:ff:ff:ff:ff:ff (útil para pruebas en la misma máquina).
"""
import sys
import os
import hashlib
from files import send_file

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()

def main():
    if len(sys.argv) < 2:
        print("Uso: sudo python3 scripts/test_send_file.py /ruta/al/archivo [dest_mac]")
        sys.exit(1)
    path = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) >= 3 else "ff:ff:ff:ff:ff:ff"
    if not os.path.isfile(path):
        print("Archivo no encontrado:", path)
        sys.exit(1)
    print("Archivo a enviar:", path)
    print("Tamaño:", os.path.getsize(path), "bytes")
    print("SHA256:", sha256_file(path))
    print("Enviando a", dest, "con ACKs (stop-and-wait)...")
    try:
        send_file(dest, path, use_ack=True, retries=5, timeout=1.0)
        print("Envío completado (se envió FILE_END).")
    except Exception as e:
        print("Error durante el envío:", e)

if __name__ == "__main__":
    main()
