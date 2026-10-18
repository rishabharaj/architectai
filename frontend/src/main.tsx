import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { AuthProvider } from "./auth";
import "./index.css";

// Firebase popup permissions and authorized domains are tied to the exact host.
// Vercel's per-commit URLs change, so use the stable production domain for sign-in.
const productionHost = import.meta.env.VITE_VERCEL_PROJECT_PRODUCTION_URL;
if (productionHost && location.hostname.endsWith(".vercel.app") && location.hostname !== productionHost) {
  const canonicalUrl = new URL(location.href);
  canonicalUrl.hostname = productionHost;
  canonicalUrl.protocol = "https:";
  location.replace(canonicalUrl.href);
} else {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode><AuthProvider><App /></AuthProvider></React.StrictMode>
  );
}
