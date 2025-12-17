import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const AiSummary = () => {
  const { token } = useAuth();
  const [patients, setPatients] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [expandedIndex, setExpandedIndex] = useState(null);

  // Time range
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [userGroups, setUserGroups] = useState([]);
  // Placeholder summary output
  const [summaries, setSummaries] = useState([]);
  const [dateError, setDateError] = useState("");

  const [selectedGroup, setSelectedGroup] = useState("");
  // Load therapist's users
  const loadUsers = async () => {
    try {
      const data = await api("/therapist/my-users", "GET", null, token);
      setPatients(data.users || []);
    } catch (err) {
      console.error("load users error:", err);
    }
  };
  const validateDates = (start, end) => {
    const today = new Date().toISOString().split("T")[0];

    if (!start || !end) {
      setDateError("");
      return false;
    }

    // no future dates
    if (start > today || end > today) {
      setDateError("Dates cannot be in the future.");
      return false;
    }

    // end >= start
    if (end < start) {
      setDateError("End date cannot be earlier than start date.");
      return false;
    }

    setDateError(""); // no errors
    return true;
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleGenerate = async () => {
    if (!selectedUser || !selectedGroup || !startDate || !endDate) return;
    if (!validateDates(startDate, endDate)) return;
    try {
      const data = await api(
        `/therapist/users/${selectedUser}/groups/${selectedGroup}/summaries?start_date=${startDate}&end_date=${endDate}`,
        "GET",
        null,
        token
      );

      setSummaries(data.summaries || []);
    } catch (err) {
      console.error("summary error:", err);
      setSummaries([]);
    }
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

        {/* Title */}
        <h2 style={{ margin: 0 }}>AI Summary</h2>

        {/* empty placeholder to align center */}
        <div style={{ width: 90 }}></div>
        </div>


      {/* Patient selector */}
      <label style={{ marginTop: 20 }}>Select Patient</label>
      <select
        value={selectedUser || ""}
        onChange={async (e) => {
          const uid = e.target.value;
          setSelectedUser(uid);

          setSummaries("");       // reset summary
          setSelectedGroup(""); // reset group selector
          setUserGroups([]);    // clear previous groups

          if (!uid) return;

          try {
            const data = await api(`/therapist/users/${uid}/groups`, "GET", null, token);
            setUserGroups(data.groups || []);
          } catch (err) {
            console.error("load user groups error:", err);
          }
        }}
        style={{ padding: 8 }}
      >


        <option value="">-- choose a patient --</option>
        {patients.map((p) => (
          <option key={p.id} value={p.id}>
            {p.prefer_name || p.username}
          </option>
        ))}
      </select>
        {/* Group selector */}
        {selectedUser && (
          <>
            <label style={{ marginTop: 20 }}>Select Group</label>
            <select
              value={selectedGroup}
              onChange={(e) => setSelectedGroup(e.target.value)}
              style={{ padding: 8 }}
            >
              <option value="">-- choose a group --</option>
              {userGroups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.group_name}
                </option>
              ))}
            </select>
          </>
        )}
      {/* Time Range */}
      <label style={{ marginTop: 20 }}>Start Date</label>
      <input
        type="date"
        value={startDate}
        onChange={(e) => {
          setStartDate(e.target.value);
          validateDates(e.target.value, endDate);
        }}
      />

      <label style={{ marginTop: 10 }}>End Date</label>
      <input
          type="date"
          value={endDate}
          onChange={(e) => {
            setEndDate(e.target.value);
            validateDates(startDate, e.target.value);
          }}
        />

      {/* Generate */}
      <button
        disabled={!selectedUser || !selectedGroup || !startDate || !endDate ||dateError !== ""}
        style={{
          marginTop: 20,
          opacity: (!selectedUser || !selectedGroup || !startDate || !endDate) ? 0.5 : 1,
          cursor: (!selectedUser || !selectedGroup || !startDate || !endDate)
            ? "not-allowed"
            : "pointer"
        }}
        onClick={handleGenerate}
      >
        Generate Summary
      </button>
      {/* Date error */}
      {dateError && (
        <p style={{ fontSize: 14, color: "red", marginTop: 10 }}>{dateError}</p>
      )}

      {/* Display summary */}
      {/* Summary Cards */}
{summaries.length === 0 && (
  <p style={{ marginTop: 20, color: "#666" }}>
    No summary found for this date range.
  </p>
)}

{summaries.length > 0 && (
  <div style={{ marginTop: 20 }}>
    {summaries.map((s, idx) => {
      const isOpen = expandedIndex === idx;

      return (
        <div
          key={idx}
          onClick={() => setExpandedIndex(isOpen ? null : idx)}
          style={{
            marginBottom: 15,
            padding: "15px 18px",
            border: "1px solid #ddd",
            borderRadius: 10,
            cursor: "pointer",
            background: "#fafafa",
            transition: "all 0.2s",
            boxShadow: isOpen
              ? "0 2px 8px rgba(0,0,0,0.15)"
              : "0 1px 3px rgba(0,0,0,0.1)"
          }}
        >
          {/* Title row */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center"
            }}
          >
            <strong style={{ fontSize: 16 }}>
              {new Date(s.summary_date).toLocaleDateString()}
            </strong>

            {/* Simple mood icon */}
            <span style={{ fontSize: 18 }}>
              {s.mood === "happy" && "😊"}
              {s.mood === "sad" && "😢"}
              {s.mood === "angry" && "😡"}
              {s.mood === "neutral" && "😐"}
              {!s.mood && "📝"}
            </span>
          </div>

          {/* Collapsible content */}
          {isOpen && (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ marginBottom: 5 }}>Mood</h4>
              <p>{s.mood || <i>No mood recorded</i>}</p>

              <h4 style={{ marginTop: 10, marginBottom: 5 }}>Summary</h4>
              <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                {s.summary_text}
              </p>
            </div>
          )}
        </div>
      );
    })}
  </div>
)}


    </div>
  );
};

export default AiSummary;
