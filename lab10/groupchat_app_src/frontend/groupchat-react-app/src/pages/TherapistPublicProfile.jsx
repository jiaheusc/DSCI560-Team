import React, { useEffect, useState } from "react";
import { getPublicTherapistProfile } from "../api";
import { useParams, useNavigate } from "react-router-dom";

const TherapistPublicProfile = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getPublicTherapistProfile(id);  
        setInfo(data);
      } catch (err) {
        setError(err.detail || "Unable to load therapist profile.");
      }
    };
    load();
  }, [id]);

  if (error)
    return (
      <div className="auth" style={{ padding: 20 }}>
        <p style={{ color: "red" }}>{error}</p>
        <button onClick={() => navigate(-1)}>← Back</button>
      </div>
    );

  if (!info) return <p style={{ padding: 20 }}>Loading...</p>;

  return (
    <div className="auth">
      <button onClick={() => navigate(-1)} style={{ marginBottom: 15 }}>
        ← Back
      </button>

      <h2>{info.prefer_name || info.username}</h2>

      <img
        src={info.avatar_url || "/static/avatars/1.png"}
        alt=""
        style={{
          width: 120,
          height: 120,
          borderRadius: "50%",
          objectFit: "cover",
          border: "3px solid #ddd",
          marginBottom: 20
        }}
      />

      <p><strong>Bio:</strong></p>
      <p>{info.bio || "No bio yet."}</p>

      <p><strong>Expertise:</strong> {info.expertise || "N/A"}</p>
      <p><strong>Years Experience:</strong> {info.years_experience}</p>
      <p><strong>License:</strong> {info.license_number || "N/A"}</p>
    </div>
  );
};

export default TherapistPublicProfile;
