// src/App.jsx
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

import { FontSizeProvider } from "./context/FontSizeContext";

import Auth from "./components/Auth";
import Questionnaire from "./components/Questionnaire";
import UserHome from "./components/UserHome";
import TherapistHome from "./components/TherapistHome";
import Mailbox from "./components/Mailbox";
import Chat from "./components/Chat";
import ProfilePage from "./components/ProfilePage";
import TherapistPublicProfile from "./pages/TherapistPublicProfile";
import AiSummary from "./pages/AiSummary";
import ChatRoom from "./pages/ChatRoom";

import AppLayout from "./AppLayout";

const App = () => {
  const { token, role } = useAuth();

  const requireAuth = (element) => {
    if (!token) return <Navigate to="/login" />;
    return element;
  };

  const requireRole = (element, required) => {
    if (!token) return <Navigate to="/login" />;
    if (role !== required) return <Navigate to="/login" />;
    return element;
  };

  return (
    <BrowserRouter>
      <FontSizeProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/login" />} />

          {/* 登录页：不套布局 */}
          <Route path="/login" element={<Auth />} />

          {/* 公共 therapist profile，如果你想也可以挪进 Layout 里 */}
          <Route
            path="/therapist-profile/:id"
            element={<TherapistPublicProfile />}
          />

          {/* 下面所有路由都套在 AppLayout（Header + Sider）里 */}
          <Route element={<AppLayout />}>
            <Route
              path="/questionnaire"
              element={requireRole(<Questionnaire />, "user")}
            />
            <Route
              path="/user"
              element={requireRole(<UserHome />, "user")}
            />
            <Route
              path="/therapist"
              element={requireRole(<TherapistHome />, "therapist")}
            />
            <Route path="/profile" element={requireAuth(<ProfilePage />)} />
            <Route path="/mailbox" element={requireAuth(<Mailbox />)} />
            <Route path="/chat" element={requireAuth(<Chat />)} />
            <Route
              path="/chat/:groupId"
              element={requireAuth(<ChatRoom />)}
            />
            <Route path="/ai-summary" element={<AiSummary />} />
          </Route>

          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </FontSizeProvider>
    </BrowserRouter>
  );
};

export default App;
