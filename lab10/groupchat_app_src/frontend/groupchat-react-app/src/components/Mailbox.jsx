import React, { useState, useEffect } from "react";
import { getMailbox, approveUser, markMailRead } from "../api";
import { useAuth } from "../AuthContext";

const Mailbox = () => {
  const { token, role } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState({});

  const load = async () => {
    const data = await getMailbox(token);
    setItems(data.messages);  
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = async (id, is_read) => {
    const nowOpen = !open[id];
    setOpen((prev) => ({ ...prev, [id]: nowOpen }));

    if (nowOpen && !is_read) {
      await markMailRead(id, token);
      load();
    }
  };

  const handleApprove = async (userId) => {
    await approveUser(userId, token);   
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

  return (
    <div className="mailbox-container">
      <h2 className="mailbox-header">📬 Mailbox</h2>

      {items.length === 0 && <p>No messages yet.</p>}

      {items.map((m) => (
        <div key={m.id} className="mailbox-card">

          {!m.is_read && (<span className="mailbox-unread-dot">●</span>)}

          <div className="mailbox-row"><strong>From:</strong> {m.from_user}</div>
          <div className="mailbox-row"><strong>Type:</strong> {m.content.type}</div>
          <div className="mailbox-row">
            <strong>Received:</strong> {new Date(m.created_at).toLocaleString()}
          </div>

          {m.content.type === "approval" && (
            <div
              className="mailbox-text"
              style={{
                background: "#e8fce8",
                border: "1px solid #8ddf8d",
                padding: "10px",
                borderRadius: "6px",
                marginTop: "8px",
                fontWeight: "bold",
                color: "#2f7d2f"
              }}
              onClick={async () => {
                if (!m.is_read) {
                  await markMailRead(m.id, token);
                }
                load();
              }}
            >
              {m.content.message || "Your questionnaire has been approved!"}
            </div>
          )}
          {/* Questionnaire */}
          {m.content.type === "questionnaire" && (
            <>
              <button
                className="mailbox-accordion-btn"
                onClick={() => toggle(m.id, m.is_read)}
              >
                {open[m.id] ? "▲ Hide Questionnaire & AI Recommendation" : "▼ View Questionnaire & AI Recommendation"}
              </button>

              {open[m.id] && (
                <div className="mailbox-qa-box">

                  {/* ========== AI Recommendation ========== */}
                  {m.content.recommendation && (
                    <div className="mailbox-qa-box" style={{ marginBottom: 10 }}>
                      <div className="mailbox-qa-row">
                        <strong>AI Recommended Group</strong>
                      </div>

                      <div className="mailbox-qa-row">
                        <strong>Decision:</strong> {m.content.recommendation.decision}
                      </div>

                      {m.content.recommendation.group_id && (
                        <div className="mailbox-qa-row">
                          <strong>Group ID:</strong> {m.content.recommendation.group_id}
                        </div>
                      )}

                      <div className="mailbox-qa-row">
                        <strong>Score:</strong> {m.content.recommendation.score}
                      </div>

                      <div className="mailbox-qa-row">
                        <strong>Threshold:</strong> {m.content.recommendation.threshold}
                      </div>

                      <div className="mailbox-qa-row">
                        <strong>Reason:</strong> {m.content.recommendation.reason}
                      </div>

                      {/* Top Candidates */}
                      {m.content.recommendation.top_candidates &&
                      m.content.recommendation.top_candidates.length > 0 && (
                        <div className="mailbox-qa-row">
                          <strong>Top Candidates:</strong>
                          <ul style={{ paddingLeft: 18, marginTop: 4 }}>
                            {m.content.recommendation.top_candidates.map(([gid, sim]) => (
                              <li key={gid}>Group {gid} ({sim})</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}


                  {/* ========== All questionnaire answers ========== */}
                  <div className="mailbox-qa-box" style={{ marginTop: 12 }}>
  
                    <div className="mailbox-qa-row">
                      <strong>Questionnaire Answers</strong>
                    </div>

                    {Object.entries(m.content.answers || {}).map(([key, value]) => (
                      <div key={key} className="mailbox-qa-row">
                        <strong>{labels[key] || key}:</strong>
                        <span>{formatAnswer(value)}</span>
                      </div>
                    ))}

                  </div>
                </div>
              )}


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
          
          {/* Text mail */}
          {m.content.type === "text" && (
            <div
              className="mailbox-text"
              onClick={async () => {
                if (!m.is_read) {
                  await markMailRead(m.id, token);
                }
                load();
              }}
            >
              {m.content.text}
            </div>
          )}

        </div>
      ))}
    </div>
  );
};

export default Mailbox;
