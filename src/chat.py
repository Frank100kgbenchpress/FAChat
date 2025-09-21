"""
chat.py - Chat de consola integrado con ethernet.py

Uso:
sudo python3 src/chat.py

Asegúrate de ajustar INTERFACE en src/ethernet.py.
"""
import threading
from ethernet import send_frame, start_recv_loop, stop_recv_loop
import sys

# Para pruebas locales en la misma máquina usaremos broadcast:
DEST_MAC = "ff:ff:ff:ff:ff:ff"

# Lock para evitar que input() y prints concurrentes se mezclen en consola
_print_lock = threading.Lock()


def on_packet(src_mac, payload):
    """Callback seguro que imprime mensajes recibidos sin romper el prompt."""
    try:
        msg = payload.decode('utf-8', errors='replace')
    except Exception:
        msg = repr(payload)

    with _print_lock:
        # imprimimos la línea del peer y volvemos a mostrar el prompt
        print(f"\n[{src_mac}] {msg}")
        # reimprime prompt si el main thread está esperando input
        sys.stdout.write("Tú: ")
        sys.stdout.flush()


def start_chat():
    print("=== LinkChat iniciado === (escribe /exit para salir)")
    start_recv_loop(on_packet)

    try:
        while True:
            # Entrada del usuario
            text = input("Tú: ")
            # enviar (broadcast por defecto)
            send_frame(DEST_MAC, text.encode())
            if text == "/exit":
                # avisar al peer y salir
                break
    except KeyboardInterrupt:
        # manejo ctrl+c
        pass
    finally:
        stop_recv_loop()
        print("\nChat terminado.")


if __name__ == "__main__":
    start_chat()
