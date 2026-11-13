
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./auth/AuthProvider";

import "./index.css";
import App from "./App";
import { isDemoMode } from "./demoMode";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

async function enableMocking() {
  if (!import.meta.env.DEV || !isDemoMode) {
    return;
  }

  const { worker } = await import("./mocks/browser");

  await worker.start();
}

enableMocking()
  .then(() => {
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </QueryClientProvider>
      </StrictMode>
    );
  })
  .catch((error) => {
    console.error("Application startup failed:", error);
  });
