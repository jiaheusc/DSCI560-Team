import React, { useEffect, useState } from "react";
import { getMailbox } from "../api";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const TherapistHome = () => {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);

  const load = async () => {
    const data = await getMailbox(token);
    setMessages(data);
  };

  useEffect(() => {
    load();
  }, []);

  const unreadCount = messages.filter((m) => !m.is_read).length;

  return (
    <div className="auth">
      <h2>Therapist Dashboard</h2>

      {/* 🔥 Unread message alert */}
      {unreadCount > 0 && (
        <p style={{ color: "red", fontWeight: "bold" }}>
          🔴 You have {unreadCount} new message{unreadCount > 1 ? "s" : ""} in your mailbox!
        </p>
      )}

      <button onClick={() => navigate("/profile")}>Edit Profile</button>

      <button onClick={() => navigate("/chat")}>Chat</button>

      {/* 🔥 Mailbox button with unread badge */}
      <button onClick={() => navigate("/mailbox")} style={{ position: "relative" }}>
        Mailbox
        {unreadCount > 0 && (
          <span
            style={{
              background: "red",
              color: "white",
              borderRadius: "50%",
              padding: "2px 6px",
              fontSize: 12,
              marginLeft: 6
            }}
          >
            {unreadCount}
          </span>
        )}
      </button>

      <button style={{ background: "#ccc" }} onClick={logout}>
        Log out
      </button>
    </div>
  );
};

export default TherapistHome;
