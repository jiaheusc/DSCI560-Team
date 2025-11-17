import React, { useEffect, useState } from "react";
import { getPublicTherapistProfile } from "../api";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

const TherapistPublicProfile = () => {
  const { id } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [info, setInfo] = useState(null);

  useEffect(() => {
    const load = async () => {
      const data = await getPublicTherapistProfile(id, token);
      setInfo(data);
    };
    load();
  }, [id]);

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
