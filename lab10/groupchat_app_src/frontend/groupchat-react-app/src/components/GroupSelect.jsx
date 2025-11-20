// GroupSelect.jsx
import React, { useEffect, useState } from "react";
import { getChatGroups, createGroup } from "../api";
import { useAuth } from "../AuthContext";

const GroupSelect = ({ setView, setSelectedGroupId }) => {
    const { token } = useAuth();
    const [groups, setGroups] = useState([]);
    const [name, setName] = useState("");

    // -----------------------------
    // Load all chat groups
    // -----------------------------
    const loadGroups = async () => {
        const data = await getChatGroups(token);
        setGroups(data.groups || []);   
    };

    // -----------------------------
    // Create new group
    // -----------------------------
    const handleCreate = async () => {
        if (!name.trim()) return;
        await createGroup(name, token);
        setName("");
        loadGroups();
    };

    useEffect(() => {
        loadGroups();
    }, []);

    return (
        <div className="group-select-container">
            <h2>Select Group</h2>

            {/* Group list */}
            {groups.map((g) => (
                <div
                    key={g.id}
                    className="group-item"
                    onClick={() => {
                        setSelectedGroupId(g.id);  
                        setView("chat");
                    }}
                >
                    {g.name}   
                </div>
            ))}

            {/* Create group */}
            <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="New group name"
            />
            <button onClick={handleCreate}>Create</button>
        </div>
    );
};

export default GroupSelect;
