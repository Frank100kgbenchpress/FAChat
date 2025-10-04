from ethernet import recv_one
import hashlib
import struct

OUTFILE = "recv_prueba.txt"

def main():
    print("Esperando archivo...")

    # 1. recibir tamaño
    src, payload = recv_one()
    filesize = struct.unpack("!Q", payload[:8])[0]
    print(f"[receiver] Tamaño esperado: {filesize} bytes")

    # 2. recibir datos hasta llegar al tamaño
    received = 0
    with open(OUTFILE, "wb") as f:
        while received < filesize:
            src, payload = recv_one()
            f.write(payload)
            received += len(payload)
            print(f"[receiver] Progreso: {received}/{filesize} bytes", end="\r")

    # calcular hash
    with open(OUTFILE, "rb") as f:
        data = f.read()
    sha256 = hashlib.sha256(data).hexdigest()

    print(f"\n[receiver] Archivo recibido y guardado en {OUTFILE}")
    print(f"[receiver] SHA256: {sha256}")
    print(f"[receiver] Tamaño final: {len(data)} bytes")

if __name__ == "__main__":
    main()
