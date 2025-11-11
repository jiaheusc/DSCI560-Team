const $ = (id) => document.getElementById(id);
function getToken() {
  return localStorage.getItem("token");
}
function setToken(t) {
  localStorage.setItem("token", t);
}
function clearToken() {
  localStorage.removeItem("token");
}

const authDiv = $("auth");
const questionnaireDiv = $("questionnaire");
const groupDiv = $("groupSelect");
const chatDiv = $("chat");
const messagesDiv = $("messages");

// Auth
const usernameInput = $("username");
const passwordInput = $("password");
const signupBtn = $("signupBtn");
const loginBtn = $("loginBtn");
const logoutBtn = $("logoutBtn");
const authMsg = $("authMsg");

// Questionnaire
const submitQBtn = $("submitQBtn");
const qContent = $("qContent");

// Groups
const groupList = $("groupList");
const newGroupName = $("newGroupName");
const createGroupBtn = $("createGroupBtn");
const enterChatBtn = $("enterChatBtn");

const chatInput = $("chatInput");
const sendBtn = $("sendBtn");

const API = location.origin + "/api";
let token = getToken() || "";
let ws = null;
let selectedGroupId = null;

function show(el) {
  [authDiv, questionnaireDiv, groupDiv, chatDiv].forEach(e => e.classList.add("hidden"));
  el.classList.remove("hidden");
}

async function callAPI(path, method = "GET", body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!res.ok) {
    let msg = "HTTP " + res.status;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

signupBtn.onclick = async () => {
  try {
    const out = await callAPI("/signup", "POST", {
      username: usernameInput.value.trim(),
      password: passwordInput.value
    });
    token = out.token;
    setToken(token);
    await afterLoginFlow();
  } catch (e) {
    authMsg.textContent = e.message;
  }
};

loginBtn.onclick = async () => {
  try {
    const out = await callAPI("/login", "POST", {
      username: usernameInput.value.trim(),
      password: passwordInput.value
    });
    token = out.token;
    setToken(token);
    await afterLoginFlow();
  } catch (e) {
    authMsg.textContent = e.message;
  }
};

logoutBtn.onclick = () => {
  token = "";
  clearToken();
  show(authDiv);
};

async function afterLoginFlow() {
  try {
    const groups = await callAPI("/chat-groups");
    if (groups.length > 0) {
      // enter the first group
      selectedGroupId = groups[0].id;
      localStorage.setItem("group_id", selectedGroupId);
      await loadMessages();
      connectWS();
      show(chatDiv);
      return;
    }
  } catch (e) {
    console.warn("Group show failed", e);
  }
  // nogroup -> questionaire
  show(questionnaireDiv);
}

submitQBtn.onclick = async () => {
  const content = qContent.value.trim();
  if (!content) return alert("请填写问卷内容");
  await callAPI("/questionnaire", "POST", { content: { mood: content } });
  await loadGroups();
  show(groupDiv);
};

async function loadGroups() {
  const groups = await callAPI("/chat-groups");
  groupList.innerHTML = "";
  groups.forEach(g => {
    const btn = document.createElement("button");
    btn.textContent = g.group_name;
    btn.onclick = () => {
      selectedGroupId = g.id;
      [...groupList.children].forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
    };
    groupList.appendChild(btn);
  });
}

createGroupBtn.onclick = async () => {
  const name = newGroupName.value.trim();
  if (!name) return alert("请输入群组名");
  await callAPI("/chat-groups", "POST", { group_name: name });
  await loadGroups();
};

enterChatBtn.onclick = async () => {
  if (!selectedGroupId) return alert("请选择一个群组");
  localStorage.setItem("group_id", selectedGroupId);
  await loadMessages();
  connectWS();
  show(chatDiv);
};

function addMessage(m) {
  const el = document.createElement("div");
  el.className = "message" + (m.is_bot ? " bot" : "");
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${m.username || "unknown"} • ${new Date(m.created_at).toLocaleString()}`;
  const body = document.createElement("div");
  body.textContent = m.content;
  el.appendChild(meta);
  el.appendChild(body);
  messagesDiv.appendChild(el);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function loadMessages() {
  const gid = localStorage.getItem("group_id");
  const data = await callAPI(`/messages?group_id=${gid}`);
  messagesDiv.innerHTML = "";
  for (const m of data.messages) addMessage(m);
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const gid = localStorage.getItem("group_id");
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${token}`);
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "message" && data.message.group_id == gid) addMessage(data.message);
    } catch (e) {}
  };
  ws.onclose = () => setTimeout(connectWS, 2000);
}

sendBtn.onclick = async () => {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  await callAPI("/messages", "POST", {
    content: text,
    group_id: Number(localStorage.getItem("group_id"))
  });
};

(async function init() {
  if (token) {
    try {
      await afterLoginFlow();
    } catch {
      show(authDiv);
    }
  } else {
    show(authDiv);
  }
})();
