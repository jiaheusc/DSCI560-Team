import React, { createContext, useState, useContext, useEffect } from "react";

const FontSizeContext = createContext();

export const FontSizeProvider = ({ children }) => {
  const [fontSize, setFontSize] = useState("medium"); // default

  // load saved preference
  useEffect(() => {
    const saved = localStorage.getItem("fontSize");
    if (saved) setFontSize(saved);
  }, []);

  const changeFontSize = (size) => {
    setFontSize(size);
    localStorage.setItem("fontSize", size);
  };

  return (
    <FontSizeContext.Provider value={{ fontSize, changeFontSize }}>
      <div style={{ fontSize: sizeToPx(fontSize) }}>{children}</div>
    </FontSizeContext.Provider>
  );
};

export const useFontSize = () => useContext(FontSizeContext);

const sizeToPx = (size) => {
  switch (size) {
    case "small": return "20px";
    case "large": return "24px";
    default: return "22px";
  }
};
