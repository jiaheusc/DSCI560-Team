import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate, useParams } from "react-router-dom";
const HARMFUL_KEYWORDS = [
  // self-harm
  "suicide",
  "kill myself",
  "self harm",
  "end my life",
  // violence
  "bomb",
  "shoot",
  "stab",
  "kill ",
  // hate
  "hate ",
  "racist",
  "anti-gay",
  "anti black",
  "anti asian",
  // sexual
  "sex",
  "porn",
  "xxx",
  "nsfw",
  "18+",
  // harassment
  "bully",
  "idiot",
  "stupid",
  "loser"
];

const ChatRoom = () => {
  const containsHarmfulLanguage = (text) => {
  const t = text.toLowerCase();
  return HARMFUL_KEYWORDS.some((word) => t.includes(word));
};
  const { token, userId } = useAuth();
  const { groupId } = useParams();      
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [members, setMembers] = useState([]);
  const [groupName, setGroupName] = useState("");
  const bottomRef = useRef(null);
  const wsRef = useRef(null);
  const [showWarning, setShowWarning] = useState(false);
  const [warningType, setWarningType] = useState("");
  const [aiOpeningLine, setAiOpeningLine] = useState("");

  const [editingName, setEditingName] = useState("");
  const [editing, setEditing] = useState(false);
  const smallBtn = {
  padding: "4px 10px",
  border: "1px solid #ccc",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "14px"
};

  // scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // load messages + group info
  useEffect(() => {
    loadMessages(groupId);
    loadGroupInfo(groupId);
    connectWS(groupId);
  }, [groupId]);
  const loadGroups = () => {};
  const loadMessages = async (gid) => {
    const res = await fetch(`/api/messages?group_id=${gid}&limit=50`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    
    setMessages(data.messages || []);
  };

  const loadGroupInfo = async (gid) => {
    const res = await fetch(`/api/chat-groups/${gid}/members`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setMembers(data.members || []);

    const ginfo = await fetch(`/api/chat-groups`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const gdata = await ginfo.json();
    const g = gdata.groups.find(x => x.id === Number(gid));
    if (g) {
      setGroupName(g.group_name);
      setEditingName(g.group_name);
    }
  };

  // websocket
  const connectWS = (gid) => {
    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`ws://localhost:8000/api/ws?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const pkg = JSON.parse(event.data);
      if (pkg.type !== "message") return;
      const msg = pkg.message;

      if (msg.group_id === Number(gid)) {
        setMessages(prev => [...prev, msg]);
      }
    };
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    await fetch("/api/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        group_id: Number(groupId),
        content: input
      })
    });
    const data = await res.json();
    if (data.ok === false) {
      setWarningType(data.detail);         
      setAiOpeningLine(data.ai_opening_line || "");
      setShowWarning(true);
      return;
    }
    setInput("");
  };

  return (
    <div className="chatroom">

      {/* Header */}
<div
  className="chatroom-header"
  style={{
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 0",
  }}
>

  {/* Group name block */}
  <div
    className="group-name-edit-container"
    style={{
      display: "flex",
      alignItems: "center",
      gap: "8px",
    }}
  >
    {!editing ? (
      <>
        {/* Normal View */}
        <h3 style={{ margin: 0 }}>{groupName}</h3>

        {/* Edit icon */}
        <button
          onClick={() => setEditing(true)}
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            fontSize: "18px",
          }}
        >
          ✏️
        </button>
      </>
    ) : (
      <>
        {/* Editing Mode */}
        <input
          className="group-name-input"
          value={editingName}
          onChange={(e) => setEditingName(e.target.value)}
          style={{ padding: "4px 6px" }}
        />

        <button
          style={smallBtn}
          onClick={async () => {
            if (containsHarmfulLanguage(editingName)) {
              alert("Group name contains harmful or unsafe language.");
              return; 
            }
            const res = await fetch(`/api/chat-groups/${groupId}`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({ group_name: editingName }),
            });

            if (res.ok) {
              // Update UI immediately
              setGroupName(editingName);

              // Exit editing mode
              setEditing(false);
            }
          }}
        >
          Save
        </button>

        {/* Cancel Button */}
        <button
          style={smallBtn}
          onClick={() => {
            setEditing(false);
            setEditingName(groupName); // revert input
          }}
        >
          Cancel
        </button>
      </>
    )}
  </div>
</div>



      {/* Message List */}
      <div className="chat-msg-list">
        {messages.map((m) => {
          const isMe = m.user_id === userId;
          return (
            <div key={m.id} className={`msg-row ${isMe ? "me" : "other"}`}>
              <div className="msg-body">
                <div className="msg-username">
                  {m.is_bot ? "LLM Bot" : m.prefer_name || m.username}
                </div>
                <div className="msg-bubble">{m.content}</div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef}></div>
      </div>

      {/* input */}
      <div className="chat-input-bar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();   
              sendMessage();
            }
          }}
          placeholder="Type a message..."
        />
        <button onClick={sendMessage}>Send</button>
      </div>
          {showWarning && (
  <div className="modal-overlay">
    <div className="modal-box">

      <h3>We detected something important</h3>

      {warningType === "self_harm" && (
        <p>
          Your message indicates distress.  
          Would you like to speak privately with our AI assistant?
        </p>
      )}

      {warningType === "hate" && (
        <p>
          This message may require a private conversation.  
          Switch to a private AI chat?
        </p>
      )}

      <div className="modal-buttons">
        <button
          className="modal-btn-primary"
          onClick={async () => {
            setShowWarning(false);

            // Find AI group
            const groupsRes = await fetch("/api/chat-groups", {
              headers: { Authorization: `Bearer ${token}` }
            });
            const groupsData = await groupsRes.json();
            const aiGroup = groupsData.groups.find(g => g.is_ai_1on1 === true);

            if (!aiGroup) {
              alert("AI chat not found.");
              return;
            }

            // Start AI support chat
            await fetch("/api/support-chat/start", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({
                group_id: aiGroup.id,
                opening_message: aiOpeningLine,
              }),
            });

            // redirect to chatroom of AI group
            window.location.href = `/chat/${aiGroup.id}`;
          }}
        >
          Talk to AI
        </button>

        <button
          className="modal-btn-secondary"
          onClick={() => setShowWarning(false)}
        >
          Cancel
        </button>
      </div>

    </div>
  </div>
)}

    </div>
  );
};

export default ChatRoom;
