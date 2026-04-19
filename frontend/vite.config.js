import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// VITE_PORT：前端开发端口；BACKEND_PORT：API 代理目标（与后端 PORT 一致）
const devPort = Number(process.env.VITE_PORT || 5173);
const apiBackend = `http://localhost:${process.env.BACKEND_PORT || "8000"}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: devPort,
    strictPort: true,
    proxy: {
      "/api": apiBackend,
    },
  },
});
