import React, { useState, useEffect } from "react";
import { getMailbox, approveUser, markMailRead } from "../api";
import { useAuth } from "../AuthContext";

const Mailbox = () => {
  const { token, role } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState({});

  const load = async () => {
    const data = await getMailbox(token);
    setItems(data);
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = async (id) => {
    // 展开/折叠
    setOpen((prev) => ({ ...prev, [id]: !prev[id] }));

    // 标记为已读
    await markMailRead(id, token);
    load();
  };

  const labels = {
    age: "Age Range",
    gender: "Gender",
    lookingFor: "What They're Looking For",
    struggles: "Current Struggles",
    atmosphere: "Preferred Atmosphere",
    communication: "Communication Preference",
  };

  const formatAnswer = (v) => {
    if (Array.isArray(v)) return v.join(", ");
    if (v === "" || v == null) return "Not specified";
    if (typeof v === "object") return Object.values(v).join(", ");
    return v;
  };

  const handleApprove = async (userId) => {
    await approveUser(userId, token);
    load();
  };

  return (
    <div className="mailbox-container">
      <h2 className="mailbox-header">📬 Mailbox</h2>

      {items.length === 0 && <p>No messages yet.</p>}

      {items.map((m) => (
        <div key={m.id} className="mailbox-card">

          {/* 🔴  */}
          {!m.is_read && (
            <span className="mailbox-unread-dot">●</span>
          )}

          <div className="mailbox-row">
            <strong>From:</strong> {m.from_user}
          </div>

          <div className="mailbox-row">
            <strong>Type:</strong>{" "}
            {m.content.type === "questionnaire" ? "Questionnaire" : "Message"}
          </div>

          <div className="mailbox-row">
            <strong>Received:</strong>{" "}
            {new Date(m.created_at).toLocaleString()}
          </div>


          {/* ------------------ Text message ------------------ */}
          {m.content.type === "text" && (
            <div
              className="mailbox-text"
              onClick={async () => {
                await markMailRead(m.id, token);
                load();
              }}
              style={{ cursor: "pointer" }}
            >
              {m.content.text}
            </div>
          )}

          {/* ---------------- Questionnaire ---------------- */}
          {m.content.type === "questionnaire" && (
            <>
              <button
                className="mailbox-accordion-btn"
                onClick={() => toggle(m.id)}
              >
                {open[m.id] ? "▲ Hide Questionnaire" : "▼ View Questionnaire"}
              </button>

              {open[m.id] && (
                <div className="mailbox-qa-box">
                  {Object.entries(m.content.answers).map(([key, value]) => (
                    <div key={key} className="mailbox-qa-row">
                      <strong>{labels[key] || key}:</strong>{" "}
                      <span>{formatAnswer(value)}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* APPROVE BUTTON */}
              {role === "therapist" && (
                <button
                  className="mailbox-accept-btn"
                  onClick={() => handleApprove(m.from_user)}
                >
                  ✅ Accept User
                </button>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
};

export default Mailbox;
