// src/AppLayout.jsx
import React from "react";
import { Layout, Menu, Grid } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { LeftOutlined } from "@ant-design/icons";
import { useAuth } from "./AuthContext";
import HeaderBar from "./components/Header";

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

const AppLayout = () => {
  const { role } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isMobile = !screens.md; // 小于 md 视为手机

  const userMenu = [
    { key: "/user", label: "Home" },
    { key: "/chat", label: "Chat" },
    { key: "/mailbox", label: "Mailbox" },
    { key: "/profile", label: "Profile" }
  ];

  const therapistMenu = [
    { key: "/therapist", label: "Dashboard" },
    { key: "/chat", label: "Chat" },
    { key: "/mailbox", label: "Mailbox" },
    { key: "/ai-summary", label: "AI Summary" },
    { key: "/profile", label: "Profile" }
  ];

  const menuItems = role === "therapist" ? therapistMenu : userMenu;

  const selectedKey =
    menuItems.find((item) => location.pathname.startsWith(item.key))?.key || "";

  const handleMenuClick = ({ key }) => {
    navigate(key);
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {/* 顶部 Header：左侧是返回按钮，中间是标题+右侧字号/菜单 */}
      <Header
        style={{
          padding: "0 12px",
          background: "#fff",
          display: "flex",
          alignItems: "center",
          gap: 12
        }}
      >
        {/* 手机端左上角：返回上一级 ← */}
        {isMobile && (
          <button
            onClick={() => navigate(-1)}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 32,
              height: 32,
              borderRadius: "999px",
              padding: 0
            }}
          >
            <LeftOutlined />
          </button>
        )}

        {/* 右边放我们的 HeaderBar（标题 + 字号 + 用户菜单） */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <HeaderBar />
        </div>
      </Header>

      <Layout>
        {/* 只有在桌面端显示左侧菜单；手机端不显示 Sider */}
        {!isMobile && (
          <Sider
            width={220}
            theme="light"
            style={{
              borderRight: "1px solid #f0f0f0"
            }}
          >
            <Menu
              mode="inline"
              items={menuItems}
              selectedKeys={[selectedKey]}
              onClick={handleMenuClick}
              style={{ height: "100%", borderRight: 0 }}
            />
          </Sider>
        )}

        <Content
          style={{
            padding: isMobile ? 8 : 16,
            background: "#f5f5f5",
            overflow: "auto"
          }}
        >
          {/* 这里渲染各个页面：TherapistHome / Chat / Mailbox / Profile / AiSummary / ChatRoom 等 */}
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
