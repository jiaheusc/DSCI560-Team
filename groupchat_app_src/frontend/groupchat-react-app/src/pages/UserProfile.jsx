import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthContext";
import {
  getMyUserProfile,
  createUserProfile,
  updateUserProfile
} from "../api";

const UserProfile = () => {
  const { token } = useAuth();

  // ALL HOOKS AT TOP LEVEL
  const [edit, setEdit] = useState({ prefer_name: "", bio: "" });
  const [exists, setExists] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getMyUserProfile(token);

        if (data?.profile) {
          setEdit(data.profile);
          setExists(true);
        } else {
          setExists(false);
        }
      } catch {
        setExists(false);
      }
      setLoading(false);
    };

    load();
  }, []);

  const save = async () => {
    if (exists) {
      await updateUserProfile(edit, token);
    } else {
      await createUserProfile(edit, token);
      setExists(true);
    }
    alert("Profile saved.");
  };

  if (loading) return <p className="auth">Loading...</p>;

  return (
    <div className="auth">
      <h2>User Profile</h2>

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

      <button onClick={save}>Save</button>
    </div>
  );
};

export default UserProfile;
