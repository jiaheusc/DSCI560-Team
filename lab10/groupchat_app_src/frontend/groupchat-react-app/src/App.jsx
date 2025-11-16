import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

import Auth from "./components/Auth";
import Questionnaire from "./components/Questionnaire";
import UserHome from "./components/UserHome";
import TherapistHome from "./components/TherapistHome";
import Mailbox from "./components/Mailbox";
import Chat from "./components/Chat";
import Profile from "./components/Profile";

const App = () => {
  const { token, role } = useAuth();

  const requireAuth = (element) => {
    return token ? element : <Navigate to="/login" />;
  };

  return (
    <BrowserRouter>
      <div className="page-container">

        <Routes>
          {/* Default */}
          <Route path="/" element={<Navigate to="/login" />} />

          {/* Login page */}
          <Route path="/login" element={<Auth />} />

          {/* Questionnaire (user fills after signup) */}
          <Route
            path="/questionnaire"
            element={requireAuth(<Questionnaire />)}
          />

          {/* USER HOME */}
          <Route
            path="/user"
            element={requireAuth(
              role === "user" ? <UserHome /> : <Navigate to="/login" />
            )}
          />

          {/* THERAPIST HOME */}
          <Route
            path="/therapist"
            element={requireAuth(
              role === "therapist" ? <TherapistHome /> : <Navigate to="/login" />
            )}
          />

          {/* Shared pages */}
          <Route path="/mailbox" element={requireAuth(<Mailbox />)} />
          <Route path="/chat" element={requireAuth(<Chat />)} />
          <Route path="/profile" element={requireAuth(<Profile />)} />

          {/* Not found → redirect */}
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>

      </div>
    </BrowserRouter>
  );
};

export default App;
