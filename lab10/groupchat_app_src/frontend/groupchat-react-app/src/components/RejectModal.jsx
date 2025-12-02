import React, { useState } from "react";

const RejectModal = ({
  visible,
  onClose,
  mailItem,
  token,
  createAutoGroup,
  addUserToGroup,
  approveUser,
  reloadMailbox
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
        // create new group
        const gid = await createAutoGroup(username, token);
        finalGroupId = gid;
      } else {
        // choose existing group
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
    <div className="mailbox-modal-overlay">
      <div className="mailbox-modal-box">
        <h3>Reject & Assign Group</h3>

        <p>Select a group for this user, or create a new one.</p>

        {/* Top candidates */}
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
            <label key={gid} style={{ cursor: "pointer" }}>
              <input
                type="radio"
                name="reject-group"
                value={gid}
                checked={selectedGroupOption === gid}
                onChange={() => setSelectedGroupOption(gid)}
                style={{ marginRight: 6 }}
              />
              Group {gid} (sim: {sim})
            </label>
          ))}

          {/* new group */}
          <label style={{ cursor: "pointer", marginTop: 6 }}>
            <input
              type="radio"
              name="reject-group"
              value="new"
              checked={selectedGroupOption === "new"}
              onChange={() => setSelectedGroupOption("new")}
              style={{ marginRight: 6 }}
            />
            ➕ Create New Group
          </label>
        </div>

        {/* Buttons */}
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
