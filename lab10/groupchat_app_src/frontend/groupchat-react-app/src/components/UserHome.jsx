import React from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const UserHome = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="auth">
      <h2>User Home</h2>

      <p>Your questionnaire has been submitted. Waiting for therapist approval.</p>

      <button onClick={() => navigate("/mailbox")}>Mailbox</button>
      <button onClick={() => navigate("/chat")}>Chat</button>

      <button style={{ background: "#ccc" }} onClick={logout}>
        Log out
      </button>
    </div>
  );
};

export default UserHome;
