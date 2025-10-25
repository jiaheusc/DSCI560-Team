const MAX_FILE_SIZE = 10485760;

let chatHistory = JSON.parse(localStorage.getItem('chatHistory')) || [];
let all_files = []
let isUploading = false;

function renderChat(){
    const chatContainer = document.querySelector('.message-container');
    chatContainer.innerHTML = ''; 
    chatHistory.forEach(message => {
        renderMessage(message);
    });
}

/* upload part*/
function renderFileList(){
    fileList.innerHTML = '';
    if (all_files.length === 0) {
        fileList.innerHTML = '<li class="empty-state">No documents uploaded yet.</li>';
        return;
    }
    all_files.forEach(fileObject => {
        const li = document.createElement('li');
        li.className = 'file-item';
        const statusClass = fileObject.status.toLowerCase().replace('...', '');
        li.innerHTML = `
            <span class="file-icon">&#128196;</span>
            <span class="file-name">${fileObject.name}</span>
            <span class="file-status ${statusClass}">${fileObject.status}</span>
            <button class="delete-btn" data-id="${fileObject.id}">&times;</button>
        `;
        fileList.appendChild(li);
    });
}

async function processUploadQueue() {
    if (isUploading) return;
    const fileToUpload = all_files.find(f => f.status === 'Queued');
    if (!fileToUpload) return;
    isUploading = true;
    fileToUpload.status = 'Uploading...';
    renderFileList();
    try {
        await uploadFile(fileToUpload);
        fileToUpload.status = 'Ready';
    } catch (error) {
        console.error('Upload failed:', error);
        fileToUpload.status = 'Error';
    }
    isUploading = false;
    renderFileList();
    processUploadQueue();
}

async function uploadFile(fileObject) {
    const formData = new FormData();
    formData.append('file', fileObject.file, fileObject.name);
    const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData
    });
    if (!response.ok) {
        throw new Error(`Server error: ${response.statusText}`);
    }

}

/* chat part*/
function renderMessage(message){
    const chatContainer = document.querySelector('.message-container');
    const messageElement = document.createElement('div');
    messageElement.classList.add('chat-message');

    let innerHtmlContent = '';
    if (message.sender === 'bot') {
        messageElement.classList.add('bot');
        innerHtmlContent = `
            <div class="avatar">
                <img src="https://upload.wikimedia.org/wikipedia/commons/0/0c/Chatbot_img.png">
            </div>
            <div class="bot-message"></div>
        `;
    } else {
        messageElement.classList.add('user');
        innerHtmlContent = `
            <div class="user-message"></div>
            <div class="avatar">
                <img src="https://upload.wikimedia.org/wikipedia/commons/9/99/Sample_User_Icon.png">
            </div>
        `;
    }
    messageElement.innerHTML = innerHtmlContent;
    const textContainer = messageElement.querySelector('.bot-message, .user-message');
    textContainer.textContent = message.text;
    chatContainer.appendChild(messageElement);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function updateHistory(message) {
    chatHistory.push(message); 
    
    localStorage.setItem('chatHistory', JSON.stringify(chatHistory));

    if (message.sender === 'user') {
        try {
            const response = await fetch('http://localhost:8000/prompt-input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: message.text }) // 假设后端需要 {prompt: ...}
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }

            const data = await response.json();
            const botAnswer = data.answer;

            handleBotResponse(botAnswer);

        } catch (error) {
            console.error("Fetch error:", error);
            handleBotResponse("Sorry, the server connection failed");
        }
    }

    const chatContainer = document.querySelector('.message-container');
    chatContainer.innerHTML = ''; 
    chatHistory.forEach(message => {
        renderMessage(message);
    });
}

function handleUserSubmit(question) {
    const userMessage = {
        sender: 'user',
        text: question,
        timestamp: new Date()
    };
    updateHistory(userMessage);
}

function handleBotResponse(answer) {
    const botMessage = {
        sender: 'bot',
        text: answer,
        timestamp: new Date()
    };
    updateHistory(botMessage);
}


document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.input-container');
    const inputElement = document.getElementById('prompt-input');

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const text = inputElement.value.trim();
        if (!text) return;
        handleUserSubmit(text);
        inputElement.value = '';
        inputElement.focus();
    })
    inputElement.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          form.requestSubmit();
        }
    });
});

const fileInput = document.getElementById('file-upload');
const fileList = document.getElementById('file-list');

fileInput.addEventListener('change', (event) => {
    const files = event.target.files;
    if (!files.length) return;
    console.log('用户选择的文件：', files);
    for (let file of files) {
        const isPDF = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
        if (!isPDF) {
            alert(`File "${file.name}" is not a PDF and will be skipped.`);
            continue;
        }
        
        if (file.size > MAX_FILE_SIZE) {
            alert(`File "${file.name}" is larger than 10MB and will be skipped.`);
            continue;
        }

        const fileObject = {
            id: Date.now() + file.name,
            file: file,
            name: file.name,
            status: 'Queued'
        };
        all_files.push(fileObject);
    }
    event.target.value = null;
    renderFileList();
    processUploadQueue();
});

fileList.addEventListener('click', (event) => {
    if (event.target.classList.contains('delete-btn')) {
        const fileId = event.target.dataset.id;

        all_files = all_files.filter(f => f.id !== fileId);
        renderFileList();
    }
});

renderFileList();
renderChat();