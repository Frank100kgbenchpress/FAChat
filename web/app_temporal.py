from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
from werkzeug.utils import secure_filename
import threading
import uuid
import os
import sys
import tempfile

# 🔹 Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from network_manager import NetworkManager
from ethernet import get_interface_mac, INTERFACE

app = Flask(__name__)
app.secret_key = "temp_key_initial"

# Configuración para subida de archivos
UPLOAD_FOLDER = tempfile.gettempdir()  # Usar carpeta temporal del sistema
ALLOWED_EXTENSIONS = set(
    [
        "txt",
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "gif",
        "doc",
        "docx",
        "zip",
        "rar",
        "mp4",
        "mp3",
    ]
)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB máximo

network_manager = NetworkManager()
chat_messages = {}

# 🔹 Obtener MAC: primero env var, si no existe, la interfaz física
mac_env = os.getenv("MY_MAC")
if mac_env:
    CONTAINER_MAC = mac_env
else:
    try:
        mac_bytes = get_interface_mac(INTERFACE)
        CONTAINER_MAC = ":".join(f"{b:02x}" for b in mac_bytes)
    except Exception as e:
        CONTAINER_MAC = "00:00:00:00:00:00"
        print(f"Error obteniendo MAC: {e}")


def allowed_file(filename):
    """Verifica si la extensión del archivo está permitida"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        if username:
            session["username"] = username
            session["mac"] = CONTAINER_MAC
            app.secret_key = f"secret_key_{CONTAINER_MAC.replace(':', '')}"

            # Lanzar NetworkManager en hilo aparte
            def start_network():
                try:
                    network_manager.start(CONTAINER_MAC)
                except Exception as e:
                    print(f"[NetworkManager] Error al iniciar: {e}")

            threading.Thread(target=start_network, daemon=True).start()

            return redirect(url_for("chat"))
    return render_template("login.html")


@app.route("/chat")
def chat():
    if "username" not in session or "mac" not in session:
        return redirect(url_for("login"))
    return render_template(
        "index.html",
        username=session["username"],
        mac=session["mac"],
    )


@app.route("/get_users")
def get_users():
    return jsonify(network_manager.get_peers_for_flask())


@app.route("/get_messages/<other_mac>")
def get_messages(other_mac):
    my_mac = session.get("mac")
    if not my_mac:
        return jsonify([])
    chat_id = "-".join(sorted([my_mac, other_mac]))
    return jsonify(chat_messages.get(chat_id, []))


@app.route("/send_message", methods=["POST"])
def send_message():
    my_mac = session.get("mac")
    data = request.json
    other_mac = data.get("other_mac")
    message_text = data.get("message")

    if not my_mac or not other_mac or not message_text:
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
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/send_file", methods=["POST"])
def send_file():
    """
    Endpoint CORREGIDO para recibir y enviar archivos.
    Recibe el archivo real vía FormData, lo guarda temporalmente,
    lo envía por red y luego lo elimina.
    """
    my_mac = session.get("mac")

    # Validar sesión
    if not my_mac:
        return jsonify({"success": False, "error": "Sesión no válida"}), 401

    # Obtener datos del formulario
    other_mac = request.form.get("other_mac")

    # Verificar que el archivo esté en la petición
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No se encontró el archivo"}), 400

    file = request.files["file"]

    # Verificar que se seleccionó un archivo
    if file.filename == "":
        return jsonify(
            {"success": False, "error": "No se seleccionó ningún archivo"}
        ), 400

    # Validar datos requeridos
    if not other_mac:
        return jsonify(
            {"success": False, "error": "MAC de destino no especificada"}
        ), 400

    try:
        # Guardar archivo temporalmente con nombre seguro
        filename = secure_filename(file.filename)
        temp_path = os.path.join(
            app.config["UPLOAD_FOLDER"], f"{uuid.uuid4()}_{filename}"
        )

        print(f"[send_file] Guardando archivo temporal: {temp_path}", flush=True)
        file.save(temp_path)

        # Verificar que el archivo se guardó correctamente
        if not os.path.exists(temp_path):
            return jsonify(
                {"success": False, "error": "Error al guardar archivo temporal"}
            ), 500

        file_size = os.path.getsize(temp_path)
        print(
            f"[send_file] Archivo guardado: {filename} ({file_size} bytes)", flush=True
        )

        # Enviar archivo por red
        print(f"[send_file] Enviando archivo a {other_mac}...", flush=True)
        network_manager.send_file(other_mac, temp_path)
        print("[send_file] ✅ Archivo enviado correctamente", flush=True)

        # Guardar referencia en chat_messages
        chat_id = "-".join(sorted([my_mac, other_mac]))
        if chat_id not in chat_messages:
            chat_messages[chat_id] = []

        file_message = {
            "id": str(uuid.uuid4()),
            "sender": my_mac,
            "text": f"[ARCHIVO]{filename}",
            "timestamp": datetime.now().strftime("%H:%M"),
        }
        chat_messages[chat_id].append(file_message)

        # Limpiar archivo temporal
        try:
            os.remove(temp_path)
            print(f"[send_file] Archivo temporal eliminado: {temp_path}", flush=True)
        except Exception as e:
            print(
                f"[send_file] ⚠️ No se pudo eliminar archivo temporal: {e}", flush=True
            )

        return jsonify({"success": True, "filename": filename})

    except FileNotFoundError as e:
        print(f"[send_file] ❌ Archivo no encontrado: {e}", flush=True)
        return jsonify(
            {"success": False, "error": f"Archivo no encontrado: {str(e)}"}
        ), 404

    except Exception as e:
        print(f"[send_file] ❌ Error enviando archivo: {e}", flush=True)
        import traceback

        traceback.print_exc()

        # Intentar limpiar archivo temporal en caso de error
        try:
            if "temp_path" in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/logout")
def logout():
    try:
        network_manager.stop()
    except Exception:
        pass
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=port)
