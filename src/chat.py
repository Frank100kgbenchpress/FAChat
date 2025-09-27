# src/chat.py
"""
chat.py - Chat de consola que usa messaging.py (protocolo).
sudo python3 src/chat.py
"""
import threading
import sys
from messaging import send_message, start_message_loop, stop_message_loop

DEST_MAC = "ff:ff:ff:ff:ff:ff"
_print_lock = threading.Lock()

def on_message(src_mac, text):
    with _print_lock:
        print(f"\n[{src_mac}] {text}")
        sys.stdout.write("Tú: ")
        sys.stdout.flush()

def start_chat():
    print("=== LinkChat (protocolo) iniciado === (escribe /exit para salir)")
    start_message_loop(on_message)
    try:
        while True:
            text = input("Tú: ")
            send_message(DEST_MAC, text)
            if text == "/exit":
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop_message_loop()
        print("\nChat terminado.")

if __name__ == "__main__":
    start_chat()
