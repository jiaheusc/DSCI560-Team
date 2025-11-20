// AuthContext.js
import React, { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [role, setRole] = useState(localStorage.getItem("role") || "");
  const [userId, setUserId] = useState(localStorage.getItem("userId") || "");
  const [authMsg, setAuthMsg] = useState("");

  // -----------------------------
  // Decode JWT
  // -----------------------------
  const parseJwt = (token) => {
    try {
      const base64 = token.split(".")[1];
      return JSON.parse(atob(base64));
    } catch {
      return {};
    }
  };

  // -----------------------------
  // Save JWT to state + storage
  // -----------------------------
  const saveAuth = (jwtToken) => {
    const payload = parseJwt(jwtToken);

    setToken(jwtToken);
    setRole(payload.role);
    setUserId(payload.user_id);

    localStorage.setItem("token", jwtToken);
    localStorage.setItem("role", payload.role);
    localStorage.setItem("userId", payload.user_id);
  };

  // -----------------------------
  // LOGIN
  // -----------------------------
  const login = async (username, password) => {
    setAuthMsg("");

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

      saveAuth(data.token);
      return data.token;

    } catch {
      setAuthMsg("Network error");
      return false;
    }
  };

  // -----------------------------
  // SIGNUP
  // -----------------------------
  const signup = async (username, password) => {
    setAuthMsg("");

    try {
      const res = await fetch("/api/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });

      const data = await res.json();

      if (!res.ok) {
        setAuthMsg(data.detail || "Signup failed");
        return false;
      }

      saveAuth(data.token);
      return data.token;

    } catch {
      setAuthMsg("Network error");
      return false;
    }
  };

  // -----------------------------
  // LOGOUT
  // -----------------------------
  const logout = () => {
    setToken("");
    setRole("");
    setUserId("");
    setAuthMsg("");
    localStorage.clear();
  };

  return (
    <AuthContext.Provider
      value={{ token, role, userId, authMsg, login, signup, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
