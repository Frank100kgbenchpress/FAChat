import chat
import file_transfer

def main():
    while True:
        print("1. Chat")
        print("2. Transferencia de archivos")
        print("3. Salir")
        op = input("Elige opción: ")
        if op == "1":
            chat.start_chat()
        elif op == "2":
            file_transfer.start_transfer()
        elif op == "3":
            break

if __name__ == "__main__":
    main()
