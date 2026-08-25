import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { getCsrfToken, setCsrfToken } from "../../api/http";
import { SessionExpiryListener, sessionQueryKey } from "./session";

function CurrentPath() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

describe("SessionExpiryListener", () => {
  it("clears session state and redirects to login after an unauthorized API event", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(sessionQueryKey, {
      user: { id: "user-1", email: "user@example.com", is_admin: false },
      csrf_token: "csrf-token",
    });
    setCsrfToken("csrf-token");

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/trips"]}>
          <SessionExpiryListener />
          <CurrentPath />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    act(() => window.dispatchEvent(new Event("trip-helper:session-expired")));

    expect(screen.getByTestId("path")).toHaveTextContent("/login");
    expect(queryClient.getQueryData(sessionQueryKey)).toBeNull();
    expect(getCsrfToken()).toBeNull();
  });
});
