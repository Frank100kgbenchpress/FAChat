# src/chat.py
from protocol import send_message, start_message_listener, stop_message_listener

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
            send_message(text)
    except KeyboardInterrupt:
        pass
    finally:
        stop_message_listener()
        print("\n[chat] Chat terminado.")
