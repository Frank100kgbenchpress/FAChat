let users = [];
let currentChat = null;
let chatMessages = {}; // Para guardar mensajes de cada chat
let writingState = {}; // mac -> true/false (si está escribiendo)

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

// Aplicar nombres guardados en localStorage
function applySavedNames() {
    let savedNames = JSON.parse(localStorage.getItem('userNames')) || {};
    users.forEach(user => {
        if(savedNames[user.mac]) user.name = savedNames[user.mac];
        writingState[user.mac] = false; // Inicialmente todos escuchando
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
        chatItem.onclick = () => user.status === "listening" && openChat(index);

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
            <span class="status ${user.status || "listening"}">${user.status || "listening"}</span>
        `;
        chatItem.appendChild(button);

        if(user.status === "offline") chatItem.classList.add("offline");

        chatList.appendChild(chatItem);
    });
}

// Abrir un chat con animación y mensajes persistentes
function openChat(index) {
    currentChat = users[index];
    const header = document.getElementById("chat-header");
    const displayName = currentChat.name ? currentChat.name : "Desconocido";
    header.innerHTML = `<h2>${displayName}</h2><p class="status ${currentChat.status || "listening"}">${currentChat.status || "listening"}</p>`;

    document.getElementById("input-area").style.display = currentChat.status === "offline" ? "none" : "flex";

    document.querySelectorAll(".chat-item").forEach((el, i) => {
        if(i === index) el.classList.add("selected");
        else el.classList.remove("selected");
    });

    // Animación suave: minimizar chat anterior y expandir actual
    const chatWindow = document.querySelector('.chat-window');
    chatWindow.style.transform = "scaleY(0.95)";
    chatWindow.style.opacity = "0.5";

    setTimeout(() => {
        chatWindow.classList.add('open');
        chatWindow.style.transform = "scaleY(1)";
        chatWindow.style.opacity = "1";
    }, 200);

    // Renderizar mensajes previos del chat
    renderMessages(currentChat.mac);
}

// Función para renderizar mensajes
function renderMessages(mac) {
    const messagesDiv = document.getElementById("messages");
    messagesDiv.innerHTML = "";

    const msgs = chatMessages[mac] || [];
    msgs.forEach(m => {
        const p = document.createElement("p");
        p.className = m.sender === "me" ? "msg-me" : "msg-them";
        p.textContent = m.text;
        messagesDiv.appendChild(p);
        setTimeout(() => p.classList.add("show"), 50);
    });
}

// Asignar un nombre a un usuario
function assignName(index) {
    const name = prompt("Ingrese un nombre para este dispositivo:");
    if(name) {
        users[index].name = name;
        let savedNames = JSON.parse(localStorage.getItem('userNames')) || {};
        savedNames[users[index].mac] = name;
        localStorage.setItem('userNames', JSON.stringify(savedNames));
        loadChats();
    }
}

// Actualizar estado listening/writing según input
const input = document.getElementById("message-input");
input.addEventListener("input", () => {
    if(currentChat) {
        writingState[currentChat.mac] = input.value.trim().length > 0;
        updateUserState(currentChat.mac);
    }
});

// Actualizar visualización del estado
function updateUserState(mac) {
    const user = users.find(u => u.mac === mac);
    if(user) {
        user.status = writingState[mac] ? "writing" : "listening";
        const chatEl = document.getElementById(`chat-${users.indexOf(user)}`);
        if(chatEl) {
            chatEl.querySelector(".status").textContent = user.status;
            chatEl.querySelector(".status").className = `status ${user.status}`;
        }
    }
}

// Enviar mensaje solo si el otro está listening
document.getElementById("send-btn").onclick = () => {
    const text = input.value.trim();
    if(!text || !currentChat) return;

    if(currentChat.status !== "listening") {
        alert(`${currentChat.name || "Desconocido"} no está escuchando en este momento.`);
        return;
    }

    // Guardar mensaje en memoria
    if(!chatMessages[currentChat.mac]) chatMessages[currentChat.mac] = [];
    chatMessages[currentChat.mac].push({ sender: "me", text: text });

    // Renderizar mensajes del chat
    renderMessages(currentChat.mac);

    input.value = "";
    writingState[currentChat.mac] = false;
    updateUserState(currentChat.mac);
};

// Enviar mensaje solo con Enter
input.addEventListener("keydown", (e) => {
    if(e.key === "Enter") {
        e.preventDefault();
        document.getElementById("send-btn").click();
    }
});

// Inicial usuario con menú logout
document.addEventListener("DOMContentLoaded", () => {
    fetchUsers();

    const userInitial = document.getElementById("user-initial");
    userInitial.addEventListener("click", () => userInitial.classList.toggle("active"));
    document.addEventListener("click", (e) => {
        if(!userInitial.contains(e.target)) userInitial.classList.remove("active");
    });
});
