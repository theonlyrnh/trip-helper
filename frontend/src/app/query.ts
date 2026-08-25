import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        const status = typeof error === "object" && error && "status" in error
          ? (error as { status?: number }).status
          : undefined;
        return status !== 401 && status !== 403 && failureCount < 2;
      },
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: false,
    },
  },
});
