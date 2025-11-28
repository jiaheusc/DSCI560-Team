import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

import Auth from "./components/Auth";
import Questionnaire from "./components/Questionnaire";
import UserHome from "./components/UserHome";
import TherapistHome from "./components/TherapistHome";
import Mailbox from "./components/Mailbox";
import Chat from "./components/Chat";
import ProfilePage from "./components/ProfilePage";   
import TherapistPublicProfile from "./pages/TherapistPublicProfile";
import AiSummary from "./pages/AiSummary";
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
      <div className="page-container">
        <Routes>

          <Route path="/" element={<Navigate to="/login" />} />

          <Route path="/login" element={<Auth />} />

          <Route path="/questionnaire" element={requireRole(<Questionnaire />, "user")} />

          {/* USER HOME */}
          <Route path="/user" element={requireRole(<UserHome />, "user")} />

          {/* THERAPIST HOME */}
          <Route path="/therapist" element={requireRole(<TherapistHome />, "therapist")} />

          {/*  Profile (user + therapist) */}
          <Route path="/profile" element={requireAuth(<ProfilePage />)} />

          {/* Public therapist view */}
          <Route path="/therapist-profile/:id" element={<TherapistPublicProfile />} />

          {/* Shared mailbox */}
          <Route path="/mailbox" element={requireAuth(<Mailbox />)} />

          {/* Shared chat */}
          <Route path="/chat" element={requireAuth(<Chat />)} />
          {/* AI Summary (therapist) */}
          <Route path="/ai-summary" element={<AiSummary />} />

          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
