import React, { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate } from "react-router-dom";

const Chat = () => {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [groups, setGroups] = useState([]);
  // groupId -> members 数组
  const [groupMembers, setGroupMembers] = useState({});

  useEffect(() => {
    const loadData = async () => {
      // 1) 先拿到我的所有群
      const res = await fetch("/api/chat-groups", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      const gs = data.groups || [];
      setGroups(gs);

      // 2) 再把每个群的 members 拉一下，做成一个 map
      const membersMap = {};

      await Promise.all(
        gs.map(async (g) => {
          try {
            const r = await fetch(`/api/chat-groups/${g.id}/members`, {
              headers: { Authorization: `Bearer ${token}` }
            });
            if (!r.ok) return;
            const md = await r.json();
            membersMap[g.id] = md.members || [];
          } catch (e) {
            // 忽略单个 group 的错误
          }
        })
      );

      setGroupMembers(membersMap);
    };

    loadData();
  }, [token]);

  return (
    <div className="chat-group-list">
      <h3>Your Groups</h3>

      {groups.length === 0 && <p>No groups yet.</p>}

      {groups.map((g) => {
        const members = groupMembers[g.id] || [];
        const showMembers = members.slice(0, 4); // 只显示前 4 个头像
        const moreCount = members.length - showMembers.length;

        return (
          <button
            key={g.id}
            className="group-btn"
            onClick={() => navigate(`/chat/${g.id}`)}
          >
            <div className="group-name">{g.group_name}</div>

            {/* ✅ 成员头像行 */}
            <div className="group-members-row">
              {showMembers.map((m) => {
                const name = m.prefer_name || m.username || "";
                const initial = name ? name.charAt(0).toUpperCase() : "?";

                return m.avatar_url ? (
                  <img
                    key={m.user_id}
                    src={m.avatar_url}
                    alt={name}
                    title={name}
                    className="group-avatar"
                  />
                ) : (
                  <div
                    key={m.user_id}
                    className="group-avatar group-avatar-fallback"
                    title={name}
                  >
                    {initial}
                  </div>
                );
              })}

              {moreCount > 0 && (
                <span className="group-members-more">+{moreCount}</span>
              )}
            </div>

            <div className="group-count">
              {(members.length || g.current_size || 0)} members
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default Chat;
