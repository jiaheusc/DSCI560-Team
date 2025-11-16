import React, { useEffect, useState } from "react";
import { getMailbox, approveUser } from "../api";
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

  const approve = async (userId) => {
    await approveUser(userId, token);
    load();
  };

  return (
    <div className="auth">
      <h2>Therapist Dashboard</h2>

      <button onClick={() => navigate("/profile")}>Edit Profile</button>
      <button onClick={() => navigate("/chat")}>Chat</button>

      <h3>Pending User Approvals</h3>

      {messages.length === 0 && <p>No pending approvals.</p>}

      {messages.map((m) => (
        <div key={m.id} className="message">
          <p><strong>From:</strong> User {m.from_user}</p>
          <p>{m.content}</p>

          <button onClick={() => approve(m.from_user)}>Approve User</button>
        </div>
      ))}

      <button style={{ background: "#ccc" }} onClick={logout}>
        Log out
      </button>
    </div>
  );
};

export default TherapistHome;
