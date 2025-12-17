import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function useUserEvents() {
  const { token, userId } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Approval event
      if (data.type === "approved") {
        navigate(`/chat/${data.group_id}`);
      }
    };

    return () => ws.close();
  }, [token]);
}
