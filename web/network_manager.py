from datetime import datetime
import threading
import time
from typing import Dict, List, Callable, Optional
import os
import uuid


class NetworkManager:
    def __init__(self):
        self.peers: Dict[str, Dict] = {}
        self.my_mac = None
        self.on_peers_updated: Optional[Callable] = None
        self.running = False
        self.chat_messages = {}
        self._import_backend_modules()

    def _import_backend_modules(self):
        try:
            import sys

            sys.path.append("/app/src")

            from messaging import discover_peers, send_message, start_message_loop
            from files import send_file, start_file_loop, stop_file_loop
            from ethernet import send_frame, start_recv_loop, stop_recv_loop

            self.backend = {
                "discover_peers": discover_peers,
                "send_message": send_message,
                "send_file": send_file,
                "start_file_loop": start_file_loop,
                "stop_file_loop": stop_file_loop,
                "send_frame": send_frame,
                "start_recv_loop": start_recv_loop,
                "stop_recv_loop": stop_recv_loop,
                "start_message_loop": start_message_loop,
            }
            self.backend_available = True
        except ImportError as e:
            print(f"Backend modules not available: {e}")
            self.backend_available = False
            self.backend = {}

    def rec_messages(self, other_mac: str, message_text: str) -> None:
        DISCOVER_REQ = "__LINKCHAT_DISCOVER_REQ__"
        DISCOVER_REPLY_PREFIX = "__LINKCHAT_DISCOVER_RPLY__|"
        print(
            f"Recibiendo mensaje de {other_mac} a {self.my_mac} con el mensaje {message_text}"
        )

        if (
            other_mac == self.my_mac
            or message_text.startswith(DISCOVER_REPLY_PREFIX)
            or message_text.startswith(DISCOVER_REQ)
            or other_mac == "ff:ff:ff:ff:ff:ff"
        ):
            return
        chat_id = "-".join(sorted([self.my_mac, other_mac]))
        if chat_id not in self.chat_messages:
            self.chat_messages[chat_id] = []
        new_message = {
            "id": str(uuid.uuid4()),
            "sender": other_mac,
            "text": message_text,
            "timestamp": datetime.now().strftime("%H:%M"),
        }
        self.chat_messages[chat_id].append(new_message)

    def rec_file(self, src_mac: str, file_path: str, status: str) -> None:
        # Maneja la recepción de archivos, similar a rec_messages
        print(f"Recibiendo archivo de {src_mac} en {file_path} con estado {status}")

        # Solo procesar cuando el archivo se completa
        if status == "completed" or status == "finished":
            # Extraer nombre del archivo sin el prefijo "recv_"
            filename = os.path.basename(file_path)
            display_name = filename.replace("recv_", "", 1)

            chat_id = "-".join(sorted([self.my_mac, src_mac]))
            if chat_id not in self.chat_messages:
                self.chat_messages[chat_id] = []

            file_message = {
                "id": str(uuid.uuid4()),
                "sender": src_mac,
                "text": f"[ARCHIVO]{display_name}",
                "file_path": file_path,
                "filename": display_name,
                "timestamp": datetime.now().strftime("%H:%M"),
                "type": "file",
            }
            self.chat_messages[chat_id].append(file_message)
            print(f"✅ Mensaje de archivo añadido al chat: {display_name}")

    def start(self, my_mac: str):
        print(f"Starting NetworkManager with MAC: {my_mac}")

        if not self.backend_available:
            print("Backend not available - running in demo mode")
            self._start_demo_mode()
            return

        self.my_mac = my_mac
        self.running = True
        self._start_discovery_polling()
        self.backend["start_message_loop"](self.rec_messages)
        self._start_file_receiver()
        print(f"NetworkManager iniciado para MAC: {my_mac}")

    def stop(self):
        self.running = False
        if self.backend_available:
            self.backend["stop_recv_loop"]()
            self.backend["stop_file_loop"]()

    def _start_discovery_polling(self):
        def discovery_loop():
            while self.running:
                try:
                    # discovery real o simulado
                    if self.backend_available:
                        discovered = self.backend["discover_peers"](timeout=1.0)
                    else:
                        # demo discovery usando env var PEERS
                        discovered_peers = os.getenv("PEERS", "")
                        discovered = []
                        for peer_info in discovered_peers.split(","):
                            if not peer_info.strip():
                                continue
                            name, mac = peer_info.split(":")
                            discovered.append((mac.strip(), name.strip()))

                    for mac, name in discovered:
                        if mac not in self.peers:
                            self.peers[mac] = {
                                "name": name,
                                "status": "online",
                                "last_seen": time.time(),
                            }
                        else:
                            self.peers[mac]["last_seen"] = time.time()

                    # limpiar peers antiguos
                    current_time = time.time()
                    for mac in list(self.peers.keys()):
                        if current_time - self.peers[mac].get("last_seen", 0) > 10:
                            del self.peers[mac]

                    if self.on_peers_updated:
                        self.on_peers_updated()

                except Exception as e:
                    print(f"Error en discovery: {e}")

                time.sleep(3)

        thread = threading.Thread(target=discovery_loop, daemon=True)
        thread.start()

    def _start_file_receiver(self):
        def file_callback(src_mac: str, path: str, status: str):
            self.rec_file(src_mac, path, status)

        if self.backend_available:
            self.backend["start_file_loop"](file_callback)

    def send_chat_message(self, dest_mac: str, message: str):
        if not self.backend_available:
            raise RuntimeError("Backend no disponible")
        self.backend["send_message"](dest_mac, message)

    def send_file(self, dest_mac: str, file_path: str):
        if not self.backend_available:
            raise RuntimeError("Backend no disponible")
        self.backend["send_file"](dest_mac, file_path)

    def get_peers_for_flask(self) -> List[Dict]:
        result = []
        for mac, data in self.peers.items():
            result.append(
                {
                    "mac": mac,
                    "name": data.get("name", f"User_{mac[-6:]}"),
                    "status": data.get("status", "offline"),
                }
            )
        return result

    def _start_demo_mode(self):
        self.running = True
        print("Running in demo mode - no real network communication")

        def demo_loop():
            while self.running:
                # agregar peers de env var PEERS
                peers_env = os.getenv("PEERS", "")
                for peer_info in peers_env.split(","):
                    if not peer_info.strip():
                        continue
                    name, mac = peer_info.split(":")
                    if mac not in self.peers:
                        self.peers[mac] = {
                            "name": name.strip(),
                            "status": "online",
                            "last_seen": time.time(),
                        }
                if self.on_peers_updated:
                    self.on_peers_updated()
                time.sleep(5)

        thread = threading.Thread(target=demo_loop, daemon=True)
        thread.start()
