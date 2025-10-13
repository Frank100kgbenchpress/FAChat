from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
import threading
import uuid
import os
import sys
import time

# 🔹 Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

print("=" * 50, flush=True)
print("🚀 INICIANDO FACHAT APPLICATION", flush=True)
print("=" * 50, flush=True)

from network_manager import NetworkManager
from ethernet import get_interface_mac, INTERFACE

app = Flask(__name__)
app.secret_key = "temp_key_initial"

network_manager = NetworkManager()
chat_messages = network_manager.chat_messages

# 🔹 Obtener MAC: primero env var, si no existe, la interfaz física
mac_env = os.getenv("MY_MAC")
print(f"[INIT] MY_MAC env var: {mac_env}", flush=True)

# if mac_env:
#     CONTAINER_MAC = mac_env
#     print(f"[INIT] Usando MAC de variable de entorno: {CONTAINER_MAC}", flush=True)
# else:
try:
    print(f"[INIT] Intentando obtener MAC de interfaz: {INTERFACE}", flush=True)
    mac_bytes = get_interface_mac(INTERFACE)
    CONTAINER_MAC = ":".join(f"{b:02x}" for b in mac_bytes)
    print(f"[INIT] MAC obtenida de interfaz: {CONTAINER_MAC}", flush=True)
except Exception as e:
    CONTAINER_MAC = "00:00:00:00:00:00"
    print(f"[INIT] ⚠️ Error obteniendo MAC: {e}", flush=True)

print(f"[INIT] MAC final del contenedor: {CONTAINER_MAC}", flush=True)


@app.route("/", methods=["GET", "POST"])
def login():
    print(f"[LOGIN] Método: {request.method}", flush=True)

    if request.method == "POST":
        username = request.form.get("username")
        print(
            f"[LOGIN] Usuario intentando login: {username}, {CONTAINER_MAC}", flush=True
        )

        if username:
            session["username"] = username
            session["mac"] = CONTAINER_MAC
            app.secret_key = f"secret_key_{CONTAINER_MAC.replace(':', '')}"

            print(
                f"[LOGIN] ✅ Login exitoso - Usuario: {username}, MAC: {CONTAINER_MAC}",
                flush=True,
            )

            # Lanzar NetworkManager en hilo aparte
            def start_network():
                try:
                    print("[NetworkManager] Iniciando en thread...", flush=True)
                    network_manager.start(CONTAINER_MAC)
                    print("[NetworkManager] ✅ Iniciado correctamente", flush=True)
                except Exception as e:
                    print(f"[NetworkManager] ❌ Error al iniciar: {e}", flush=True)
                    import traceback

                    traceback.print_exc()

            thread = threading.Thread(target=start_network, daemon=True)
            thread.start()
            print("[LOGIN] Thread de NetworkManager lanzado", flush=True)

            return redirect(url_for("chat"))

    print("[LOGIN] Mostrando página de login", flush=True)
    return render_template("login.html")


@app.route("/chat")
def chat():
    print("[CHAT] Acceso a página de chat", flush=True)
    if "username" not in session or "mac" not in session:
        print("[CHAT] ⚠️ Sesión no válida, redirigiendo a login", flush=True)
        return redirect(url_for("login"))

    print(f"[CHAT] Usuario: {session['username']}, MAC: {session['mac']}", flush=True)
    return render_template(
        "index.html",
        username=session["username"],
        mac=session["mac"],
    )


@app.route("/get_users")
def get_users():
    users = network_manager.get_peers_for_flask()
    print(f"[API] get_users - Retornando {len(users)} usuarios", flush=True)
    return jsonify(users)


@app.route("/get_messages/<other_mac>")
def get_messages(other_mac):
    my_mac = session.get("mac")
    if not my_mac:
        return jsonify([])
    chat_id = "-".join(sorted([my_mac, other_mac]))
    messages = chat_messages.get(chat_id, [])
    print(f"[API] get_messages - Chat {chat_id}: {len(messages)} mensajes", flush=True)
    return jsonify(messages)


@app.route("/send_message", methods=["POST"])
def send_message():
    mac_bytes = get_interface_mac(INTERFACE)
    CONTAINER_MAC = ":".join(f"{b:02x}" for b in mac_bytes)
    print(f"send_message {CONTAINER_MAC}")
    my_mac = session.get("mac", CONTAINER_MAC)
    data = request.json
    other_mac = data.get("other_mac")
    message_text = data.get("message")

    print(
        f"[API] send_message - De: {my_mac}, Para: {other_mac}, Msg: {message_text[:50]}...",
        flush=True,
    )

    if not my_mac or not other_mac or not message_text:
        print("[API] ⚠️ send_message - Datos incompletos", flush=True)
        return jsonify({"success": False})

    try:
        network_manager.send_chat_message(other_mac, message_text)
        chat_id = "-".join(sorted([my_mac, other_mac]))
        if chat_id not in chat_messages:
            chat_messages[chat_id] = []
        new_message = {
            "id": str(uuid.uuid4()),
            "sender": my_mac,
            "text": message_text,
            "timestamp": datetime.now().strftime("%H:%M"),
        }
        chat_messages[chat_id].append(new_message)
        print("[API] ✅ Mensaje enviado correctamente", flush=True)
        return jsonify({"success": True})
    except Exception as e:
        print(f"[API] ❌ Error enviando mensaje: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route("/send_file", methods=["POST"])
def send_file():
    my_mac = session.get("mac")
    data = request.json
    other_mac = data.get("other_mac")
    file_path = data.get("file_path")

    print(
        f"[API] send_file - De: {my_mac}, Para: {other_mac}, File: {file_path}",
        flush=True,
    )

    if not my_mac or not other_mac or not file_path:
        return jsonify({"success": False})

    try:
        network_manager.send_file(other_mac, file_path)
        chat_id = "-".join(sorted([my_mac, other_mac]))
        if chat_id not in chat_messages:
            chat_messages[chat_id] = []
        file_message = {
            "id": str(uuid.uuid4()),
            "sender": my_mac,
            "text": f"[ARCHIVO]{file_path}",
            "timestamp": datetime.now().strftime("%H:%M"),
        }
        chat_messages[chat_id].append(file_message)
        print("[API] ✅ Archivo enviado correctamente", flush=True)
        return jsonify({"success": True})
    except Exception as e:
        print(f"[API] ❌ Error enviando archivo: {e}", flush=True)
        return jsonify({"success": False, "error": str(e)})


@app.route("/logout")
def logout():
    print(f"[LOGOUT] Usuario cerrando sesión: {session.get('username')}", flush=True)
    try:
        network_manager.stop()
    except Exception:
        pass
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[INIT] 🌐 Iniciando servidor Flask en puerto {port}", flush=True)
    print("[INIT] 🔧 Debug mode: True", flush=True)
    print("[INIT] 📡 Host: 0.0.0.0", flush=True)
    app.run(debug=True, host="0.0.0.0", port=port, use_reloader=False)
