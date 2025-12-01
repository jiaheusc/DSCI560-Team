import React, { useEffect, useState } from "react";
import { getMailbox } from "../api";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const TherapistHome = () => {
  const { token} = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);

  const load = async () => {
    try {
      const data = await getMailbox(token);   
      setMessages(data.messages || []);
    } catch (err) {
      console.error("Mailbox load error:", err);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const unreadCount = messages.filter((m) => !m.is_read).length;

  return (
    <div className="auth"
        style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",     
        alignItems: "center" 
      }}>
      <h2>Therapist Dashboard</h2>

      {/* Unread alert */}
      {unreadCount > 0 && (
        <p style={{ color: "red", fontWeight: "bold" }}>
          🔴 You have {unreadCount} new message{unreadCount > 1 ? "s" : ""} in your mailbox!
        </p>
      )}

      {/* Profile */}
      <button onClick={() => navigate("/profile")}>
        Edit Profile
      </button>

      {/* <button onClick={() => navigate("/chat")}>Chat</button> */}

      {/* Mailbox with badge */}
      <button
        onClick={() => navigate("/mailbox")}
        style={{ position: "relative" }}
      >
        Mailbox
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              width: "16px",
              height: "16px",
              borderRadius: "50%",
              background: "red",
              color: "white",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "12px"
            }}
          >
            {unreadCount}
          </span>
        )}
      </button>
      {/* AI Summary */}
      <button onClick={() => navigate("/ai-summary")}>
        AI Summary
      </button>
    </div>
  );
};

export default TherapistHome;
