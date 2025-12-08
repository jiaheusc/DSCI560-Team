import React from "react";
import ReactDOM from "react-dom/client";
import { AuthProvider } from "./AuthContext";
import App from "./App";
import "./styles.css"; 
import "antd/dist/reset.css";
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <AuthProvider>
    <App />
  </AuthProvider>
);
