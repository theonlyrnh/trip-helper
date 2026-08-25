import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { setCsrfToken } from "../../api/http";
import { authApi } from "../../api/resources";
import type { AuthSession } from "../../api/types";

export const sessionQueryKey = ["auth", "session"] as const;

export function useSession() {
  return useQuery<AuthSession | null>({
    queryKey: sessionQueryKey,
    queryFn: authApi.currentUser,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      setCsrfToken(null);
      queryClient.setQueryData(sessionQueryKey, null);
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" });
    },
  });
}

export function SessionExpiryListener() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    const clearSession = () => {
      setCsrfToken(null);
      queryClient.setQueryData(sessionQueryKey, null);
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" });
      navigate("/login", { replace: true });
    };
    window.addEventListener("trip-helper:session-expired", clearSession);
    return () => window.removeEventListener("trip-helper:session-expired", clearSession);
  }, [navigate, queryClient]);

  return null;
}
