import React, { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [role, setRole] = useState(localStorage.getItem("role") || "");
  const [userId, setUserId] = useState(localStorage.getItem("userId") || "");
  const [authMsg, setAuthMsg] = useState("");   // ⭐ 登录/注册错误消息

  // ----------------------------------
  // SAVE AUTH (统一封装)
  // ----------------------------------
  const saveAuth = (jwtToken, userRole) => {
    const payload = parseJwt(jwtToken);

    setToken(jwtToken);
    setRole(payload.role);
    setUserId(payload.user_id);

    localStorage.setItem("token", jwtToken);
    localStorage.setItem("role", payload.role);
    localStorage.setItem("userId", payload.user_id);
  };

  // ----------------------------------
  // LOGIN
  // ----------------------------------
  const login = async (username, password) => {
    setAuthMsg(""); // reset

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        const err = await res.json();
        setAuthMsg(err.detail || "Login failed");
        return false;
      }

      const data = await res.json();
      saveAuth(data.token, data.role);
      return true;

    } catch (err) {
      setAuthMsg("Network error");
      return false;
    }
  };

  // ----------------------------------
  // SIGNUP
  // ----------------------------------
  const signup = async (username, password) => {
    setAuthMsg("");

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
      setAuthMsg("Network error");
      return false;
    }
  };

  // ----------------------------------
  // LOGOUT
  // ----------------------------------
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

// ----------------------------------
// Helper: decode JWT
// ----------------------------------
function parseJwt(token) {
  const base64 = token.split(".")[1];
  return JSON.parse(atob(base64));
}
