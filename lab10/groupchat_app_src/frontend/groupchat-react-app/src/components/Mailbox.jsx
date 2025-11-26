import React, { useState, useEffect } from "react";
import { getMailbox, getTherapistUserProfile, sendMail,approveUser, markMailRead,getMailPartner } from "../api";
import { useAuth } from "../AuthContext";
const Mailbox = () => {
  const { token, role } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState({});
  const [showSend, setShowSend] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [recipient, setRecipient] = useState(null);
  const [msg, setMsg] = useState("");
  const [status, setStatus] = useState("");
  const loadUserPartner = async () => {
    if (role !== "user") return; 
    
    const data = await getMailPartner(token);  
    if (data.ok) {
      setRecipient({
        id: data.partner_id,
        name: data.name
      });
    }
  };
  const lookupUser = async () => {
    if (!targetId) return;
    try {
      const data = await getTherapistUserProfile(targetId, token);
      setRecipient({
        id: data.user_id,   
        name: data.prefer_name || data.username || `User ${data.user_id}`
      });
      setStatus("");
    } catch {
      setRecipient(null);
      setStatus("❌ User not found");
    }
  };

  const doSend = async () => {
    if (!msg.trim()) {
      setStatus("❌ Message cannot be empty");
      return;
    }

    const result = await sendMail({
      target_id: Number(targetId),
      message: msg
    }, token);

    if (result.ok) {
      setStatus("✅ Sent!");
      setMsg("");
      setTimeout(() => {
        setShowSend(false);
        load(); // refresh mailbox
      }, 800);
    } else {
      setStatus("❌ Failed to send");
    }
  };
  const load = async () => {
    const data = await getMailbox(token);
    setItems(data.messages);  
  };

  useEffect(() => {
    load();
    if (role === "user") {
      loadUserPartner();
    }
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
      <div className="mailbox-header-row">
        <h2 className="mailbox-header">📬 Mailbox</h2>
        <button className="mailbox-send-btn" onClick={() => setShowSend(true)}>
          Send
        </button>
        {showSend && (
          <div className="mailbox-modal-overlay">
            <div className="mailbox-modal-box">
              <h3>Send Message</h3>

              {/* USER VERSION (auto target) */}
              {role === "user" && recipient && (
                <p>
                  Sending to: <strong>{recipient.name}</strong>
                </p>
              )}

              {/* THERAPIST VERSION (search required) */}
              {role === "therapist" && (
                <>
                  <label>Recipient User ID</label>
                  <input
                    type="number"
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                  />
                  <button onClick={lookupUser}>Lookup User</button>

                  {recipient && (
                    <p>
                      Sending to: <strong>{recipient.name}</strong>
                    </p>
                  )}
                </>
              )}

              {/* MESSAGE BOX */}
              <label>Message</label>
              <textarea
                value={msg}
                onChange={(e) => setMsg(e.target.value)}
                style={{ height: 80 }}
              />

              {/* BUTTONS */}
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                <button
                  disabled={!recipient}
                  onClick={async () => {
                    if (!msg.trim()) return setStatus("❌ Message cannot be empty");

                    const result = await sendMail(
                      {
                        target_id: role === "user" ? recipient.id : Number(targetId),
                        message: msg
                      },
                      token
                    );

                    if (result.ok) {
                      setStatus("✅ Sent!");
                      setMsg("");
                      setTimeout(() => {
                        setShowSend(false);
                        load();
                      }, 800);
                    } else {
                      setStatus("❌ Failed to send");
                    }
                  }}
                >
                  Send
                </button>
                <button onClick={() => setShowSend(false)}>Cancel</button>
              </div>

              {status && (
                <p
                  style={{
                    marginTop: 10,
                    color: status.startsWith("❌") ? "red" : "green",
                  }}
                >
                  {status}
                </p>
              )}
            </div>
          </div>
        )}


      </div>


      {items.length === 0 && <p>No messages yet.</p>}

      {items.map((m) => (
        <div key={m.id} className="mailbox-card">

          {!m.is_read && (<span className="mailbox-unread-dot">●</span>)}

          <div className="mailbox-row"><strong>From:</strong> {m.from_name}</div>
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
          {["text", "direct_message"].includes(m.content.type) && (
            <div
              className="mailbox-text"
              style={{
                padding: "10px",
                borderRadius: "6px",
                marginTop: "8px",
              }}
              onClick={async () => {
                if (!m.is_read) {
                  await markMailRead(m.id, token);
                  load();
                }
              }}
            >
              {/* Display content */}
              <div style={{ marginBottom: 6 }}>
                {m.content.text || m.content.message || "(No content)"}
              </div>

              {/* Reply button for both user and therapist */}
              <button
                style={{
                  fontSize: "13px",
                  padding: "4px 8px",
                  cursor: "pointer"
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  setShowSend(true);

                  if (role === "user") {
                    // USER MUST reply to fixed therapist
                    if (!recipient) {
                      setStatus("❌ No therapist assigned yet");
                      setShowSend(false);
                      return;
                    }

                    setRecipient({
                      id: recipient.id,
                      name: recipient.name
                    });
                    setTargetId(recipient.id);
                  } else {
                    // THERAPIST replying directly to a user
                    setRecipient({
                      id: m.from_user,
                      name: m.from_name || `User ${m.from_user}`
                    });
                    setTargetId(m.from_user);
                  }
                }}

              >
                ↩ Reply
              </button>
            </div>
          )}



        </div>
      ))}
    </div>
  );
};

export default Mailbox;
