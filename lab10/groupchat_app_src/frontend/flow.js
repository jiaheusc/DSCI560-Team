const authDiv = document.getElementById("auth");
const questionnaireDiv = document.getElementById("questionnaire");
const groupDiv = document.getElementById("groupSelect");
const chatDiv = document.getElementById("chat");

const submitQBtn = document.getElementById("submitQBtn");
const qContent = document.getElementById("qContent");
const groupList = document.getElementById("groupList");
const newGroupName = document.getElementById("newGroupName");
const createGroupBtn = document.getElementById("createGroupBtn");
const enterChatBtn = document.getElementById("enterChatBtn");

let selectedGroupId = null;
let token = localStorage.getItem("token");

function show(el) {
  [authDiv, questionnaireDiv, groupDiv, chatDiv].forEach(e => e.classList.add("hidden"));
  el.classList.remove("hidden");
}

// If login in, show questionaires
if (token) {
  show(questionnaireDiv);
}

// submit questionaires
submitQBtn.onclick = async () => {
  const content = qContent.value.trim();
  if (!content) return alert("Please fill something.");
  await fetch("/api/questionnaire", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ content: { mood: content } })
  });
  show(groupDiv);
  loadGroups();
};

// load groups
async function loadGroups() {
  const res = await fetch("/api/chat-groups", {
    headers: { "Authorization": `Bearer ${token}` }
  });
  const groups = await res.json();
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

// create group
createGroupBtn.onclick = async () => {
  const name = newGroupName.value.trim();
  if (!name) return alert("Enter group name");
  await fetch("/api/chat-groups", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ group_name: name })
  });
  loadGroups();
};

// enter chat
enterChatBtn.onclick = () => {
  if (!selectedGroupId) return alert("Select a group first");
  localStorage.setItem("group_id", selectedGroupId);
  show(chatDiv);
};