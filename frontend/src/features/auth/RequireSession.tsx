import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ApiError } from "../../api/http";
import { useSession } from "./session";

export function RequireSession() {
  const location = useLocation();
  const session = useSession();

  if (session.isPending) {
    return <main className="centered-state" aria-live="polite">正在恢复登录状态...</main>;
  }

  if (session.error instanceof ApiError && session.error.status === 401) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (session.error || !session.data) {
    return (
      <main className="centered-state">
        <p>无法连接服务，请确认网络后重试。</p>
        <button className="button button-secondary" onClick={() => void session.refetch()}>重新连接</button>
      </main>
    );
  }

  return <Outlet />;
}
