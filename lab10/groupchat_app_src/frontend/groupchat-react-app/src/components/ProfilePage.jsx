import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

// APIs
import {
  getMyUserProfile,
  updateUserProfile,
  getMyTherapistProfile,
  updateTherapistProfile,
  listAvatars,
  changePassword
} from "../api";

// ---------- CONFIG ----------
const profileConfig = {
  user: {
    load: getMyUserProfile,
    update: updateUserProfile,
    home: "/user",
    fields: [
      { key: "prefer_name", label: "Preferred Name", type: "text" },
      { key: "bio", label: "Bio", type: "textarea" },
    ],
  },

  therapist: {
    load: getMyTherapistProfile,
    update: updateTherapistProfile,
    home: "/therapist",
    fields: [
      { key: "prefer_name", label: "Preferred Name", type: "text" },
      { key: "bio", label: "Bio", type: "textarea" },
      { key: "expertise", label: "Expertise", type: "text" },
      { key: "years_experience", label: "Years Experience", type: "number" },
      { key: "license_number", label: "License Number", type: "text" }
    ],
  }
};

const ProfilePage = () => {
  const { token,role } = useAuth();

  const cfg = profileConfig[role];
  const DEFAULT_AVATAR = "/static/avatars/default.png";
  const [profile, setProfile] = useState({});
  const [edit, setEdit] = useState({});
  const [avatars, setAvatars] = useState([]);

  const [showAvatarPanel, setShowAvatarPanel] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  // LOAD PROFILE + AVATARS
  const load = async () => {
    const p = await cfg.load(token);

    const cleaned = {};
    cfg.fields.forEach(f => cleaned[f.key] = p[f.key] || "");

    cleaned.avatar_url = p.avatar_url || DEFAULT_AVATAR;
    cleaned.created_at = p.created_at ? new Date(p.created_at).toLocaleString() : "";
    cleaned.updated_at = p.updated_at ? new Date(p.updated_at).toLocaleString() : "";

    setProfile(cleaned);
    setEdit(cleaned);

    const av = await listAvatars(token);
    setAvatars(av.avatars || []);
  };

  useEffect(() => {
    load();
  }, []);

  const toastProfile = (msg) => {
    setProfileSuccess(msg);
    setTimeout(() => setProfileSuccess(""), 2000);
  };

  const toastPassword = (msg) => {
    setPasswordSuccess(msg);
    setTimeout(() => setPasswordSuccess(""), 2000);
  };

  const saveProfile = async () => {
    if (!edit.prefer_name || edit.prefer_name.trim() === "") {
      toastProfile("❌ Preferred Name is required");
      return;
    }
    // ---- Number Parsing Logic ----
    const sanitized = { ...edit };

    cfg.fields.forEach(f => {
      if (f.type === "number") {
        if (sanitized[f.key] === "" || sanitized[f.key] === null) {
          sanitized[f.key] = null;  
        } else {
          sanitized[f.key] = Number(sanitized[f.key]); 
        }
      }
    });
    await cfg.update(sanitized, token);
    toastProfile("Profile updated!");
    setTimeout(load, 300);
};


  const saveAvatar = async (url) => {
    await cfg.update({ ...edit, avatar_url: url }, token);
    setShowAvatarPanel(false);
    setTimeout(load, 200);
  };

  const savePassword = async () => {
    try {
      await changePassword(oldPassword, newPassword, token);
      toastPassword("Password updated!");
      setOldPassword("");
      setNewPassword("");
    } catch {
      toastPassword("❌ Wrong password or update failed");
    }
  };

  return (
    <div className="auth">
      {/* Header Row */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        marginBottom: 20,
        alignItems: "center"
      }}>

        <h2 style={{ margin: 0 }}>
          {role === "user" ? "User Profile" : "Therapist Profile"}
        </h2>

        <div style={{ width: 90 }}></div>
      </div>

      {/* Avatar Preview */}
      <div style={{ textAlign: "center", marginBottom: 20 }}>
        <img
          src={profile.avatar_url || "/static/avatars/1.png"}
          alt="avatar"
          style={{
            width: 120, height: 120, borderRadius: "50%",
            objectFit: "cover", border: "3px solid #ddd"
          }}
        />
        <br />
        <button onClick={() => setShowAvatarPanel(true)}>
          Choose Avatar
        </button>
      </div>

      {/* Avatar Panel */}
      {showAvatarPanel && (
        <div style={{ border: "1px solid #ccc", padding: 20, borderRadius: 8 }}>
          <h4>Select Avatar</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {avatars.map((url) => (
              <img
                key={url}
                src={url}
                onClick={() => saveAvatar(url)}
                style={{
                  width: 70, height: 70, borderRadius: "50%",
                  cursor: "pointer",
                  border: "2px solid transparent"
                }}
              />
            ))}
          </div>
          <button onClick={() => setShowAvatarPanel(false)}>Close</button>
        </div>
      )}

      {/* Dynamic Fields */}
      {cfg.fields.map((f) => (
        <div key={f.key}>
          <label>{f.label}</label>

          {f.type === "textarea" ? (
            <textarea
              value={edit[f.key]}
              onChange={(e) => setEdit({ ...edit, [f.key]: e.target.value })}
            />
          ) : (
            <input
              type={f.type}
              value={edit[f.key]}
              onChange={(e) => setEdit({ ...edit, [f.key]: e.target.value })}
            />
          )}
        </div>
      ))}

      <button onClick={saveProfile}>Save Profile</button>

      {profileSuccess && (
        <p style={{
          marginTop: 10,
          padding: 8,
          background: profileSuccess.startsWith("❌") ? "#b33a3a" : "#4caf50",
          color: "white",
          borderRadius: 6
        }}>
          {profileSuccess}
        </p>
      )}

      <hr />
      <h3>Change Password</h3>

      <label>Old Password</label>
      <input
        type="password"
        value={oldPassword}
        onChange={(e) => setOldPassword(e.target.value)}
      />

      <label>New Password</label>
      <input
        type="password"
        value={newPassword}
        onChange={(e) => setNewPassword(e.target.value)}
      />

      <button onClick={savePassword}>Update Password</button>

      {passwordSuccess && (
        <p style={{
          marginTop: 10,
          padding: 8,
          background: passwordSuccess.startsWith("❌") ? "#b33a3a" : "#4caf50",
          color: "white",
          borderRadius: 6
        }}>
          {passwordSuccess}
        </p>
      )}

    </div>
  );
};

export default ProfilePage;
