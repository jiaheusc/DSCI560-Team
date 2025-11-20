import React, { useState } from "react";
import { submitQuestionnaire } from "../api";
import { useAuth } from "../AuthContext";
import TherapistPicker from "./TherapistPicker";
import { useNavigate } from "react-router-dom"; 

const Questionnaire = () => {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [showTherapistPopup, setShowTherapistPopup] = useState(false);
  const [errors, setErrors] = useState({});

  // Fields
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [lookingFor, setLookingFor] = useState([]);
  const [struggles, setStruggles] = useState([]);
  const [atmosphere, setAtmosphere] = useState("");
  const [communication, setCommunication] = useState("");

  const toggleSelect = (value, setter, list) => {
    if (list.includes(value)) setter(list.filter((v) => v !== value));
    else setter([...list, value]);
  };

  // Submit
  const submit = async () => {
    const newErrors = {};

    if (!age) newErrors.age = "Please select your age group.";
    if (!gender) newErrors.gender = "Please select your gender.";
    if (lookingFor.length === 0) newErrors.lookingFor = "Please select at least one option.";
    if (struggles.length === 0) newErrors.struggles = "Please select at least one option.";
    if (!atmosphere) newErrors.atmosphere = "Please choose one option.";
    if (!communication) newErrors.communication = "Please choose one option.";

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const answers = {
      age,
      gender,
      lookingFor,
      struggles,
      atmosphere,
      communication
    };

    await submitQuestionnaire(answers, token);

    setShowTherapistPopup(true);
  };

  return (
    <div className="card">
      <h2>Health & Wellness Questionnaire</h2>

      {/* Age */}
      <div className={`question-block ${errors.age ? "error" : ""}`}>
        <p className="question"><strong>Age Group</strong></p>
        {["18–25", "26–40", "41–60", "60+"].map(item => (
          <label key={item}>
            <input
              type="radio"
              name="age"
              onChange={() => {
                setAge(item);
                setErrors(prev => ({ ...prev, age: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.age && <p className="error-message">{errors.age}</p>}
      </div>

      {/* Gender */}
      <div className={`question-block ${errors.gender ? "error" : ""}`}>
        <p className="question"><strong>Gender</strong></p>
        {["Male", "Female", "Other", "Prefer not to say"].map(item => (
          <label key={item}>
            <input
              type="radio"
              name="gender"
              onChange={() => {
                setGender(item);
                setErrors(prev => ({ ...prev, gender: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.gender && <p className="error-message">{errors.gender}</p>}
      </div>

      {/* Looking For */}
      <div className={`question-block ${errors.lookingFor ? "error" : ""}`}>
        <p className="question"><strong>What are you mainly looking for?</strong></p>
        {[
          "Someone to listen and understand me",
          "A place to vent or let feelings out",
          "Advice or practical suggestions",
          "Emotional support and encouragement",
          "Calm company and quiet presence",
          "Not sure yet, I just want to try"
        ].map(item => (
          <label key={item}>
            <input
              type="checkbox"
              checked={lookingFor.includes(item)}
              onChange={() => {
                toggleSelect(item, setLookingFor, lookingFor);
                setErrors(prev => ({ ...prev, lookingFor: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.lookingFor && <p className="error-message">{errors.lookingFor}</p>}
      </div>

      {/* Struggles */}
      <div className={`question-block ${errors.struggles ? "error" : ""}`}>
        <p className="question"><strong>Current struggles</strong></p>
        {[
          "Stress from school or work",
          "Relationship or friendship issues",
          "Family or partner conflicts",
          "Feeling anxious or overwhelmed",
          "Feeling sad, numb or low-energy",
          "Loneliness or lack of connection",
          "Low confidence or self-doubt",
          "General confusion about life direction"
        ].map(item => (
          <label key={item}>
            <input
              type="checkbox"
              checked={struggles.includes(item)}
              onChange={() => {
                toggleSelect(item, setStruggles, struggles);
                setErrors(prev => ({ ...prev, struggles: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.struggles && <p className="error-message">{errors.struggles}</p>}
      </div>

      {/* Atmosphere */}
      <div className={`question-block ${errors.atmosphere ? "error" : ""}`}>
        <p className="question"><strong>Your preferred group atmosphere</strong></p>
        {[
          "Warm & gentle",
          "Real & direct",
          "Light & humorous",
          "Calm & slow"
        ].map(item => (
          <label key={item}>
            <input
              type="radio"
              name="atmosphere"
              onChange={() => {
                setAtmosphere(item);
                setErrors(prev => ({ ...prev, atmosphere: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.atmosphere && <p className="error-message">{errors.atmosphere}</p>}
      </div>

      {/* Communication */}
      <div className={`question-block ${errors.communication ? "error" : ""}`}>
        <p className="question"><strong>Preferred communication style</strong></p>
        {[
          "Mostly text chat",
          "Text chat + occasional voice",
          "Prefer to read/listen first"
        ].map(item => (
          <label key={item}>
            <input
              type="radio"
              name="communication"
              onChange={() => {
                setCommunication(item);
                setErrors(prev => ({ ...prev, communication: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.communication && <p className="error-message">{errors.communication}</p>}
      </div>

      <button className="submit-btn" onClick={submit}>
        Submit
      </button>

      {/* Therapist Picker Popup */}
      {showTherapistPopup && (
        <TherapistPicker
          onClose={() => setShowTherapistPopup(false)}
          onChosen={() => {
            setShowTherapistPopup(false);
            navigate("/user"); // return home
          }}
        />
      )}
    </div>
  );
};

export default Questionnaire;
