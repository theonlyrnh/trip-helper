import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { LoaderCircle, LockKeyhole, LogIn } from "lucide-react";
import { authApi } from "../../api/resources";
import { sessionQueryKey, useSession } from "./session";

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const session = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () => authApi.login(email.trim(), password),
    onSuccess: (nextSession) => {
      queryClient.setQueryData(sessionQueryKey, nextSession);
      const from = (location.state as LocationState | null)?.from || "/trips";
      navigate(from, { replace: true });
    },
  });

  if (session.data) return <Navigate to="/trips" replace />;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password || login.isPending) return;
    login.mutate();
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={submit} aria-busy={login.isPending}>
        <header className="login-header">
          <div className="login-mark" aria-hidden="true"><LockKeyhole size={24} /></div>
          <div>
            <h1>Trip Helper</h1>
            <p>登录后管理属于你的报销项目和票据。</p>
          </div>
        </header>
        <label className="field">
          <span>账号</span>
          <input type="email" name="email" inputMode="email" autoComplete="username" placeholder="name@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="field">
          <span>密码</span>
          <input type="password" name="password" autoComplete="current-password" minLength={6} value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {login.error && <p className="form-error" role="alert">登录失败，请检查账号和密码后重试。</p>}
        <button className="button button-primary button-wide" type="submit" disabled={login.isPending}>
          {login.isPending ? <LoaderCircle className="spin" size={17} aria-hidden="true" /> : <LogIn size={17} aria-hidden="true" />}
          {login.isPending ? "正在登录" : "登录"}
        </button>
      </form>
    </main>
  );
}
