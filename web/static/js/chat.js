let users = [];
let currentChat = null;
let isGroupChat = false;

// Cargar usuarios desde Flask
function fetchUsers() {
    fetch('/get_users')
        .then(res => res.json())
        .then(data => {
            users = data;
            applySavedNames();
            loadChats();
        })
        .catch(err => console.error("Error al cargar usuarios:", err));
}

// Aplicar nombres guardados
function applySavedNames() {
    let savedNames = JSON.parse(localStorage.getItem('userNames')) || {};
    users.forEach(user => {
        if(savedNames[user.mac]) user.name = savedNames[user.mac];
    });
}

// Cargar la lista de chats
function loadChats() {
    const chatList = document.getElementById("chat-list");
    chatList.innerHTML = "";

    users.forEach((user, index) => {
        const chatItem = document.createElement("div");
        chatItem.className = "chat-item";
        chatItem.id = "chat-" + index;
        chatItem.setAttribute("data-mac", user.mac);
        chatItem.onclick = () => openChat(index);

        const displayName = user.name ? user.name : "Desconocido";

        const button = document.createElement("button");
        button.className = "assign-name-btn";
        button.innerHTML = "⋮";
        button.onclick = (e) => {
            e.stopPropagation();
            assignName(index);
        };

        chatItem.innerHTML = `
            <div>
                <span class="chat-name">${displayName}</span>
                ${!user.name ? `<small class="chat-mac">${user.mac}</small>` : ""}
            </div>
            <span class="status ${user.status || "offline"}">${user.status || "offline"}</span>
        `;
        chatItem.appendChild(button);

        if(user.status === "offline") chatItem.classList.add("offline");

        chatList.appendChild(chatItem);
    });
}

// Abrir chat individual
function openChat(index) {
    isGroupChat = false;
    currentChat = users[index];
    const header = document.getElementById("chat-header");
    const displayName = currentChat.name ? currentChat.name : "Desconocido";
    header.innerHTML = `<h2>${displayName}</h2><p class="status ${currentChat.status || "offline"}">${currentChat.status || "offline"}</p>`;

    document.getElementById("input-area").style.display = currentChat.status === "offline" ? "none" : "flex";

    // Actualizar selección visual
    document.querySelectorAll(".chat-item").forEach((el, i) => {
        if(i === index) el.classList.add("selected");
        else el.classList.remove("selected");
    });
    document.getElementById("group-chat").classList.remove("selected");

    // Cargar mensajes desde el servidor
    loadMessages(currentChat.mac);
}

// Abrir chat grupal
function openGroupChat() {
    isGroupChat = true;
    currentChat = null;
    const header = document.getElementById("chat-header");
    header.innerHTML = `<h2>💬 Chat Grupal</h2><p class="status online">Todos los usuarios online</p>`;

    document.getElementById("input-area").style.display = "flex";

    // Actualizar selección visual
    document.getElementById("group-chat").classList.add("selected");
    document.querySelectorAll(".chat-item").forEach(el => {
        el.classList.remove("selected");
    });

    // Limpiar mensajes (o cargar mensajes grupales si los guardas)
    document.getElementById("messages").innerHTML = "";
}

// Cargar mensajes desde el servidor
function loadMessages(otherMac) {
    if (isGroupChat) return; // Los mensajes grupales no se cargan así

    fetch(`/get_messages/${otherMac}`)
        .then(res => res.json())
        .then(messages => {
            renderMessages(messages);
        })
        .catch(err => console.error("Error al cargar mensajes:", err));
}

// Renderizar mensajes
function renderMessages(messages) {
    const messagesDiv = document.getElementById("messages");

    // Verificar si los mensajes son diferentes usando IDs
    const currentMessageIds = new Set(Array.from(messagesDiv.querySelectorAll('p')).map(p => p.dataset.messageId));
    const newMessageIds = new Set(messages.map(m => m.id));

    // Si los conjuntos de IDs son iguales, no hacer nada
    if (currentMessageIds.size === newMessageIds.size &&
        [...currentMessageIds].every(id => newMessageIds.has(id))) {
        return;
    }

    // Si hay cambios, renderizar todo de nuevo
    messagesDiv.innerHTML = "";

    messages.forEach(m => {
        const p = document.createElement("p");
        const isMyMessage = m.sender === currentUserMac;
        p.className = isMyMessage ? "msg-me" : "msg-them";
        p.dataset.messageId = m.id;

        const timestamp = m.timestamp ? `<small class="timestamp">${m.timestamp}</small>` : '';

        // Detectar si es mensaje de archivo
        if (m.text && m.text.startsWith("[ARCHIVO]")) {
            p.classList.add("file-message");
            const fileInfo = m.text.replace("[ARCHIVO]", "");
            p.innerHTML = `<span class="file-info">📎 ${fileInfo}</span>${timestamp}`;
        } else {
            p.innerHTML = `${m.text} ${timestamp}`;
        }

        messagesDiv.appendChild(p);
        setTimeout(() => p.classList.add("show"), 50);
    });

    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Asignar nombre
function assignName(index) {
    const name = prompt("Ingrese un nombre para este dispositivo:");
    if(name) {
        users[index].name = name;
        let savedNames = JSON.parse(localStorage.getItem('userNames')) || {};
        savedNames[users[index].mac] = name;
        localStorage.setItem('userNames', JSON.stringify(savedNames));
        loadChats();

        // Si estamos en el chat de esta persona, actualizar header
        if(currentChat && currentChat.mac === users[index].mac) {
            const header = document.getElementById("chat-header");
            header.innerHTML = `<h2>${name}</h2><p class="status ${currentChat.status || "offline"}">${currentChat.status || "offline"}</p>`;
        }
    }
}

// Función para enviar mensaje
function sendMessage() {
    const input = document.getElementById("message-input");
    const text = input.value.trim();

    if(!text) return;

    if (isGroupChat) {
        // Enviar a todos los usuarios online
        const onlineUsers = users.filter(user => user.status === "online");
        let sentCount = 0;

        onlineUsers.forEach(user => {
            fetch('/send_message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    other_mac: user.mac,
                    message: text
                })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) sentCount++;
            })
            .catch(err => console.error("Error enviando mensaje grupal:", err));
        });

        // Mostrar mensaje localmente
        const messagesDiv = document.getElementById("messages");
        const p = document.createElement("p");
        p.className = "msg-me";
        p.innerHTML = `${text} <small class="timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</small>`;
        messagesDiv.appendChild(p);
        setTimeout(() => p.classList.add("show"), 50);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        console.log(`Mensaje grupal enviado a ${sentCount} usuarios`);

    } else if(currentChat) {
        // Enviar mensaje individual
        fetch('/send_message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                other_mac: currentChat.mac,
                message: text
            })
        })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                loadMessages(currentChat.mac);
            }
        })
        .catch(err => console.error("Error al enviar mensaje:", err));
    }

    input.value = "";
}

