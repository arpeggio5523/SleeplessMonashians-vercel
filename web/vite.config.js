import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// X mounts this build's output (dist/) as static files behind the
// FastAPI app, at the same origin as the API. No CORS to configure.
export default defineConfig({
  plugins: [react()],
  server: {
    // Uncomment once X's API is live locally, so /emails etc. proxy through
    // during dev instead of hitting a missing route on the Vite dev server:
    // proxy: { "/emails": "http://localhost:8000", "/review": "http://localhost:8000" },
  },
});