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

  // ===== 核心心理问卷字段（全部用于 grouping） =====
  const [lookingFor, setLookingFor] = useState([]);        // 你来这里主要想要什么
  const [struggles, setStruggles] = useState([]);          // 当前困扰
  const [atmosphere, setAtmosphere] = useState("");        // 小组氛围
  const [communication, setCommunication] = useState("");  // 沟通方式偏好

  // ===== 新增 5 个更“心理 + 兴趣”向问题 =====
  const [topics, setTopics] = useState([]);            // 想聊的主题
  const [coping, setCoping] = useState([]);            // 压力大时会怎么做
  const [sharingComfort, setSharingComfort] = useState(""); // 在小组里分享的舒适度
  const [safePeople, setSafePeople] = useState([]);    // 和什么样的人在一起最有安全感
  const [interests, setInterests] = useState([]);      // 想在小组里一起分享的兴趣

  const toggleSelect = (value, setter, list) => {
    if (list.includes(value)) setter(list.filter((v) => v !== value));
    else setter([...list, value]);
  };

  const submit = async () => {
    const newErrors = {};

    // 原有的 4 个核心问题
    if (lookingFor.length === 0)
      newErrors.lookingFor = "Please select at least one option.";
    if (struggles.length === 0)
      newErrors.struggles = "Please select at least one option.";
    if (!atmosphere)
      newErrors.atmosphere = "Please choose one option.";
    if (!communication)
      newErrors.communication = "Please choose one option.";

    // 新增 5 个问题的校验
    if (topics.length === 0)
      newErrors.topics = "Please select at least one topic.";
    if (coping.length === 0)
      newErrors.coping = "Please select at least one option.";
    if (!sharingComfort)
      newErrors.sharingComfort = "Please choose one option.";
    if (safePeople.length === 0)
      newErrors.safePeople = "Please select at least one option.";
    if (interests.length === 0)
      newErrors.interests = "Please select at least one interest.";

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const answers = {
      lookingFor,
      struggles,
      atmosphere,
      communication,
      topics,
      coping,
      sharingComfort,
      safePeople,
      interests,
    };

    await submitQuestionnaire(answers, token);
    setShowTherapistPopup(true);
  };

  return (
    <div className="card questionnaire-card">
      <h2>Health & Wellness Questionnaire</h2>

      {/* 1.what are you mainly looking for from this group? */}
      <div className={`question-block ${errors.lookingFor ? "error" : ""}`}>
        <p className="question">
          <strong>What are you mainly looking for from this group?</strong>
        </p>
        {[
          "Someone to listen and understand me",
          "A place to vent or let feelings out",
          "Advice or practical suggestions",
          "Emotional support and encouragement",
          "Calm company and quiet presence",
          "Not sure yet, I just want to try",
        ].map((item) => (
          <label key={item}>
            <input
              type="checkbox"
              checked={lookingFor.includes(item)}
              onChange={() => {
                toggleSelect(item, setLookingFor, lookingFor);
                setErrors((prev) => ({ ...prev, lookingFor: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.lookingFor && (
          <p className="error-message">{errors.lookingFor}</p>
        )}
      </div>

      {/* 2. Current struggles */}
      <div className={`question-block ${errors.struggles ? "error" : ""}`}>
        <p className="question">
          <strong>Current struggles</strong>
        </p>
        {[
          "Stress from school or work",
          "Relationship or friendship issues",
          "Family or partner conflicts",
          "Feeling anxious or overwhelmed",
          "Feeling sad, numb or low-energy",
          "Loneliness or lack of connection",
          "Low confidence or self-doubt",
          "General confusion about life direction",
        ].map((item) => (
          <label key={item}>
            <input
              type="checkbox"
              checked={struggles.includes(item)}
              onChange={() => {
                toggleSelect(item, setStruggles, struggles);
                setErrors((prev) => ({ ...prev, struggles: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.struggles && (
          <p className="error-message">{errors.struggles}</p>
        )}
      </div>

      {/* 3. Topics you would most like to explore */}
      <div className={`question-block ${errors.topics ? "error" : ""}`}>
        <p className="question">
          <strong>Topics you would most like to explore</strong>
        </p>
        {[
          "Coping with anxiety and worry",
          "Managing low mood or burnout",
          "Relationships & communication",
          "Self-esteem & self-criticism",
          "Life transitions / identity questions",
          "Not sure yet, open to different topics",
        ].map((item) => (
          <label key={item}>
            <input
              type="checkbox"
              checked={topics.includes(item)}
              onChange={() => {
                toggleSelect(item, setTopics, topics);
                setErrors((prev) => ({ ...prev, topics: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.topics && (
          <p className="error-message">{errors.topics}</p>
        )}
      </div>

      {/* 4. Coping strategies when stressed */}
      <div className={`question-block ${errors.coping ? "error" : ""}`}>
        <p className="question">
          <strong>When you feel stressed, what do you usually do?</strong>
        </p>
        {[
          "Scroll on my phone / social media",
          "Sleep or stay in bed more",
          "Eat or snack more / less than usual",
          "Work or study more to distract myself",
          "Talk to friends or family",
          "Do creative things (music, art, journaling)",
          "It changes a lot / not sure",
        ].map((item) => (
          <label key={item}>
            <input
              type="checkbox"
              checked={coping.includes(item)}
              onChange={() => {
                toggleSelect(item, setCoping, coping);
                setErrors((prev) => ({ ...prev, coping: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.coping && (
          <p className="error-message">{errors.coping}</p>
        )}
      </div>

      {/* 5. Preferred group atmosphere */}
      <div className={`question-block ${errors.atmosphere ? "error" : ""}`}>
        <p className="question">
          <strong>Your preferred group atmosphere</strong>
        </p>
        {["Warm & gentle", "Real & direct", "Light & humorous", "Calm & slow"].map(
          (item) => (
            <label key={item}>
              <input
                type="radio"
                name="atmosphere"
                checked={atmosphere === item}
                onChange={() => {
                  setAtmosphere(item);
                  setErrors((prev) => ({ ...prev, atmosphere: null }));
                }}
              />
              {item}
            </label>
          )
        )}
        {errors.atmosphere && (
          <p className="error-message">{errors.atmosphere}</p>
        )}
      </div>

      {/* 6. Sharing comfort level */}
      <div
        className={`question-block ${
          errors.sharingComfort ? "error" : ""
        }`}
      >
        <p className="question">
          <strong>
            How comfortable are you sharing personal stories in a small group?
          </strong>
        </p>
        {[
          "I prefer to listen first and maybe share later",
          "I can share a bit once I feel safe",
          "I'm okay sharing openly most of the time",
          "I like deep and honest sharing from the start",
        ].map((item) => (
          <label key={item}>
            <input
              type="radio"
              name="sharingComfort"
              checked={sharingComfort === item}
              onChange={() => {
                setSharingComfort(item);
                setErrors((prev) => ({ ...prev, sharingComfort: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.sharingComfort && (
          <p className="error-message">{errors.sharingComfort}</p>
        )}
      </div>

      {/* 7. People you feel safest around */}
      <div className={`question-block ${errors.safePeople ? "error" : ""}`}>
        <p className="question">
          <strong>What kind of people do you feel safest around?</strong>
        </p>
        {[
          "People around my age",
          "Mixed ages are okay",
          "People with similar life experiences",
          "People from a similar cultural background",
          "People with similar values or beliefs",
          "No strong preference",
        ].map((item) => (
          <label key={item}>
            <input
              type="checkbox"
              checked={safePeople.includes(item)}
              onChange={() => {
                toggleSelect(item, setSafePeople, safePeople);
                setErrors((prev) => ({ ...prev, safePeople: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.safePeople && (
          <p className="error-message">{errors.safePeople}</p>
        )}
      </div>

      {/* 8. Preferred communication style */}
      <div
        className={`question-block ${
          errors.communication ? "error" : ""
        }`}
      >
        <p className="question">
          <strong>Preferred communication style</strong>
        </p>
        {[
          "Mostly text chat",
          "Text chat + occasional voice",
          "Prefer to read/listen first",
        ].map((item) => (
          <label key={item}>
            <input
              type="radio"
              name="communication"
              checked={communication === item}
              onChange={() => {
                setCommunication(item);
                setErrors((prev) => ({ ...prev, communication: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.communication && (
          <p className="error-message">{errors.communication}</p>
        )}
      </div>

      {/* 9. Interests to share with others */}
      <div className={`question-block ${errors.interests ? "error" : ""}`}>
        <p className="question">
          <strong>
            Which activities or interests would you enjoy sharing with others?
          </strong>
        </p>
        {[
          "Movies / TV / anime",
          "Games (video games or board games)",
          "Music / singing",
          "Art / crafts / writing",
          "Sports / outdoor activities",
          "Mindfulness / yoga / spiritual topics",
          "Just talking, no specific activities",
        ].map((item) => (
          <label key={item}>
            <input
              type="checkbox"
              checked={interests.includes(item)}
              onChange={() => {
                toggleSelect(item, setInterests, interests);
                setErrors((prev) => ({ ...prev, interests: null }));
              }}
            />
            {item}
          </label>
        ))}
        {errors.interests && (
          <p className="error-message">{errors.interests}</p>
        )}
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
