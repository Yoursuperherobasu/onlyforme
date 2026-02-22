import react from "@vitejs/plugin-react-swc";
import * as dotenv from "dotenv";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";
import tsconfigPaths from "vite-tsconfig-paths";
import {
  API_ROUTES,
  BASENAME,
  PORT,
  PROXY_TARGET,
} from "./src/customization/config-constants";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  const envAgentCoreResult = dotenv.config({
    path: path.resolve(__dirname, "../../.env"),
  });
  

  const envAgentCore = envAgentCoreResult.parsed || {};

  const apiRoutes = API_ROUTES || ["^/api/", "^/api/", "/health"];

  const target =
    envAgentCore.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || PROXY_TARGET || "http://localhost:7860";
  
  const port = Number(envAgentCore.VITE_PORT || env.VITE_PORT) || PORT || 3000;

  const proxyTargets = apiRoutes.reduce((proxyObj: Record<string, any>, route) => {
    proxyObj[route] = {
      target: target,
      changeOrigin: true,
      secure: false,
      ws: true,
      // Ensure streaming (SSE / NDJSON) responses are forwarded
      // chunk-by-chunk without buffering by the dev-server proxy.
      configure: (proxy: any) => {
        proxy.on("proxyRes", (proxyRes: any, _req: any, res: any) => {
          const ct = proxyRes.headers["content-type"] || "";
          if (ct.includes("text/event-stream") || ct.includes("application/x-ndjson")) {
            // Prevent Node / proxy from coalescing small chunks
            res.setHeader("X-Accel-Buffering", "no");
            res.setHeader("Cache-Control", "no-cache, no-transform");
            if (typeof res.flushHeaders === "function") {
              res.flushHeaders();
            }
          }
        });
      },
    };
    return proxyObj;
  }, {});

  return {
    base: BASENAME || "",
    build: {
      outDir: "build",
    },
    define: {
      "process.env.BACKEND_URL": JSON.stringify(
        envAgentCore.BACKEND_URL ?? "http://localhost:7860",
      ),
      "process.env.ACCESS_TOKEN_EXPIRE_SECONDS": JSON.stringify(
        envAgentCore.ACCESS_TOKEN_EXPIRE_SECONDS ?? 60,
      ),
      "process.env.CI": JSON.stringify(envAgentCore.CI ?? false),
      "process.env.AGENTCORE_MCP_COMPOSER_ENABLED": JSON.stringify(
        envAgentCore.AGENTCORE_MCP_COMPOSER_ENABLED ?? "true",
      ),
    },
    plugins: [react(), svgr(), tsconfigPaths()],
    server: {
      port: port,
      proxy: {
        ...proxyTargets,
      },
    },
  };
});
