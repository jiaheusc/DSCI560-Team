import React, { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const Chat = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);

  const loadGroups = async () => {
    const res = await fetch("/api/chat-groups", {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await res.json();
    setGroups(data.groups || []);
  };

  useEffect(() => { loadGroups(); }, []);

  return (
    <div className="chat-group-list">
      <h3>Your Groups</h3>

      {groups.length === 0 && <p>No groups yet.</p>}

      {groups.map((g) => (
        <button
          key={g.id}
          className="group-btn"
          onClick={() => navigate(`/chat/${g.id}`)}
        >
          <div className="group-name">{g.group_name}</div>
          <div className="group-count">{g.current_size} members</div>
        </button>
      ))}
    </div>
  );
};

export default Chat;
