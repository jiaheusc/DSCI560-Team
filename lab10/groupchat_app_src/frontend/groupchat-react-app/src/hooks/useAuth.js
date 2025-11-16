import { useState } from "react";

const useAuth = () => {
    const [token, setToken] = useState(localStorage.getItem("token") || "");
    const [role, setRole] = useState(localStorage.getItem("role") || "");
    const [authMsg, setAuthMsg] = useState("");

    const saveAuth = (token, role) => {
        localStorage.setItem("token", token);
        localStorage.setItem("role", role);
        setToken(token);
        setRole(role);
        setAuthMsg("");
    };

    const clearAuth = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("role");
        setToken("");
        setRole("");
    };

    // ----------------------
    // LOGIN
    // ----------------------
    const login = async (username, password) => {
    try {
        const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json(); 

        if (!res.ok) {
            setAuthMsg(data.detail || "Login failed");
            return false;
        }

        // backend returns: { ok: true, token: "...", role: "user" }
        saveAuth(data.token, data.role);
        return true;
    } catch (err) {
        setAuthMsg("Network error");
        return false;
    }
};


    // ----------------------
    // SIGNUP
    // ----------------------
    const signup = async (username, password) => {
        try {
            const res = await fetch("/api/signup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });

            if (!res.ok) {
                const err = await res.json();
                setAuthMsg(err.detail || "Signup failed");
                return false;
            }

            const data = await res.json();
            saveAuth(data.token, data.role);
            return true;
        } catch (err) {
            setAuthMsg(err.message);
            return false;
        }
    };

    const logout = () => clearAuth();

    return { token, role, authMsg, login, signup, logout };
};

export default useAuth;
