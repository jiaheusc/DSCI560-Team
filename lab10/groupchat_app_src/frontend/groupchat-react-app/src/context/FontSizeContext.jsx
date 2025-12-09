import React, { createContext, useState, useContext, useEffect } from "react";

const FontSizeContext = createContext();

export const FontSizeProvider = ({ children }) => {
  const [fontSize, setFontSize] = useState("medium"); // small / medium / large

  useEffect(() => {
    const saved = localStorage.getItem("fontSize");
    if (saved) setFontSize(saved);
  }, []);

  const changeFontSize = (size) => {
    setFontSize(size);
    localStorage.setItem("fontSize", size);
  };

  const scale = sizeToScale(fontSize);

  console.log("Current fontSize from context:", fontSize, "scale:", scale);

  return (
    <FontSizeContext.Provider value={{ fontSize, changeFontSize }}>
      {/* 这里用 em，当 html/body 是 16px 时：
          small = 0.9em ≈ 14.4px
          medium = 1em = 16px
          large = 1.1em ≈ 17.6px */}
      <div style={{ fontSize: `${scale}em` }} className="font-root">
        {children}
      </div>
    </FontSizeContext.Provider>
  );
};

export const useFontSize = () => useContext(FontSizeContext);

const sizeToScale = (size) => {
  switch (size) {
    case "small":
      return 0.8;  
    case "large":
      return 1.4;   
    default:
      return 1;     
  }
};
