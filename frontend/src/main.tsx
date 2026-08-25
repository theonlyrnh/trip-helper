import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { queryClient } from "./app/query";
import { SessionExpiryListener } from "./features/auth/session";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SessionExpiryListener />
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
