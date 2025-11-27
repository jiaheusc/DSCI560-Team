import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../AuthContext";

const Chat = () => {
  const { token, userId } = useAuth();
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [groupInfo, setGroupInfo] = useState(null);
  const [members, setMembers] = useState([]);
  const [editingName, setEditingName] = useState("");
  const wsRef = useRef(null);
  const bottomRef = useRef(null);

  // scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // load user's chat groups
  const loadGroups = async () => {
    const res = await fetch("/api/chat-groups", {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setGroups(data.groups || []);
  };

  useEffect(() => {
    loadGroups();
  }, []);

  // load history for selected group
  const loadMessages = async (gid) => {
    const res = await fetch(`/api/messages?group_id=${gid}&limit=50`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setMessages(data.messages || []);
  };

  // connect WebSocket
  const connectWS = (gid) => {
    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`ws://localhost:8000/api/ws?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const pkg = JSON.parse(event.data);

      // backend sends { type: 'message', message: {...} }
      if (pkg.type !== "message") return;

      const msg = pkg.message;

      if (msg.group_id === gid) {
        setMessages((prev) => [...prev, msg]);
      }
    };

    ws.onclose = () => console.warn("WebSocket closed");
  };

  // user selects group
  const handleSelectGroup = async (gid) => {
    setGroupId(gid);

    // load messages
    await loadMessages(gid);

    // load members
    const memRes = await fetch(`/api/chat-groups/${gid}/members`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const mem = await memRes.json();
    setMembers(mem.members || []);

    // load group info
    const info = groups.find(g => g.id === gid);
    setGroupInfo(info);
    setEditingName(info.group_name);

    // connect websocket
    connectWS(gid);
  };


  // send chat message
  const sendMessage = async () => {
    if (!input.trim()) return;

    const res = await fetch("/api/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        group_id: groupId,
        content: input   // <-- must match backend
      })
    });

    if (res.ok) setInput("");
  };

  return (
  <div className="chat-container">

    {/* 左侧群组列表 */}
    <div className="chat-sidebar">
      <h3>Your Groups</h3>
      {groups.length === 0 && <p>No groups yet.</p>}

      {groups.map((g) => {
        const isActive = g.id === groupId;
        return (
          <button
            key={g.id}
            className={`group-btn ${isActive ? "active" : ""}`}
            onClick={() => handleSelectGroup(g.id)}
          >
            <div className="group-name">{g.group_name}</div>
            <div className="group-count">{g.current_size} members</div>
          </button>
        );
      })}
    </div>

    {/* 右侧聊天区 */}
    <div className="chat-main">

      {!groupId && (
        <p className="chat-placeholder">Select a group to start chatting</p>
      )}

      {groupId && (
        <>
          {/* ⭐ 聊天顶部栏（群名 + 成员头像）⭐ */}
          <div className="chat-header">

            {/* 群名可编辑 */}
            <div className="group-name-box">
              <input
                className="group-name-input"
                value={editingName}
                onChange={(e) => setEditingName(e.target.value)}
              />
              <button
                className="group-name-save-btn"
                onClick={async () => {
                  await fetch(`/api/chat-groups/${groupId}`, {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/json",
                      Authorization: `Bearer ${token}`
                    },
                    body: JSON.stringify({ group_name: editingName })
                  });
                  // reload group list so sidebar updates
                  loadGroups();
                }}
              >
                Save
              </button>
            </div>

            {/* 头像列表 */}
            <div className="member-avatar-list">
              {members.map((m) => (
                <img
                  key={m.user_id}
                  src={m.avatar_url || "/static/avatars/default.png"}
                  className="member-avatar"
                  title={m.prefer_name || m.username}
                />
              ))}
            </div>
          </div>
          {/* 聊天内容区 */}
          <div className="chat-msg-list">
            {messages.map((m) => {
              const isMe = m.user_id === userId;

              return (
                <div key={m.id} className={`msg-row ${isMe ? "me" : "other"}`}>
                  <div className="msg-body">

                    <div className="msg-username">
                      {m.is_bot ? "LLM Bot" : (m.prefer_name || m.username)}
                    </div>

                    <div className="msg-bubble">
                      {m.content}
                    </div>

                    <div className="msg-time">
                      {new Date(m.created_at).toLocaleTimeString()}
                    </div>

                  </div>
                </div>
              );
            })}

            <div ref={bottomRef}></div>
          </div>

          {/* 输入框 */}
          <div className="chat-input-bar">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a message..."
            />
            <button onClick={sendMessage}>Send</button>
          </div>
        </>
      )}

    </div>
  </div>
);

};

export default Chat;
