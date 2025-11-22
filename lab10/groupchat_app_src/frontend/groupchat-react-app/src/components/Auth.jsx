// Auth.jsx
import React, { useState } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";
import ConfidentialityModal from "./ConfidentialityModal";

import {
    api,
    getMyUserProfile,
    getUserProfileStatus,
    listTherapists,
    getMyTherapistProfile,
    getUserProfileStatus as userProfileStatusAPI
} from "../api";

const Auth = () => {
  const { login, signup, authMsg } = useAuth();
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [localError, setLocalError] = useState("");
  const [showConsent, setShowConsent] = useState(false);

  const navigate = useNavigate();

  const goNextByToken = async (jwtToken) => {
    if (!jwtToken) return;

    const payload = JSON.parse(atob(jwtToken.split(".")[1]));

    // ========================
    // USER LOGIN FLOW
    // ========================
    if (payload.role === "user") {
      try {
        // 1. Questionnaire?
        const q = await api(`/user/questionnaire`, "GET", null, jwtToken);
        if (!q.ok) {
          navigate("/questionnaire");
          return;
        }

        // 2. Has therapist?
        const t = await api(`/user/me/therapist`, "GET", null, jwtToken);
        if (!t.has_therapist) {
          navigate("/user");
          return;
        }

        // 3. User profile exists?
        const prof = await getUserProfileStatus(jwtToken);
        if (!prof.ok) {
          navigate("/profile");
          return;
        }

        // 4. All good → user home
        navigate("/user");
        return;

      } catch (err) {
        console.log("Login status check failed:", err);
        navigate("/user");
      }
    }

    // ========================
    // THERAPIST LOGIN FLOW
    // ========================
    if (payload.role === "therapist") {
      try {
        const prof = await api("/therapist/profile/status", "GET", null, jwtToken);
        if (!prof.ok) {
          navigate("/therapist/profile");
          return;
        }
        navigate("/therapist");
        return;
      } catch (err) {
        navigate("/profile");
      }
    }

    if (payload.role === "operator") {
      navigate("/admin");
      return;
    }

    navigate("/questionnaire");
  };

  // LOGIN
  const handleLogin = async () => {
    setLocalError("");

    const jwt = await login(u, p);
    if (jwt) goNextByToken(jwt);
  };

  // SIGNUP → open modal
  const handleSignup = () => {
    setLocalError("");

    if (!u || !p) {
      setLocalError("Username and password required.");
      return;
    }
    setShowConsent(true);
  };

  // modal agree → real signup
  const handleAgree = async () => {
    setShowConsent(false);

    const jwt = await signup(u, p);
    if (jwt) goNextByToken(jwt);
  };

  const handleDecline = () => {
    setShowConsent(false);
    setLocalError("You must agree to the confidentiality agreement.");
  };

  return (
    <div className="card auth">
      {showConsent && (
        <ConfidentialityModal
          onAgree={handleAgree}
          onDecline={handleDecline}
        />
      )}

      <h2>Welcome</h2>

      <input
        className="auth-input"
        placeholder="Username"
        value={u}
        onChange={(e) => setU(e.target.value)}
      />
      <input
        className="auth-input"
        placeholder="Password"
        type="password"
        value={p}
        onChange={(e) => setP(e.target.value)}
      />

      <button onClick={handleLogin}>Log In</button>
      <button onClick={handleSignup}>Sign Up</button>

      {(localError || authMsg) && (
        <p className="error-message">{localError || authMsg}</p>
      )}
    </div>
  );
};

export default Auth;
