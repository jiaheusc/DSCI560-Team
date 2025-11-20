// Auth.jsx
import React, { useState } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";
import ConfidentialityModal from "./ConfidentialityModal";

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

        if (payload.role === "user") {

            const r = await fetch("/api/user/questionnaire", {
                headers: { Authorization: `Bearer ${jwtToken}` }
            });
            const q = await r.json();

            if (!q.ok) {
                navigate("/questionnaire");
                return;
            }

            const r2 = await fetch("/api/user/me/therapist", {
                headers: { Authorization: `Bearer ${jwtToken}` }
            });
            const t = await r2.json();

            if (!t.has_therapist) {
                navigate("/user");  
                return;               
            }

            navigate("/user");
        }

        else if (payload.role === "therapist") navigate("/therapist");
        else if (payload.role === "operator") navigate("/admin");
        else navigate("/questionnaire");
    };

    // LOGIN
    const handleLogin = async () => {
        setLocalError("");

        const jwt = await login(u, p);  // jwt is real token

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

        const jwt = await signup(u, p);   // jwt is real token

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
