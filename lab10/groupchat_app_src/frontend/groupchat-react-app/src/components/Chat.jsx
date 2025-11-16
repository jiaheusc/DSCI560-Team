import React, { useEffect, useState } from "react";
import { getChatGroups, getMessages, sendMessageToGroup } from "../api";
import { useAuth } from "../AuthContext";

const Chat = () => {
  const { token, userId } = useAuth();
  const [groups, setGroups] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");

  const loadGroups = async () => {
    const g = await getChatGroups(token);
    setGroups(g);
    if (g.length > 0) setSelected(g[0].id);
  };

  const loadMessagesNow = async () => {
    if (selected)
      setMessages((await getMessages(selected, token)).messages);
  };

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    loadMessagesNow();
  }, [selected]);

  const send = async () => {
    await sendMessageToGroup(text, selected, token);
    setText("");
    loadMessagesNow();
  };

  return (
    <div className="auth">
      <h2>Group Chat</h2>

      <select value={selected || ""} onChange={(e) => setSelected(Number(e.target.value))}>
        {groups.map((g) => (
          <option key={g.id} value={g.id}>{g.group_name}</option>
        ))}
      </select>

      <div className="messages">
        {messages.map((m) => (
          <div key={m.id} className="message">
            <p><strong>{m.username}</strong></p>
            <p>{m.content}</p>
          </div>
        ))}
      </div>

      <textarea value={text} onChange={(e) => setText(e.target.value)} />
      <button onClick={send}>Send</button>
    </div>
  );
};

export default Chat;
