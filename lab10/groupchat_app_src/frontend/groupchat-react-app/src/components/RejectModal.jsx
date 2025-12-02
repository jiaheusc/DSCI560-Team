import React, { useState } from "react";

const RejectModal = ({
  visible,
  onClose,
  mailItem,
  token,
  createAutoGroup,
  addUserToGroup,
  approveUser,
  reloadMailbox,
}) => {
  const [selectedGroupOption, setSelectedGroupOption] = useState(null);

  if (!visible || !mailItem) return null;

  const rec = mailItem.content?.recommendation;
  const tops = rec?.top_candidates || [];

  const handleConfirm = async () => {
    const userId = mailItem.from_user;
    const username = mailItem.from_name || `user_${userId}`;

    try {
      let finalGroupId = null;

      if (selectedGroupOption === "new") {
        const gid = await createAutoGroup(username, token);
        finalGroupId = gid;
      } else {
        finalGroupId = Number(selectedGroupOption);
        await addUserToGroup(finalGroupId, username, token);
      }

      await approveUser(userId, token);

      alert(`Assigned user to group ${finalGroupId}`);

      onClose();
      reloadMailbox();
    } catch (err) {
      console.error(err);
      alert("❌ Failed to assign group");
    }
  };

  return (
    <div
      className="mailbox-modal-overlay"
      style={{
        position: "fixed",     // ⭐ 必须：让 modal 覆盖整个屏幕
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        background: "rgba(0, 0, 0, 0.45)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 9999,          // ⭐ 必须：压在所有内容上面
      }}
    >
      <div
        className="mailbox-modal-box"
        style={{
          background: "#fff",
          padding: "24px",
          borderRadius: "10px",
          width: "420px",
          maxHeight: "85vh",
          overflowY: "auto",
          boxShadow: "0 6px 18px rgba(0, 0, 0, 0.25)",
        }}
      >
        <h3 style={{ marginTop: 0 }}>Reject & Assign Group</h3>

        <p>Select a group for this user, or create a new one.</p>

        <div style={{ marginBottom: 12 }}>
          <strong>Top Candidates:</strong>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {tops.length === 0 && (
            <div style={{ fontSize: 14, color: "#777" }}>
              No candidate groups available.
            </div>
          )}

          {tops.map(([gid, sim]) => (
            <div
              key={gid}
              onClick={() => setSelectedGroupOption(gid)}
              style={{
                padding: "12px",
                borderRadius: "10px",
                border:
                  selectedGroupOption === gid
                    ? "2px solid #3A7AFE"
                    : "1px solid #ddd",
                background:
                  selectedGroupOption === gid ? "#eef4ff" : "#fff",
                cursor: "pointer",
                boxShadow:
                  selectedGroupOption === gid
                    ? "0 0 8px rgba(58,122,254,0.3)"
                    : "0 1px 4px rgba(0,0,0,0.08)",
                transition: "0.2s",
              }}
            >
              <div style={{ fontWeight: "bold", fontSize: 16 }}>
                Group {gid}
              </div>
              <div style={{ fontSize: 14 }}>
                <strong>Similarity:</strong> {sim}
              </div>
            </div>
          ))}

          {/* Create new group */}
          <div
            onClick={() => setSelectedGroupOption("new")}
            style={{
              padding: "12px",
              borderRadius: "10px",
              border:
                selectedGroupOption === "new"
                  ? "2px solid #3A7AFE"
                  : "1px solid #ddd",
              background:
                selectedGroupOption === "new" ? "#eef4ff" : "#fff",
              cursor: "pointer",
              textAlign: "center",
              fontWeight: "bold",
              boxShadow:
                selectedGroupOption === "new"
                  ? "0 0 8px rgba(58,122,254,0.3)"
                  : "0 1px 4px rgba(0,0,0,0.08)",
            }}
          >
            ➕ Create New Group
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
          <button
            className="modal-btn-primary"
            disabled={!selectedGroupOption}
            onClick={handleConfirm}
          >
            Confirm
          </button>

          <button className="modal-btn-secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default RejectModal;
