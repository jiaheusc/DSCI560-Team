import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

import Auth from "./components/Auth";
import Questionnaire from "./components/Questionnaire";
import UserHome from "./components/UserHome";
import TherapistHome from "./components/TherapistHome";
import Mailbox from "./components/Mailbox";
import Chat from "./components/Chat";

import Profile from "./components/Profile";                 // therapist private profile
import TherapistPublicProfile from "./pages/TherapistPublicProfile";
import UserProfile from "./pages/UserProfile";

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

          {/* Default */}
          <Route path="/" element={<Navigate to="/login" />} />

          {/* Login */}
          <Route path="/login" element={<Auth />} />

          {/* Questionnaire (user only) */}
          <Route
            path="/questionnaire"
            element={requireRole(<Questionnaire />, "user")}
          />

          {/* USER HOME */}
          <Route
            path="/user"
            element={requireRole(<UserHome />, "user")}
          />

          {/* USER PROFILE */}
          <Route
            path="/user/profile"
            element={requireRole(<UserProfile />, "user")}
          />

          {/* THERAPIST HOME */}
          <Route
            path="/therapist"
            element={requireRole(<TherapistHome />, "therapist")}
          />

          {/* THERAPIST private profile (edit profile) */}
          <Route
            path="/therapist/profile"
            element={requireRole(<Profile />, "therapist")}
          />

          {/* PUBLIC therapist profile (view only) */}
          <Route
            path="/therapist-profile/:id"
            element={<TherapistPublicProfile />}
          />

          {/* Mailbox (shared by both) */}
          <Route
            path="/mailbox"
            element={requireAuth(<Mailbox />)}
          />

          {/* Chat (shared by both) */}
          <Route
            path="/chat"
            element={requireAuth(<Chat />)}
          />

          {/* Not found */}
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
};

export default App;
