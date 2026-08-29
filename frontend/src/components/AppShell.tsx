import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { BarChart3, FolderKanban, LogOut, Settings, UserRound } from "lucide-react";
import { useLogout, useSession } from "../features/auth/session";

export function AppShell() {
  const navigate = useNavigate();
  const session = useSession();
  const logout = useLogout();
  const user = session.data?.user;

  async function handleLogout() {
    await logout.mutateAsync().catch(() => undefined);
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="sidebar app-header">
        <div className="app-header-inner">
          <NavLink to="/trips" className="brand" aria-label="Trip Helper 项目列表">
            <span className="brand-mark"><FolderKanban size={19} /></span>
            <span>Trip Helper</span>
          </NavLink>
          <nav className="navigation" aria-label="主导航">
            <NavLink to="/trips" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              <FolderKanban size={17} />
              <span>项目</span>
            </NavLink>
            <NavLink to="/dashboard" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              <BarChart3 size={17} />
              <span>年度出差</span>
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              <Settings size={17} />
              <span>设置</span>
            </NavLink>
          </nav>
          <div className="sidebar-user">
            <div className="user-identity">
              <span className="user-avatar"><UserRound size={16} /></span>
              <span title={user?.email}>{user?.display_name || user?.email || "当前用户"}</span>
            </div>
            <button className="icon-button sidebar-logout" type="button" onClick={() => void handleLogout()} disabled={logout.isPending} aria-label="退出登录" title="退出登录">
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </header>
      <main className="app-content"><Outlet /></main>
    </div>
  );
}
