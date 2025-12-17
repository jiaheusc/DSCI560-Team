import { useAuth } from "../AuthContext";

const Message = ({ message }) => {
    const { userId } = useAuth();
    const isMe = message.sender_id === userId;

    return (
        <div className={`chat-msg ${isMe ? "me" : "other"}`}>
            <div className="chat-msg-user">{message.sender_name}</div>
            <div className="chat-msg-text">{message.text}</div>
            <div className="chat-msg-time">
                {new Date(message.created_at).toLocaleTimeString()}
            </div>
        </div>
    );
};

export default Message;
