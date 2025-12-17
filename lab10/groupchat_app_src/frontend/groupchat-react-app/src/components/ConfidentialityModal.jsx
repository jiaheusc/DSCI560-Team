import React from "react";

const ConfidentialityModal = ({ onAgree, onDecline }) => (
    <div className="modal-overlay">
        <div className="modal-box">
            <h2>Confidentiality Agreement</h2>

            <p>
                Before joining the support space, please review the confidentiality guidelines:
            </p>

            <ul className="modal-list">
                <li>You agree to respect other members’ privacy and confidentiality.</li>
                <li>You may encounter emotional or sensitive topics inside the group.</li>
                <li>Your participation is voluntary and you may leave anytime.</li>
                <li>This group is peer support, not a replacement for medical treatment.</li>
            </ul>

            <p>Do you agree to these conditions?</p>

            <div className="modal-buttons">
                <button className="agree-btn" onClick={onAgree}>I Agree</button>
                <button className="decline-btn" onClick={onDecline}>Decline</button>
            </div>
        </div>
    </div>
);

export default ConfidentialityModal;
