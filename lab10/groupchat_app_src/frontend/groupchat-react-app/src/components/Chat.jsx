// Chat.jsx
import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../AuthContext";

const Chat = () => {
  const { token, userId } = useAuth();
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const wsRef = useRef(null);
  const bottomRef = useRef(null);

  // -----------------------------
  // Auto scroll to bottom when messages update
  // -----------------------------
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // -----------------------------
  // Load my chat groups
  // GET /api/chat-groups
  // -----------------------------
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

  // -----------------------------
  // Load history messages
  // GET /api/messages?group_id=xx
  // -----------------------------
  const loadMessages = async (gid) => {
    const res = await fetch(`/api/messages?group_id=${gid}&limit=50`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setMessages(data.messages || []);
  };

  // -----------------------------
  // Connect WebSocket for real-time chat
  // -----------------------------
  const connectWS = (gid) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(`ws://localhost:8000/api/ws?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      // Only push messages for the active group
      if (msg.group_id === gid) {
        setMessages((prev) => [...prev, msg]);
      }
    };

    ws.onclose = () => {
      console.warn("WebSocket closed");
    };
  };

  // -----------------------------
  // When user selects a group
  // -----------------------------
  const handleSelectGroup = (gid) => {
    setGroupId(gid);
    loadMessages(gid);
    connectWS(gid);
  };

  // -----------------------------
  // Send message
  // POST /api/messages
  // -----------------------------
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
        text: input
      })
    });

    if (res.ok) {
      setInput("");
    }
  };

  return (
    <div className="chat-page">

      {/* ------------------ Left panel: group list ------------------ */}
      <div className="chat-groups">
        <h3>Your Groups</h3>
        {groups.length === 0 && <p>No groups yet.</p>}

        {groups.map((g) => (
          <div
            key={g.id}
            className={`chat-group-item ${g.id === groupId ? "active" : ""}`}
            onClick={() => handleSelectGroup(g.id)}
          >
            {g.name} ({g.member_count})
          </div>
        ))}
      </div>

      {/* ------------------ Right panel: chat area ------------------ */}
      <div className="chat-main">
        {!groupId && (
          <p className="chat-placeholder">Select a group to start chatting</p>
        )}

        {groupId && (
          <>
            <div className="chat-msg-list">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`chat-msg ${
                    m.sender_id === userId ? "me" : "other"
                  }`}
                >
                  <div className="chat-msg-user">{m.sender_name}</div>
                  <div className="chat-msg-text">{m.text}</div>
                  <div className="chat-msg-time">
                    {new Date(m.created_at).toLocaleTimeString()}
                  </div>
                </div>
              ))}

              <div ref={bottomRef}></div>
            </div>

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
