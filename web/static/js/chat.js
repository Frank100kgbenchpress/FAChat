let users = [];
let currentChat = null;
let writingState = {};

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
        writingState[user.mac] = false;
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
        const earIcon = user.listening ? "👂" : "❌👂";

        const button = document.createElement("button");
        button.className = "assign-name-btn";
        button.innerHTML = "⋮";
        button.onclick = (e) => {
            e.stopPropagation();
            assignName(index);
        };

        chatItem.innerHTML = `
            <div>
                <span class="chat-name">${displayName} ${earIcon}</span>
                ${!user.name ? `<small class="chat-mac">${user.mac}</small>` : ""}
            </div>
            <span class="status ${user.status || "listening"}">${user.status || "listening"}</span>
        `;
        chatItem.appendChild(button);

        if(user.status === "offline") chatItem.classList.add("offline");

        chatList.appendChild(chatItem);
    });
}

// Abrir chat - CARGAR MENSAJES DESDE EL SERVIDOR
function openChat(index) {
    currentChat = users[index];
    const header = document.getElementById("chat-header");
    const displayName = currentChat.name ? currentChat.name : "Desconocido";
    const earIcon = currentChat.listening ? "👂" : "❌👂";
    header.innerHTML = `<h2>${displayName} ${earIcon}</h2><p class="status ${currentChat.status || "listening"}">${currentChat.status || "listening"}</p>`;

    document.getElementById("input-area").style.display = currentChat.status === "offline" ? "none" : "flex";

       // LIMPIAR EL INPUT AL CAMBIAR DE CHAT
    document.getElementById("message-input").value = "";

    document.querySelectorAll(".chat-item").forEach((el, i) => {
        if(i === index) el.classList.add("selected");
        else el.classList.remove("selected");
    });

    // Cargar mensajes desde el servidor
    loadMessages(currentChat.mac);
}

// CARGAR mensajes desde el servidor
function loadMessages(otherMac) {
    fetch(`/get_messages/${otherMac}`)
        .then(res => res.json())
        .then(messages => {
            renderMessages(messages);
        })
        .catch(err => console.error("Error al cargar mensajes:", err));
}

// Renderizar mensajes (VERSIÓN DEFINITIVA CON IDs)
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
        p.dataset.messageId = m.id;  // Guardar ID en el elemento

        const timestamp = m.timestamp ? `<small class="timestamp">${m.timestamp}</small>` : '';
        p.innerHTML = `${m.text} ${timestamp}`;

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
            const earIcon = currentChat.listening ? "👂" : "❌👂";
            header.innerHTML = `<h2>${name} ${earIcon}</h2><p class="status ${currentChat.status || "listening"}">${currentChat.status || "listening"}</p>`;
        }
    }
}

// Función para enviar mensaje (AHORA AL SERVIDOR)
function sendMessage() {
    const input = document.getElementById("message-input");
    const text = input.value.trim();

    if(!text || !currentChat) return;

    if(!currentChat.listening) {
        alert(`${currentChat.name || "Usuario"} no está escuchando en este momento.`);
        return;
    }

    // Enviar mensaje al servidor
    fetch('/send_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            other_mac: currentChat.mac,
            message: text
        })
    })
    .then(res => res.json())
    .then(data => {
        if(data.success) {
            // Recargar mensajes después de enviar
            loadMessages(currentChat.mac);
            input.value = "";
        } else {
            alert("Error al enviar el mensaje");
        }
    })
    .catch(err => {
        console.error("Error al enviar mensaje:", err);
        alert("Error de conexión al enviar mensaje");
    });
}

// Botón enviar
document.getElementById("send-btn").onclick = sendMessage;

// Enter envía mensaje
document.getElementById("message-input").addEventListener("keydown", (e) => {
    if(e.key === "Enter") {
        e.preventDefault();
        sendMessage();
    }
});

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

// Polling mejorado para refrescar usuarios y mensajes
function startUserPolling() {
    let isPolling = false;

    setInterval(() => {
        if (isPolling) return; // Evitar superposición de requests

        isPolling = true;
        fetch('/get_users')
            .then(res => res.json())
            .then(data => {
                users = data;
                applySavedNames();
                loadChats();

                // Si hay un chat abierto, recargar sus mensajes también
                if(currentChat) {
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
    }, 3000); // Aumentado a 3 segundos
}

// Inicialización
document.addEventListener("DOMContentLoaded", () => {
    fetchUsers();
    startUserPolling();
});