#!/usr/bin/env python3
# scripts/test_recv_file.py
"""
Receptor bloqueante para pruebas de files.py
Ejecutar en la máquina que recibe:
sudo python3 scripts/test_recv_file.py
"""
import os
import hashlib
from files import receive_file_blocking

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()

def main():
    print("Esperando a recibir un archivo... (esto bloqueará hasta que termine una transferencia)")
    src, path = receive_file_blocking()
    if not src or not path:
        print("No se recibió archivo o hubo un error.")
        return
    print(f"Transferencia completada desde {src}. Archivo guardado en: {path}")
    try:
        print("SHA256 del archivo recibido:", sha256_file(path))
        print("Tamaño:", os.path.getsize(path), "bytes")
    except Exception as e:
        print("No se pudo calcular hash/tamaño:", e)

if __name__ == "__main__":
    main()
