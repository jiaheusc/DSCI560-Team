import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { getMailbox } from "../api";
import { useNavigate } from "react-router-dom";

const UserHome = () => {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);

  // Load mailbox unread count
  const loadUnread = async () => {
    try {
      const data = await getMailbox(token);
      const unread = data.filter((m) => !m.is_read).length;
      setUnreadCount(unread);
    } catch (err) {
      console.error("Mailbox error:", err);
    }
  };

  useEffect(() => {
    loadUnread();
  }, []);

  return (
    <div className="auth">
      <h2>User Home</h2>

      <p>Your questionnaire has been submitted. Waiting for therapist approval.</p>

      {/* 🔥 Unread message banner */}
      {unreadCount > 0 && (
        <p style={{ color: "red", fontWeight: "bold" }}>
          You have {unreadCount} unread message{unreadCount > 1 ? "s" : ""} in your mailbox!
        </p>
      )}

      {/* 📬 Mailbox button with red dot */}
      <button
        onClick={() => navigate("/mailbox")}
        style={{ position: "relative" }}
      >
        Mailbox
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-5px",
              right: "-5px",
              width: "12px",
              height: "12px",
              borderRadius: "50%",
              background: "red",
              display: "inline-block",
            }}
          ></span>
        )}
      </button>

      {/* Chat */}
      <button onClick={() => navigate("/chat")}>Chat</button>

      {/* Logout */}
      <button style={{ background: "#ccc" }} onClick={logout}>
        Log out
      </button>
    </div>
  );
};

export default UserHome;
