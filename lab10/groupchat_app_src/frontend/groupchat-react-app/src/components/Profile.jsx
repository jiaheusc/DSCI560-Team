import React, { useEffect, useState } from "react";
import { getMyProfile, updateProfile } from "../api";
import { useAuth } from "../AuthContext";

const Profile = () => {
  const { token } = useAuth();
  const [profile, setProfile] = useState({});
  const [edit, setEdit] = useState({});

  const load = async () => {
    const data = await getMyProfile(token);
    setProfile(data);
    setEdit(data);
  };

  const save = async () => {
    await updateProfile(edit, token);
    load();
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="auth">
      <h2>Therapist Profile</h2>

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

      <button onClick={save}>Save</button>
    </div>
  );
};

export default Profile;
