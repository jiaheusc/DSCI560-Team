import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useFontSize } from "../context/FontSizeContext";
import { useAuth } from "../AuthContext";

const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { fontSize, changeFontSize } = useFontSize();
  const { logout } = useAuth();

  const path = location.pathname;

  // Case 1: inside a chat room (/chat/123)
  const isChatRoom = /^\/chat\/\d+/.test(path);

  // Case 2: show generic Home button
  const showBackHomeGeneral = [
    "/chat",
    "/mailbox",
    "/profile",
    "/ai-summary",
  ].some((p) => path === p);

  // Case 3: show Logout
  const showLogout = ["/user", "/therapist"].some((p) =>
    path.startsWith(p)
  );

  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 20px",
        background: "#f7f7f7",
        borderBottom: "1px solid #ddd",
        position: "sticky",
        top: 0,
        zIndex: 1000,
      }}
    >
      {/* Left side button */}
      <div>
        {isChatRoom && (
          <button onClick={() => navigate("/chat")} style={btn}>
            ← Back to Groups
          </button>
        )}

        {!isChatRoom && showBackHomeGeneral && (
          <button onClick={() => navigate("/")} style={btn}>
            ← Home
          </button>
        )}
      </div>

      {/* Font Size */}
      <div>
        <button
          style={fontSizeBtn(fontSize === "small")}
          onClick={() => changeFontSize("small")}
        >
          A-
        </button>
        <button
          style={fontSizeBtn(fontSize === "medium")}
          onClick={() => changeFontSize("medium")}
        >
          A
        </button>
        <button
          style={fontSizeBtn(fontSize === "large")}
          onClick={() => changeFontSize("large")}
        >
          A+
        </button>
      </div>

      {/* Logout */}
      <div>
        {showLogout && (
          <button
            onClick={() => {
              logout();
              navigate("/auth");
            }}
            style={btn}
          >
            Logout
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;

const btn = {
  padding: "6px 12px",
  marginRight: "10px",
  cursor: "pointer",
};

const fontSizeBtn = (active) => ({
  padding: "6px 12px",
  margin: "0 5px",
  border: active ? "2px solid #000" : "1px solid #aaa",
  borderRadius: "4px",
  cursor: "pointer",
  color: active ? "#000" : "#555",
  background: active ? "#e2e2e2" : "#fff",
});
