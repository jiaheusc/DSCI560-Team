import React, { useEffect, useState } from "react";
import {
  getMyProfile,
  updateProfile,
  listAvatars,
  changePassword
} from "../api";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";
const Profile = () => {
  const { token } = useAuth();

  // ALL HOOKS AT TOP LEVEL
  const [profile, setProfile] = useState({});
  const [edit, setEdit] = useState({});
  const [avatars, setAvatars] = useState([]);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [profileSuccess, setProfileSuccess] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [showAvatarPanel, setShowAvatarPanel] = useState(false);
  const navigate = useNavigate();
  const load = async () => {
    const p = await getMyProfile(token);
    const cleaned = {
      prefer_name: p.prefer_name || "",
      bio: p.bio || "",
      expertise: p.expertise || "",
      years_experience: p.years_experience ?? "",
      license_number: p.license_number || "",
      avatar_url: p.avatar_url || ""
    };

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
    await updateProfile(edit, token);
    toastProfile("Profile updated!");
    setTimeout(() => load(), 200);
  };

  const saveAvatar = async (url) => {
  await updateProfile(
    {
      ...edit,
      avatar_url: url
    },
    token
  );
  setTimeout(() => load(), 200);
  setShowAvatarPanel(false);
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
      {/* HEADER ROW */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        {/* Back Home Button - same style as avatar button */}
        <button
          onClick={() => navigate("/therapist")}
          style={{
            padding: "8px 14px",
            border: "1px solid #ccc",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          ← Home
        </button>

        <h2 style={{ margin: 0 }}>Therapist Profile</h2>

        <div style={{ width: 90 }}></div>
      </div>


      {/* Avatar Preview */}
      <div style={{ textAlign: "center", marginBottom: 20 }}>
        <img
          src={profile.avatar_url || "/static/avatars/1.png"}
          alt="avatar"
          style={{
            width: 120,
            height: 120,
            borderRadius: "50%",
            objectFit: "cover",
            border: "3px solid #ddd"
          }}
        />
        <br />
        <button onClick={() => setShowAvatarPanel(true)}>Choose Avatar</button>
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
                  width: 70,
                  height: 70,
                  borderRadius: "50%",
                  cursor: "pointer",
                  border: "2px solid transparent"
                }}
              />
            ))}
          </div>

          <button onClick={() => setShowAvatarPanel(false)}>Close</button>
        </div>
      )}

      <label>Preferred Name</label>
      <input
        value={edit.prefer_name || ""}
        onChange={(e) => setEdit({ ...edit, prefer_name: e.target.value })}
      />

      <label>Bio</label>
      <textarea
        value={edit.bio || ""}
        onChange={(e) => setEdit({ ...edit, bio: e.target.value })}
      />

      <label>Expertise</label>
      <input
        value={edit.expertise || ""}
        onChange={(e) => setEdit({ ...edit, expertise: e.target.value })}
      />

      <label>Years Experience</label>
      <input
        type="number"
        value={edit.years_experience || ""}
        onChange={(e) => setEdit({ ...edit, years_experience: e.target.value })}
      />

      <label>License Number</label>
      <input
        value={edit.license_number || ""}
        onChange={(e) => setEdit({ ...edit, license_number: e.target.value })}
      />

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

export default Profile;
