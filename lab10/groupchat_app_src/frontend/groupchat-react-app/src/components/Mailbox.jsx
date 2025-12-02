import React, { useState, useEffect } from "react";
import { getMailbox, getTherapistUserProfile, getUserGroups,sendMail,addUserToGroup,createAutoGroup,approveUser, markMailRead,getMailPartner } from "../api";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";
const Mailbox = () => {
  const { token, role } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState({});
  const [showSend, setShowSend] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [recipient, setRecipient] = useState(null);
  const [msg, setMsg] = useState("");
  const [status, setStatus] = useState("");
  const [userGroups, setUserGroups] = useState({});
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

    // 从 messages 提取需要 check 的用户 ID（questionnaire）
    const usersToCheck = data.messages
      .filter(m => m.content.type === "questionnaire")
      .map(m => m.from_user);

    // 去重
    const uniqueUsers = [...new Set(usersToCheck)];

    // 批量请求每个用户的 group 信息
    const results = {};
    for (const uid of uniqueUsers) {
      try {
        const g = await getUserGroups(uid, token);
        results[uid] = g.groups || [];
      } catch {
        results[uid] = [];
      }
    }

    // 保存
    setUserGroups(results);
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

  const handleApprove = async (mailItem) => {
    const userId = mailItem.from_user;
    const username = mailItem.from_name || `user_${userId}`;

    const rec = mailItem.content?.recommendation;

    if (!rec) {
      alert("No AI recommendation found.");
      return;
    }

    try {
      let finalGroupId = null;

      // Case 1 — system detected no groups configured
      if (rec.decision === "no_groups_configured") {
        const gid = await createAutoGroup(username, token);
        finalGroupId = gid;
        console.log("✔ Created new group:", gid);
      }

      // Case 2 — AI recommended new group
      else if (rec.decision === "new_group") {
        const gid = await createAutoGroup(username, token);
        finalGroupId = gid;
        console.log("✔ Created AI recommended new group:", gid);
      }

      // Case 3 — AI recommended existing group
      else if (rec.decision === "group" && rec.group_id) {
        await addUserToGroup(rec.group_id, username, token);
        finalGroupId = rec.group_id;
        console.log("✔ Added user to existing group:", rec.group_id);
      }

      await approveUser(userId, token);

      alert(`User approved and assigned to group ${finalGroupId}`);

      load(); // refresh mailbox

    } catch (err) {
      console.error("Approve error:", err);
      alert("❌ Failed to approve user or assign group.");
    }
  };

  const handleRejectCreateGroup = async (mailItem) => {
    const userId = mailItem.from_user;
    const username = mailItem.from_name || `user_${userId}`;
    let finalGroupId = null;
    const gid = await createAutoGroup(username, token);
    finalGroupId = gid;
    alert("✔ Created new group", gid);
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
      <div className="mailbox-header-bar"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20
        }}
      >

        {/* Title */}
        <h2 style={{ margin: 0 }}>Mailbox</h2>

        {/* placeholder 保持居中对齐 */}
        <div style={{ width: 90 }}></div>
      </div>

      <div className="mailbox-header-row">
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
                  onClick={() => {
                    toggle(m.id, m.is_read);
                  }}
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
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: "10px",
      marginTop: "10px",
    }}
  >
    {(() => {
      const groups = userGroups[m.from_user] || [];
      const alreadyInGroup = groups.length < 0;

      return (
        <>
          <button
            className="mailbox-accept-btn"
            disabled={alreadyInGroup}
            onClick={() => !alreadyInGroup && handleApprove(m)}
            style={{
              opacity: alreadyInGroup ? 0.5 : 1,
              cursor: alreadyInGroup ? "not-allowed" : "pointer",
            }}
          >
            Accept User
          </button>

          <button
            className="mailbox-reject-btn"
            disabled={alreadyInGroup}
            onClick={() => !alreadyInGroup && handleRejectCreateGroup(m)}
            style={{
              opacity: alreadyInGroup ? 0.5 : 1,
              cursor: alreadyInGroup ? "not-allowed" : "pointer",
            }}
          >
            Reject, Create Group
          </button>

          {alreadyInGroup && (
            <span style={{ color: "#888", fontSize: 13 }}>
              User already in group
            </span>
          )}
        </>
      );
    })()}
  </div>
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
