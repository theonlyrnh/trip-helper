import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "首页", end: true },
  { to: "/workspace", label: "工作台" },
  { to: "/dashboard", label: "年度统计" },
  { to: "/trips", label: "项目列表" },
  { to: "/settings", label: "设置" },
];

export default function Layout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <nav
        style={{
          width: 220,
          background: "#1a1a2e",
          color: "#eee",
          padding: "24px 0",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "0 20px 24px",
            fontSize: 18,
            fontWeight: 700,
            borderBottom: "1px solid #333",
            marginBottom: 16,
          }}
        >
          🧾 Trip Helper
        </div>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            style={({ isActive }) => ({
              padding: "10px 20px",
              color: isActive ? "#fff" : "#aaa",
              background: isActive ? "#16213e" : "transparent",
              textDecoration: "none",
              fontSize: 15,
              borderLeft: isActive ? "3px solid #4fc3f7" : "3px solid transparent",
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main style={{ flex: 1, padding: 32, background: "#f5f5f5" }}>
        <Outlet />
      </main>
    </div>
  );
}