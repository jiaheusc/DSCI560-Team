import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import TherapistPicker from "./TherapistPicker";

const UserHome = () => {
  const { token } = useAuth();
  const [needsTherapist, setNeedsTherapist] = useState(false);
  const [showPicker, setShowPicker] = useState(false);

  // ===== Check if user has a therapist =====
  const checkTherapist = async () => {
    try {
      const res = await fetch("/api/user/me/therapist", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();

      if (!data.has_therapist) {
        setNeedsTherapist(true);
        setShowPicker(true);
      } else {
        setNeedsTherapist(false);
        setShowPicker(false);
      }

    } catch (err) {
      console.error("Failed to check therapist:", err);
    }
  };

  useEffect(() => {
    if (token) checkTherapist();
  }, [token]);

  // ===== Chosen therapist =====
  const handleTherapistChosen = () => {
    setShowPicker(false);
    setNeedsTherapist(false);
  };

  return (
    <div className="auth"
        style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",    
        alignItems: "center" 
      }}>
      <h2>User Home</h2>
      {/* Therapist picker popup */}
      {showPicker && (
        <TherapistPicker
          onClose={() => setShowPicker(false)}
          onChosen={handleTherapistChosen}
        />
      )}

      {needsTherapist ? (
        <p style={{ color: "red", marginBottom: 20 }}>
          You must select a therapist before entering the chat.
        </p>
      ) : (<p>Welcome!</p>
      )}

      {!needsTherapist && (
        <>
          <button onClick={() => (window.location.href = "/profile")}>
            Edit Profile
          </button>

          <button onClick={() => (window.location.href = "/mailbox")}>
            Mailbox
          </button>

          <button onClick={() => (window.location.href = "/chat")}>
            Chat
          </button>
        </>
      )}

    </div>
  );
};

export default UserHome;
