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

    // Navigate based on role inside token
    const goNextByToken = (token) => {
        if (!token) return;

        const payload = JSON.parse(atob(token.split(".")[1])); // decode JWT
        
        if (payload.role === "user") navigate("/questionnaire");
        else if (payload.role === "therapist") navigate("/therapist");
        else if (payload.role === "operator") navigate("/admin");
        else navigate("/questionnaire");
    };

    // LOGIN
    const handleLogin = async () => {
        setLocalError("");

        const ok = await login(u, p);

        if (ok) {
            goNextByToken(localStorage.getItem("token"));
        }
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

    // modal agree → do real signup
    const handleAgree = async () => {
        setLocalError("");
        setShowConsent(false);

        const ok = await signup(u, p);

        if (ok) {
            goNextByToken(localStorage.getItem("token"));
        }
    };

    // modal decline
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
