import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api va al backend local (uvicorn en :8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