// Función para enviar archivo
function sendFile(file) {
    if (!file) return;

    const fileName = file.name;
    const fileSize = (file.size / 1024 / 1024).toFixed(2) + " MB";

    if (isGroupChat) {
        // Enviar archivo a todos los usuarios online
        const onlineUsers = users.filter(user => user.status === "online");
        let sentCount = 0;

        onlineUsers.forEach(user => {
            // Aquí implementarías el envío real del archivo
            // Por ahora solo mostramos el mensaje
            console.log(`Enviando archivo ${fileName} a ${user.mac}`);
            sentCount++;
        });

        // Mostrar mensaje de archivo localmente
        const messagesDiv = document.getElementById("messages");
        const p = document.createElement("p");
        p.className = "msg-me file-message";
        p.innerHTML = `<span class="file-info">📎 ${fileName}</span><span class="file-size">${fileSize}</span> <small class="timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</small>`;
        messagesDiv.appendChild(p);
        setTimeout(() => p.classList.add("show"), 50);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        alert(`Archivo '${fileName}' enviado a ${sentCount} usuarios`);

    } else if(currentChat) {
        // Enviar archivo individual
        // Aquí llamarías a tu backend para enviar el archivo
        fetch('/send_file', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                other_mac: currentChat.mac,
                file_path: file.name  // En una implementación real, subirías el archivo
            })
        })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                // Mostrar mensaje de archivo enviado
                const messagesDiv = document.getElementById("messages");
                const p = document.createElement("p");
                p.className = "msg-me file-message";
                p.innerHTML = `<span class="file-info">📎 ${fileName}</span><span class="file-size">${fileSize}</span> <small class="timestamp">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</small>`;
                messagesDiv.appendChild(p);
                setTimeout(() => p.classList.add("show"), 50);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } else {
                alert("Error al enviar archivo: " + (data.error || "Error desconocido"));
            }
        })
        .catch(err => {
            console.error("Error enviando archivo:", err);
            alert("Error de conexión al enviar archivo");
        });
    }
}

// Botón enviar mensaje
document.getElementById("send-btn").onclick = sendMessage;

// Enter envía mensaje
document.getElementById("message-input").addEventListener("keydown", (e) => {
    if(e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

// Botón de archivo
document.getElementById("file-btn").addEventListener("click", () => {
    document.getElementById("file-input").click();
});

// Selección de archivo
document.getElementById("file-input").addEventListener("change", (e) => {
    if(e.target.files.length > 0) {
        sendFile(e.target.files[0]);
        e.target.value = ''; // Resetear input
    }
});

// Chat grupal
document.getElementById("group-chat").addEventListener("click", openGroupChat);

// Toggle logout menu
document.getElementById("user-initial").addEventListener("click", function() {
    this.classList.toggle("active");
});

// Cerrar menú al hacer click fuera
document.addEventListener("click", function(e) {
    if (!e.target.closest('.user-initial')) {
        document.getElementById('user-initial').classList.remove('active');
    }
});

// Polling para refrescar usuarios y mensajes
function startUserPolling() {
    let isPolling = false;

    setInterval(() => {
        if (isPolling) return;

        isPolling = true;
        fetch('/get_users')
            .then(res => res.json())
            .then(data => {
                users = data;
                applySavedNames();
                loadChats();

                // Si hay un chat abierto, recargar sus mensajes también
                if(currentChat && !isGroupChat) {
                    return fetch(`/get_messages/${currentChat.mac}`)
                        .then(res => res.json())
                        .then(messages => {
                            renderMessages(messages);
                        });
                }
            })
            .catch(err => console.error(err))
            .finally(() => {
                isPolling = false;
            });
    }, 3000);
}

// Inicialización
document.addEventListener("DOMContentLoaded", () => {
    fetchUsers();
    startUserPolling();
});