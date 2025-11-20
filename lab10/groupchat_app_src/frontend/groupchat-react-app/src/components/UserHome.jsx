import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import TherapistPicker from "./TherapistPicker";
import { assignTherapist, getMailbox, sendMail } from "../api";

const UserHome = () => {
  const { token, logout } = useAuth();
  const [needsTherapist, setNeedsTherapist] = useState(false);
  const [showPicker, setShowPicker] = useState(false);

  // ======= STEP 1: Check if user has therapist =======
  const checkTherapist = async () => {
    try {
      const res = await fetch("/api/user/me/therapist", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();

      if (!data.has_therapist) {
        setNeedsTherapist(true);
        setShowPicker(true);  // auto open modal
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

  // ======= When user selects therapist from modal =======
  const handleTherapistChosen = () => {
    setShowPicker(false);
    setNeedsTherapist(false);
  };

  return (
    <div className="auth">

      <h2>User Home</h2>

      {/* Auto-popup therapist picker */}
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
      ) : (
        <p>Your questionnaire has been submitted.</p>
      )}

      {/* Buttons visible only after therapist selected */}
      {!needsTherapist && (
        <>
          <button onClick={() => (window.location.href = "/mailbox")}>
            Mailbox
          </button>

          <button onClick={() => (window.location.href = "/chat")}>
            Chat
          </button>
        </>
      )}

      <button style={{ background: "#ccc", marginTop: 20 }} onClick={logout}>
        Log out
      </button>
    </div>
  );
};

export default UserHome;
