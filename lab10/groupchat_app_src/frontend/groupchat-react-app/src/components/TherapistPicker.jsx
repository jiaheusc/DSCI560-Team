import React, { useEffect, useState } from "react";
import { listTherapists, assignTherapist } from "../api";
import { useAuth } from "../AuthContext";

const TherapistPicker = ({ onClose, onChosen }) => {
  const { token } = useAuth();
  const [therapists, setTherapists] = useState([]);
  const [viewProfile, setViewProfile] = useState(null); // profile modal

  useEffect(() => {
    const load = async () => {
      const data = await listTherapists(token);
      setTherapists(data.therapists);
    };
    load();
  }, []);

  const choose = async (id) => {
    await assignTherapist(id, token);
    onChosen();
  };

  return (
    <div className="modal-overlay">
      <div className="modal-window">

        <h3>Select a Therapist</h3>

        {therapists.map(t => (
          <div key={t.id} className="therapist-row">
            <span
              onClick={() => setViewProfile(t)}
              style={{ color: "blue", textDecoration: "underline", cursor: "pointer" }}
            >
              {t.prefer_name || t.username}
            </span>

            <button onClick={() => choose(t.id)}>Select</button>
          </div>
        ))}

        <button onClick={onClose} className="close-btn">Close</button>


        {/* ================= PROFILE MODAL ================ */}
        {viewProfile && (
          <div className="modal-overlay">
            <div className="modal-window small">

              <button
                className="close-btn"
                onClick={() => setViewProfile(null)}
              >
                ×
              </button>

              <h3>{viewProfile.prefer_name || viewProfile.username}</h3>

              <img
                src={viewProfile.avatar_url || "/static/avatars/1.png"}
                alt=""
                style={{
                  width: 100,
                  height: 100,
                  borderRadius: "50%",
                  objectFit: "cover",
                  marginBottom: 15
                }}
              />

              <p><strong>Expertise:</strong> {viewProfile.expertise || "N/A"}</p>
              <p><strong>Experience:</strong> {viewProfile.years_experience}</p>
              <p><strong>License:</strong> {viewProfile.license_number || "N/A"}</p>
              <p><strong>Bio:</strong><br /> {viewProfile.bio || "No bio yet."}</p>

              <button
                style={{ marginTop: 10 }}
                onClick={() => choose(viewProfile.id)}
              >
                Select This Therapist
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default TherapistPicker;
