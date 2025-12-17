import { useEffect, useRef } from 'react';

const useWebSocket = (token, onMessage) => {
  const ws = useRef(null);

  useEffect(() => {
    if (!token) return;

    const connectWS = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const gid = localStorage.getItem('group_id');
      ws.current = new WebSocket(`${proto}://${window.location.host}/ws?token=${token}`);

      ws.current.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === 'message' && data.message.group_id === gid) {
            onMessage(data.message);
          }
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      ws.current.onclose = () => setTimeout(connectWS, 2000);
    };

    connectWS();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [token, onMessage]);

  return ws;
};

export default useWebSocket;