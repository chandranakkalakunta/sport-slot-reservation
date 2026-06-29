import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-ext-400.css";
import "@fontsource/inter/latin-ext-500.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { loadBranding } from "./lib/branding";
import { applyMode, getInitialMode } from "./lib/themeMode";
import "./styles/theme.css";

// Apply theme before first render to avoid flash
applyMode(getInitialMode());

const queryClient = new QueryClient();

// loadBranding applies CSS vars before first render; silent fallback on error.
// Top-level await rejected by esbuild target — wrapped in .then() per 4.6 STEP 5 note.
loadBranding().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
});
