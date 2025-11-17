import React from 'react';

const Message = ({ message }) => {
    return (
        <div className={`message ${message.is_bot ? 'bot' : ''}`}>
            <div className="meta">
                {`${message.username || 'unknown'} • ${new Date(message.created_at).toLocaleString()}`}
            </div>
            <div className="body">
                {message.content}
            </div>
        </div>
    );
};

export default Message;