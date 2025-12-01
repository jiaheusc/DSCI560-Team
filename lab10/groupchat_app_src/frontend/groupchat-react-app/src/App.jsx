import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

import Header from "./components/Header";
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
        <Header />  {/* 全局 Header（会自动隐藏在 login 页） */}

        <div className="page-container">
          <Routes>
            <Route path="/" element={<Navigate to="/login" />} />

            <Route path="/login" element={<Auth />} />

            <Route path="/questionnaire" element={requireRole(<Questionnaire />, "user")} />

            {/* USER HOME */}
            <Route path="/user" element={requireRole(<UserHome />, "user")} />

            {/* THERAPIST HOME */}
            <Route path="/therapist" element={requireRole(<TherapistHome />, "therapist")} />

            {/* Profile */}
            <Route path="/profile" element={requireAuth(<ProfilePage />)} />

            {/* Public therapist */}
            <Route path="/therapist-profile/:id" element={<TherapistPublicProfile />} />

            {/* Mailbox */}
            <Route path="/mailbox" element={requireAuth(<Mailbox />)} />

            {/* Chat */}
            <Route path="/chat" element={requireAuth(<Chat />)} />
            <Route path="/chat/:groupId" element={requireAuth(<ChatRoom />)} />
            {/* AI Summary */}
            <Route path="/ai-summary" element={<AiSummary />} />

            <Route path="*" element={<Navigate to="/login" />} />
          </Routes>
        </div>
      </FontSizeProvider>
    </BrowserRouter>
  );
};

export default App;
