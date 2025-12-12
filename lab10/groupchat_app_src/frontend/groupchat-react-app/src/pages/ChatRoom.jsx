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
  "loser",
];

const ChatRoom = () => {
  const { token, userId } = useAuth();
  const { groupId } = useParams();
  const navigate = useNavigate();

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [members, setMembers] = useState([]);
  const [groupName, setGroupName] = useState("");

  const [myUsername, setMyUsername] = useState(""); // 当前登录用户的 username

  const bottomRef = useRef(null);
  const wsRef = useRef(null);
  const [isSummarizing, setIsSummarizing] = useState(false);

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
    fontSize: "14px",
  };

  const numericUserId = Number(userId);

  const containsHarmfulLanguage = (text) => {
    const t = (text || "").toLowerCase();
    return HARMFUL_KEYWORDS.some((word) => t.includes(word));
  };

  // 滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 首次 / groupId 变化时加载数据 & 建立 WS
  useEffect(() => {
    if (!groupId) return;
    loadMessages(groupId);
    loadGroupInfo(groupId);
    connectWS(groupId);

    // 组件卸载时关闭 ws
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [groupId]);

  // 根据成员列表 + userId 推断当前用户的 username
  useEffect(() => {
    if (!members.length || !numericUserId) return;
    const me = members.find((m) => m.user_id === numericUserId);
    if (me) {
      setMyUsername(me.username);
    }
  }, [members, numericUserId]);

  const loadMessages = async (gid) => {
    const res = await fetch(`/api/messages?group_id=${gid}&limit=50`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    const visibleMessages = (data.messages || []).filter(
      (m) => m.is_visible !== false
    );

    setMessages(visibleMessages);
  };

  const loadGroupInfo = async (gid) => {
    // group info
    const res = await fetch(`/api/chat-groups/${gid}/members`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    setMembers(data.members || []);

    // group name
    const ginfo = await fetch(`/api/chat-groups`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const gdata = await ginfo.json();
    const g = gdata.groups.find((x) => x.id === Number(gid));
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
        setMessages((prev) => [...prev, msg]);
      }
    };
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    if (trimmed.toLowerCase().startsWith("@WeMindBot summary")) {
      await handleSummarize(trimmed);
      setInput("");   
      return;
    }

    const res = await fetch("/api/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        group_id: Number(groupId),
        content: input,
      }),
    });

    const data = await res.json();

    // dangerous message detection
    if (data.ok === false) {
      setWarningType(data.detail);
      setAiOpeningLine(data.ai_opening_line || "");
      setShowWarning(true);
      return;
    }

    // normal sed
    setInput("");
  };
  const handleSummarize = async (triggerText) => {
    if (isSummarizing) return;
    setIsSummarizing(true);

    try {
      const res = await fetch("/api/support-chat/summary", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          group_id: Number(groupId),
          content:
            triggerText ||
            "Please summarize the recent group conversation.",
        }),
      });

      const data = await res.json();
      if (!res.ok || data.ok === false) {
        alert("Failed to generate summary. Please try again.");
      }
    } catch (e) {
      console.error(e);
      alert("Network error while summarizing.");
    } finally {
      setIsSummarizing(false);
    }
  };


  return (
    <div className="chatroom-container">
      {/* Header：name + edit */}
      <div
        className="chatroom-header"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 0",
        }}
      >
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
              <h3 style={{ margin: 0 }}>{groupName}</h3>
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
                    setGroupName(editingName);
                    setEditing(false);
                  }
                }}
              >
                Save
              </button>

              <button
                style={smallBtn}
                onClick={() => {
                  setEditing(false);
                  setEditingName(groupName);
                }}
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
      <div className="chat-msg-wrapper">
      {/* Message List */}
        <div className="chat-msg-list">
          {messages.map((m) => {
            // user_id first
            const isMeById =
              !m.is_bot &&
              typeof m.user_id !== "undefined" &&
              Number(m.user_id) === numericUserId;

            // then username
            const isMeByName =
              !m.is_bot && myUsername && m.username === myUsername;

            const isMe = isMeById || isMeByName;

            // prefer name
            const member = members.find((u) => u.username === m.username);
            const displayName = m.is_bot
              ? "WeMind AI"
              : member?.prefer_name ||
                member?.username ||
                m.username ||
                "Unknown";

            return (
              <div key={m.id} className={`msg-row ${isMe ? "me" : ""}`}>
                <div className="msg-body">
                  <div className="msg-username">{displayName}</div>
                  <div className="msg-bubble">{m.content}</div>
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
        <button
          className="summary-chip summary-fab"
          onClick={handleSummarize}
          disabled={isSummarizing}
        >
          <span className="summary-chip-text">
            {isSummarizing ? "Summarizing..." : "Help me summarize group chat"}
          </span>
        </button>
        
      </div>

      {/* Input */}
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

      {/* Danger detection */}
      {showWarning && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h3>We detected something important</h3>

            {warningType === "self_harm" && (
              <p>
                Your message indicates distress.
                <br />
                Would you like to speak privately with our AI assistant?
              </p>
            )}

            {warningType === "hate" && (
              <p>
                This message may require a private conversation.
                <br />
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
                    headers: { Authorization: `Bearer ${token}` },
                  });
                  const groupsData = await groupsRes.json();
                  const aiGroup = groupsData.groups.find(
                    (g) => g.is_ai_1on1 === true
                  );

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

                  // goto ai chat 
                  navigate(`/chat/${aiGroup.id}`);
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
