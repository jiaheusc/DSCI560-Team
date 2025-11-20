import React, { useEffect, useState } from "react";
import {
  getMyProfile,
  updateProfile,
  listAvatars,
  updateAvatar,
  changePassword
} from "../api";
import { useAuth } from "../AuthContext";

const Profile = () => {
  const { token } = useAuth();

  // ALL HOOKS AT TOP LEVEL
  const [profile, setProfile] = useState({});
  const [edit, setEdit] = useState({});
  const [avatars, setAvatars] = useState([]);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [success, setSuccess] = useState("");
  const [showAvatarPanel, setShowAvatarPanel] = useState(false);

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

  const toast = (msg) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(""), 2000);
  };

  const saveProfile = async () => {
    await updateProfile(edit, token);
    toast("Profile updated!");
    load();
  };

  const saveAvatar = async (url) => {
  await updateProfile(
    {
      ...edit,
      avatar_url: url
    },
    token
  );
  toast("Avatar updated!");
  load();
  setShowAvatarPanel(false);
};


  const savePassword = async () => {
    try {
      await changePassword(oldPassword, newPassword, token);
      toast("Password updated!");
      setOldPassword("");
      setNewPassword("");
    } catch {
      toast("❌ Wrong password or update failed");
    }
  };

  return (
    <div className="auth">
      <h2>Therapist Profile</h2>

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

      {success && (
        <p
          style={{
            marginTop: 15,
            padding: 10,
            background: success.startsWith("❌") ? "#b33a3a" : "#4caf50",
            color: "white",
            borderRadius: 6
          }}
        >
          {success}
        </p>
      )}
    </div>
  );
};

export default Profile;
