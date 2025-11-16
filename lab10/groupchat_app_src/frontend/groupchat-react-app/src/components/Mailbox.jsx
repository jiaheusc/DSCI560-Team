import React, { useState, useEffect } from "react";
import { sendMail, getMailbox, replyMail } from "../api";
import { useAuth } from "../AuthContext";

const Mailbox = () => {
  const { token, role } = useAuth();
  const [inbox, setInbox] = useState([]);
  const [message, setMessage] = useState("");

  const load = async () => {
    if (role === "therapist") {
      const data = await getMailbox(token);
      setInbox(data);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const send = async () => {
    await sendMail(message, token);
    setMessage("");
  };

  const reply = async (to_user, text) => {
    await replyMail(to_user, text, token);
    load();
  };

  return (
    <div className="auth">
      <h2>Mailbox</h2>

      {role === "user" && (
        <>
          <textarea
            placeholder="Send a message to therapist"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          <button onClick={send}>Send</button>
        </>
      )}

      {role === "therapist" &&
        inbox.map((m) => (
          <div className="message" key={m.id}>
            <p><strong>From:</strong> User {m.from_user}</p>
            <p>{m.content}</p>

            <button onClick={() => reply(m.from_user, "Thanks, received!")}>
              Quick Reply
            </button>
          </div>
        ))}
    </div>
  );
};

export default Mailbox;
