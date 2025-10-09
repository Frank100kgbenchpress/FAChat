# src/chat.py
from protocol import send_message, start_message_listener, stop_message_listener
from messaging import send_message_to_all

def chat_mode():
    print("=== Modo Chat === (escribe /exit para salir)")
    def on_msg(src, msg):
        print(f"\n[{src}] {msg}\nTú: ", end="", flush=True)

    start_message_listener(on_msg)
    try:
        while True:
            text = input("Tú: ")
            if text == "/exit":
                break
            # enviar a todos: /all mensaje  OR /all (pedir mensaje)
            if text.startswith("/all"):
                rest = text[4:].strip()
                if not rest:
                    rest = input("Mensaje para todos: ").strip()
                if rest:
                    sent = send_message_to_all(rest)
                    print(f"[chat] enviado a {len(sent)} peers")
                continue
            send_message(text)
    except KeyboardInterrupt:
        pass
    finally:
        stop_message_listener()
        print("\n[chat] Chat terminado.")
