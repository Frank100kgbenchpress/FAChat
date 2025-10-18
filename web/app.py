import tempfile
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    jsonify,
    send_file,
)
from datetime import datetime
from werkzeug.utils import secure_filename
import threading
import uuid
import os
import sys
import time
from network_manager import NetworkManager
import secrets

# 🔹 Agregar src al path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

print("=" * 50, flush=True)
print("🚀 INICIANDO FACHAT APPLICATION", flush=True)
print("=" * 50, flush=True)


def get_secret_path():
    # Obtener la ruta raíz del proyecto
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    secret_folder = os.path.join(base_path, "secret_keys")
    if not os.path.exists(secret_folder):
        os.makedirs(secret_folder)
    return os.path.join(secret_folder, "secret_key.txt")


def get_or_create_secret():
    """Obtiene o crea la clave secreta para Flask"""
    secret_path = get_secret_path()
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()  # Leer y devolver la clave si existe
    key = secrets.token_hex(32)  # Si no existe, crear una nueva clave
    with open(secret_path, "w") as f:
        f.write(key)  # Guardar la clave generada en el archivo
    print(f"[INIT] 🔐 Nueva SECRET_KEY generada en {secret_path}", flush=True)
    return key


def create_app():
    app = Flask(__name__)
    app.secret_key = get_or_create_secret()
    app.config["SESSION_COOKIE_NAME"] = os.environ.get(
        "SESSION_COOKIE_NAME", "session_app"
    )
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
    return app


from ethernet import get_interface_mac, INTERFACE

app = create_app()

# Usar carpeta temporal del sistema
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
# 🔹 Crear carpetas de archivos enviados y recibidos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEND_DIR = os.path.join(BASE_DIR, "send_files")
RECV_DIR = os.path.join(BASE_DIR, "recv_files")

for folder in ["send_files", "recv_files"]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"[INIT] 📁 Carpeta creada: {folder}", flush=True)

app.config["MAX_CONTENT_LENGTH"] = 1000 * 1024 * 1024

network_manager = NetworkManager(RECV_DIR)
chat_messages = network_manager.chat_messages

no_login = False

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


def allowed_file(filename):
    """Verifica si la extensión del archivo está permitida"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
            # app.secret_key = f"secret_key_{CONTAINER_MAC.replace(':', '')}"

            print(
                f"[LOGIN] ✅ Login exitoso - Usuario: {username}, MAC: {CONTAINER_MAC}",
                flush=True,
            )

            global no_login
            no_login = True
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
    global no_login
    if not no_login:
        no_login = True
        thread = threading.Thread(target=start_network, daemon=True)
        thread.start()
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
    my_mac = session.get("mac")
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


@app.route("/upload_file", methods=["POST"])
def upload_file():
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
        # Guardar archivo en la carpeta de enviados
        file_id = str(uuid.uuid4())
        save_path = os.path.join(SEND_DIR, f"{file_id}_{filename}")
        file.save(save_path)
        print(f"[send_file] 📤 Archivo guardado en enviados: {save_path}", flush=True)

        # Verificar que el archivo se guardó correctamente
        if not os.path.exists(save_path):
            return jsonify(
                {"success": False, "error": "Error al guardar archivo temporal"}
            ), 500

        file_size = os.path.getsize(save_path)
        print(
            f"[send_file] Archivo guardado: {filename} ({file_size} bytes)", flush=True
        )

        # Enviar archivo por red
        print(f"[send_file] Enviando archivo a {other_mac}...", flush=True)
        network_manager.send_file(other_mac, save_path)
        print("[send_file] ✅ Archivo enviado correctamente", flush=True)

        # Guardar referencia en chat_messages
        chat_id = "-".join(sorted([my_mac, other_mac]))
        if chat_id not in chat_messages:
            chat_messages[chat_id] = []

        file_message = {
            "id": str(uuid.uuid4()),
            "sender": my_mac,
            "text": f"[ARCHIVO]{filename}",
            "filename": filename,
            "file_path": save_path,  # 🔹 agregar ruta real
            "timestamp": datetime.now().strftime("%H:%M"),
            "type": "file",
        }

        chat_messages[chat_id].append(file_message)

        # # Limpiar archivo temporal
        # try:
        #     os.remove(temp_path)
        #     print(f"[send_file] Archivo temporal eliminado: {temp_path}", flush=True)
        # except Exception as e:
        #     print(
        #         f"[send_file] ⚠️ No se pudo eliminar archivo temporal: {e}", flush=True
        #     )

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
            if "temp_path" in locals() and os.path.exists(save_path):
                os.remove(save_path)
        except Exception:
            pass

        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/logout")
def logout():
    print(f"[LOGOUT] Usuario cerrando sesión: {session.get('username')}", flush=True)
    try:
        network_manager.stop()
    except Exception:
        pass
    session.clear()
    return redirect(url_for("login"))


@app.route("/download_file/<file_id>")
def download_file(file_id):
    """Descargar archivo real según su ID almacenado"""
    try:
        print(f"[DOWNLOAD] Solicitado archivo con ID: {file_id}", flush=True)

        # Buscar el mensaje que tenga este ID
        for chat_id, messages in network_manager.chat_messages.items():
            for message in messages:
                if message.get("id") == file_id and (
                    message.get("type") == "file"
                    or message.get("text", "").startswith("[ARCHIVO]")
                ):
                    file_path = message.get("file_path")
                    filename = message.get("filename", "archivo_descargado")

                    if not file_path or not os.path.exists(file_path):
                        print(
                            f"[DOWNLOAD] ❌ Archivo no encontrado en disco: {file_path}",
                            flush=True,
                        )
                        return "Archivo no encontrado", 404

                    print(
                        f"[DOWNLOAD] ✅ Enviando archivo real: {file_path}", flush=True
                    )

                    # 🔹 Usa send_file en modo binario con el nombre correcto
                    return send_file(
                        file_path,
                        as_attachment=True,
                        download_name=filename,
                        mimetype="application/octet-stream",
                    )

        print(f"[DOWNLOAD] ❌ Mensaje con ID {file_id} no encontrado", flush=True)
        return "Mensaje no encontrado", 404

    except Exception as e:
        print(f"[DOWNLOAD] ❌ Error al descargar: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return "Error al descargar archivo", 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[INIT] 🌐 Iniciando servidor Flask en puerto {port}", flush=True)
    print("[INIT] 🔧 Debug mode: True", flush=True)
    print("[INIT] 📡 Host: 0.0.0.0", flush=True)
    app.run(debug=True, host="0.0.0.0", port=port, use_reloader=False)
