# recv_debug_filtered.py
import socket
import struct
import time

# AJUSTA ESTO:
INTERFACE = "wlp2s0"     # tu interfaz (ver `ip a`)
ETH_TYPE_INT = 0x1234    # EtherType que usamos para LinkChat

def is_printable(b: bytes) -> bool:
    try:
        txt = b.decode('utf-8')
    except Exception:
        return False
    # permitimos imprimir si la mayoría son caracteres imprimibles
    printable_ratio = sum(1 for ch in txt if ch.isprintable()) / max(1, len(txt))
    return printable_ratio > 0.6

def main():
    # Intentamos que el socket lo filtre a nivel kernel por ethertype
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_TYPE_INT))
    s.bind((INTERFACE, 0))
    print(f"[recv_filtered] escuchando EN {INTERFACE} - filtrando EtherType {hex(ETH_TYPE_INT)}")
    print("Presiona Ctrl+C para salir.\n")

    try:
        while True:
            raw, _ = s.recvfrom(65535)
            # parsear
            eth_type = struct.unpack("!H", raw[12:14])[0]
            src = ":".join(f"{b:02x}" for b in raw[6:12])
            payload = raw[14:]
            # Solo debería llegar nuestro eth_type (pero chequeamos por si acaso)
            if eth_type != ETH_TYPE_INT:
                continue

            # Mostrar de forma legible
            if is_printable(payload) and len(payload) > 0:
                try:
                    msg = payload.decode('utf-8', errors='replace')
                    print(f"[{time.strftime('%H:%M:%S')}] {src} -> {msg}")
                except Exception:
                    print(f"[{time.strftime('%H:%M:%S')}] {src} -> <imposible decodificar>")
            else:
                # payload no textual: mostrar hexdump corto
                hexd = payload[:60].hex()
                print(f"[{time.strftime('%H:%M:%S')}] {src} -> (binario) {hexd}... (len={len(payload)})")
    except KeyboardInterrupt:
        print("\n[recv_filtered] detenido por usuario")
    finally:
        s.close()

if __name__ == "__main__":
    main()
