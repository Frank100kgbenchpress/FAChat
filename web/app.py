from flask import Flask, render_template, request, redirect, session, url_for, jsonify

app = Flask(__name__)
app.secret_key = "tu_clave_secreta_aqui"

# JSON de ejemplo de usuarios detectados
users_example = [
    {"mac": "00:11:22:33:44:55", "name": "", "status": "online"},
    {"mac": "AA:BB:CC:DD:EE:FF", "name": "", "status": "offline"},
    {"mac": "11:22:33:44:55:66", "name": "", "status": "online"},
]


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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
