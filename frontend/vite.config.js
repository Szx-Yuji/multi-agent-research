import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Bind-mounted source on Docker Desktop does not deliver filesystem events
    // to the container, so hot reload silently stops working there. Polling is
    // opt-in via the compose file rather than always on, since it costs CPU.
    watch: process.env.VITE_USE_POLLING
      ? { usePolling: true, interval: 300 }
      : undefined,
  },
});
