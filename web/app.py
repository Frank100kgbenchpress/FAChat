from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = "tu_clave_secreta_aqui"

# Estructura mejorada de datos
users_example = [
    {"mac": "00:11:22:33:44:55", "name": "", "status": "online", "listening": True},
    {"mac": "AA:BB:CC:DD:EE:FF", "name": "", "status": "offline", "listening": False},
    {"mac": "11:22:33:44:55:66", "name": "", "status": "online", "listening": True},
]

# Almacenamiento de mensajes por conversación
# Estructura: { "mac_usuario1-mac_usuario2": [mensajes] }
chat_messages = {}


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        mac = request.form.get("mac")
        if username and mac:
            session["username"] = username
            session["mac"] = mac
            return redirect(url_for("chat"))
    return render_template("login.html")


@app.route("/chat")
def chat():
    if "username" not in session or "mac" not in session:
        return redirect(url_for("login"))
    return render_template(
        "index.html",
        users=users_example,
        username=session["username"],
        mac=session["mac"],
    )


@app.route("/get_users")
def get_users():
    return jsonify(users_example)


@app.route("/get_messages/<other_mac>")
def get_messages(other_mac):
    my_mac = session.get("mac")
    if not my_mac:
        return jsonify([])

    # Crear ID único para la conversación (ordenado alfabéticamente)
    chat_id = "-".join(sorted([my_mac, other_mac]))

    # Devolver mensajes o lista vacía si no existen
    return jsonify(chat_messages.get(chat_id, []))


@app.route("/send_message", methods=["POST"])
def send_message():
    my_mac = session.get("mac")
    data = request.json
    other_mac = data.get("other_mac")
    message_text = data.get("message")

    if not my_mac or not other_mac or not message_text:
        return jsonify({"success": False})

    # Crear ID único para la conversación
    chat_id = "-".join(sorted([my_mac, other_mac]))

    # Inicializar lista de mensajes si no existe
    if chat_id not in chat_messages:
        chat_messages[chat_id] = []

    # Agregar mensaje con ID único
    new_message = {
        "id": str(uuid.uuid4()),  # ID único para cada mensaje
        "sender": my_mac,
        "text": message_text,
        "timestamp": datetime.now().strftime("%H:%M"),
    }

    chat_messages[chat_id].append(new_message)

    return jsonify({"success": True})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
