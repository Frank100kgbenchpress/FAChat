import sys
import os
import struct
from ethernet import send_frame

# Broadcast para pruebas
DEST_MAC = "ff:ff:ff:ff:ff:ff"

def main():
    if len(sys.argv) != 2:
        print("Uso: sudo python3 send_file.py <archivo>")
        return

    path = sys.argv[1]
    try:
        filesize = os.path.getsize(path)
        print(f"[sender] Enviando '{path}' ({filesize} bytes)...")

        # 1. enviar tamaño (8 bytes, unsigned long long big-endian)
        send_frame(DEST_MAC, struct.pack("!Q", filesize))

        # 2. enviar bloques de datos
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                send_frame(DEST_MAC, chunk)

        print(f"[sender] Archivo '{path}' enviado correctamente.")
    except Exception as e:
        print(f"[sender] Error enviando archivo: {e}")

if __name__ == "__main__":
    main()
