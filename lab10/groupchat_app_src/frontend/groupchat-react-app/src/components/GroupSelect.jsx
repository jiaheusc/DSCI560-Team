import React, { useEffect, useState } from "react";
import { getChatGroups, createGroup } from "../api";
import { useAuth } from "../AuthContext";

const GroupSelect = ({ setView }) => {
    const { token } = useAuth();
    const [groups, setGroups] = useState([]);
    const [name, setName] = useState("");

    const loadGroups = async () => {
        const data = await getChatGroups(token);
        setGroups(data);
    };

    const create = async () => {
        await createGroup(name, token);
        loadGroups();
    };

    useEffect(() => {
        loadGroups();
    }, []);

    return (
        <div>
            <h2>Select Group</h2>

            {groups.map((g) => (
                <div key={g.id} onClick={() => setView("chat")} className="group-item">
                    {g.group_name}
                </div>
            ))}

            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New group name" />
            <button onClick={create}>Create</button>
        </div>
    );
};

export default GroupSelect;
