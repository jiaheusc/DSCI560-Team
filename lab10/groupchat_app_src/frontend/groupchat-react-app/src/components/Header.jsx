// src/components/Header.jsx
import React from "react";
import { Dropdown } from "antd";
import {
  DownOutlined,
  LogoutOutlined,
  UserOutlined,
  HomeOutlined
} from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useFontSize } from "../context/FontSizeContext";

const routeTitleMap = [
  { path: "/therapist", title: "Home" },
  { path: "/user", title: "Home" },
  { path: "/chat", title: "Chat" },
  { path: "/mailbox", title: "Mailbox" },
  { path: "/ai-summary", title: "AI Summary" },
  { path: "/profile", title: "Profile" },
  { path: "/questionnaire", title: "Questionnaire" }
];

const HeaderBar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { role, username, logout } = useAuth();
  const { fontSize, changeFontSize } = useFontSize();

  // 当前标题：找路由前缀
  const currentTitle =
    routeTitleMap.find((r) => location.pathname.startsWith(r.path))?.title ||
    "Home";

  // 根据角色决定“Home”跳去哪
  const homePath = role === "therapist" ? "/therapist" : "/user";
  const homeLabel = role === "therapist" ? "Therapist Dashboard" : "User Home";

  // 用户菜单
  const items = [
    {
      key: "home",
      label: homeLabel,
      icon: <HomeOutlined />
    },
    {
      key: "profile",
      label: "Profile",
      icon: <UserOutlined />
    },
    {
      type: "divider"
    },
    {
      key: "logout",
      label: "Logout",
      icon: <LogoutOutlined />,
      danger: true
    }
  ];

  const onMenuClick = ({ key }) => {
    if (key === "home") {
      navigate(homePath);
    }
    if (key === "profile") {
      navigate("/profile");
    }
    if (key === "logout") {
      if (logout) logout();
      navigate("/login");
    }
  };

  return (
    <div className="app-header-inner">
      {/* 左：当前页面标题（Therapist / User 的首页都显示 Home） */}
      <div className="header-title">{currentTitle}</div>

      {/* 右：字号切换 + 用户菜单 */}
      <div className="header-right">
        {/* 字体大小切换 */}
        <div className="header-fontsize-toggle">
          <button
            className={fontSize === "small" ? "fs-btn active" : "fs-btn"}
            onClick={() => changeFontSize("small")}
          >
            A-
          </button>
          <button
            className={fontSize === "medium" ? "fs-btn active" : "fs-btn"}
            onClick={() => changeFontSize("medium")}
          >
            A
          </button>
          <button
            className={fontSize === "large" ? "fs-btn active" : "fs-btn"}
            onClick={() => changeFontSize("large")}
          >
            A+
          </button>
        </div>

        {/* 用户 / Home / Logout 下拉 */}
        <Dropdown
          menu={{ items, onClick: onMenuClick }}
          trigger={["click"]}
        >
          <button className="header-user-btn">
            <span className="header-user-name">
              {username || (role === "therapist" ? "Therapist" : "User")}
            </span>
            <DownOutlined />
          </button>
        </Dropdown>
      </div>
    </div>
  );
};

export default HeaderBar;
