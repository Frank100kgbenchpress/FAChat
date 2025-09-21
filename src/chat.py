# src/chat.py
from ethernet import send_frame, start_recv_loop, stop_recv_loop
import sys

# Para pruebas locales en la misma máquina usaremos broadcast:
DEST_MAC = "ff:ff:ff:ff:ff:ff"

def on_packet(src_mac, payload):
    try:
        msg = payload.decode('utf-8', errors='ignore')
    except Exception:
        msg = str(payload)
    # mostrar en pantalla limpiamente
    print(f"\n[{src_mac}] {msg}\nTú: ", end="", flush=True)

def start_chat():
    print("=== LinkChat iniciado === (escribe /exit para salir)")
    start_recv_loop(on_packet)

    try:
        while True:
            text = input("Tú: ")
            send_frame(DEST_MAC, text.encode())
            if text == "/exit":
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_recv_loop()
        print("\nChat terminado.")

if __name__ == "__main__":
    start_chat()
