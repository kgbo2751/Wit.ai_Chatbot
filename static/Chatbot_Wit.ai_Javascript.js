function buttons(message) {
    sendtochatbot(message);
}

function keypress(event) {
    if (event.key === "Enter") sendmessage();
}

function sendmessage() {
    const input = document.getElementById("messageinput");
    const message = input.value.trim();
    if (!message) return;
    sendtochatbot(message);
    input.value = "";
}

function sendtochatbot(message) {
    const messagesDiv = document.getElementById("messages");

    const now = new Date();
    const time = now.toLocaleTimeString("en-US", {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });

    const userWrapper = document.createElement('div');
    userWrapper.className = "message_box2";

    const userTime = document.createElement('div');
    userTime.className = "time";
    userTime.textContent = time;

    const userMessage = document.createElement('div');
    userMessage.className = "user";
    userMessage.textContent = "🧑‍💼 " + message;

    userWrapper.appendChild(userTime);
    userWrapper.appendChild(userMessage);
    messagesDiv.appendChild(userWrapper);

    setTimeout(() => {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }, 50);

    fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        const nowBot = new Date();
        const timeBot = nowBot.toLocaleTimeString("en-US", {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });

        const botWrapper = document.createElement('div');
        botWrapper.className = "message_box";

        const botMessage = document.createElement('div');
        botMessage.className = "bot";
        botMessage.innerHTML = "🤖 " + data.answer;

        const botTime = document.createElement('div');
        botTime.className = "time";
        botTime.textContent = timeBot;

        botWrapper.appendChild(botMessage);
        botWrapper.appendChild(botTime);
        messagesDiv.appendChild(botWrapper);

        setTimeout(() => {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }, 50);
    });
}

function scrollToBottom() {
    const messages = document.getElementById('messages');
    messages.scrollTop = messages.scrollHeight;
}

function addMessage(content, sender) {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = sender === 'user' ? 'user' : 'bot';
    div.innerHTML = content;
    messages.appendChild(div);

    scrollToBottom();
}