import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const AiSummary = () => {
  const { token } = useAuth();
  const [patients, setPatients] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const navigate = useNavigate();
  // Time range
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Placeholder summary output
  const [summary, setSummary] = useState("");

  // Load therapist's users
  const loadUsers = async () => {
    try {
      const data = await api("/therapist/my-users", "GET", null, token);
      setPatients(data.users || []);
    } catch (err) {
      console.error("load users error:", err);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleGenerate = () => {
    setSummary(
      `Summary (Mock)\nUser: ${selectedUser}\nDuration: ${startDate} → ${endDate}\n\n(Waiting backend summary API...)`
    );
  };

  return (
    <div className="auth" style={{ padding: 20 }}>

      {/* Top Header Row */}
        <div
        style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20
        }}
        >
        {/* Back Home button */}
        <button
            onClick={() => navigate("/therapist")}
            style={{
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid #ccc",
            cursor: "pointer"
            }}
        >
            ← Home
        </button>

        {/* Title */}
        <h2 style={{ margin: 0 }}>AI Summary</h2>

        {/* empty placeholder to align center */}
        <div style={{ width: 90 }}></div>
        </div>


      {/* Patient selector */}
      <label style={{ marginTop: 20 }}>Select Patient</label>
      <select
        value={selectedUser || ""}
        onChange={(e) => setSelectedUser(e.target.value)}
        style={{ padding: 8 }}
      >
        <option value="">-- choose a patient --</option>
        {patients.map((p) => (
          <option key={p.id} value={p.id}>
            {p.prefer_name || p.username}
          </option>
        ))}
      </select>

      {/* Time Range */}
      <label style={{ marginTop: 20 }}>Start Date</label>
      <input
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
      />

      <label style={{ marginTop: 10 }}>End Date</label>
      <input
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
      />

      {/* Generate */}
      <button
        style={{ marginTop: 20 }}
        onClick={handleGenerate}
        disabled={!selectedUser || !startDate || !endDate}
      >
        Generate Summary
      </button>

      {/* Display summary */}
      {summary && (
        <div
          style={{
            marginTop: 30,
            padding: 15,
            borderRadius: 8,
            background: "#f5f5f5",
            whiteSpace: "pre-wrap"
          }}
        >
          {summary}
        </div>
      )}
    </div>
  );
};

export default AiSummary;
