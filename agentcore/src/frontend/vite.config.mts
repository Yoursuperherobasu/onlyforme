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

  const envSenseiResult = dotenv.config({
    path: path.resolve(__dirname, "../../.env"),
  });
  

  const envSensei = envSenseiResult.parsed || {};

  const apiRoutes = API_ROUTES || ["^/api/", "^/api/", "/health"];

  const target =
    envSensei.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || PROXY_TARGET || "http://localhost:7860";
  
  const port = Number(envSensei.VITE_PORT || env.VITE_PORT) || PORT || 3000;

  const proxyTargets = apiRoutes.reduce((proxyObj, route) => {
    proxyObj[route] = {
      target: target,
      changeOrigin: true,
      secure: false,
      ws: true,
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
        envSensei.BACKEND_URL ?? "http://localhost:7860",
      ),
      "process.env.ACCESS_TOKEN_EXPIRE_SECONDS": JSON.stringify(
        envSensei.ACCESS_TOKEN_EXPIRE_SECONDS ?? 60,
      ),
      "process.env.CI": JSON.stringify(envSensei.CI ?? false),
      "process.env.SENSEI_MCP_COMPOSER_ENABLED": JSON.stringify(
        envSensei.SENSEI_MCP_COMPOSER_ENABLED ?? "true",
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
