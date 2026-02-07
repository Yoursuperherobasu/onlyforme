import type { Edge, Node, ReactFlowJsonObject } from "@xyflow/react";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import {
  customGetAppVersions,
  customGetLatestVersion,
} from "@/customization/utils/custom-get-app-latest-version";
import { BASE_URL_API } from "../../constants/constants";
import { api } from "../../controllers/API/api";
import type {
  VertexBuildTypeAPI,
  VerticesOrderTypeAPI,
} from "../../types/api/index";
import type { FlowStyleType, FlowType } from "../../types/flow";
// [STORE REMOVED] import type { StoreComponentResponse } from "../../types/store";

const GITHUB_API_URL = "https://api.github.com";
const DISCORD_API_URL =
  "https://discord.com/api/v9/invites/EqksyE2EX9?with_counts=true";

export async function getRepoStars(owner: string, repo: string) {
  try {
    const response = await api.get(`${GITHUB_API_URL}/repos/${owner}/${repo}`);
    return response?.data.stargazers_count;
  } catch (error) {
    console.error("Error fetching repository data:", error);
    return null;
  }
}

export async function getDiscordCount() {
  try {
    const response = await api.get(DISCORD_API_URL);
    return response?.data.approximate_member_count;
  } catch (error) {
    console.error("Error fetching repository data:", error);
    return null;
  }
}

export const getAppVersions = customGetAppVersions;
export const getLatestVersion = customGetLatestVersion;

export async function createApiKey(name: string) {
  try {
    const res = await api.post(`${BASE_URL_API}api_key/`, { name });
    if (res.status === 200) {
      return res.data;
    }
  } catch (error) {
    throw error;
  }
}

// [STORE REMOVED] All store API functions (saveFlowStore, getStoreComponents, getComponent, checkHasApiKey, checkHasStore, updateFlowStore) removed — backend store service deleted
// Export stubs so imports don't break:
export async function saveFlowStore(..._args: any[]): Promise<any> { return undefined; }
export async function getStoreComponents(..._args: any[]): Promise<any> { return undefined; }
export async function getComponent(..._args: any[]): Promise<any> { return undefined; }
export async function checkHasApiKey(): Promise<any> { return { has_api_key: false, is_valid: false }; }
export async function checkHasStore(): Promise<any> { return { enabled: false }; }
export async function updateFlowStore(..._args: any[]): Promise<any> { return undefined; }

export async function getVerticesOrder(
  flowId: string,
  startNodeId?: string | null,
  stopNodeId?: string | null,
  nodes?: Node[],
  Edges?: Edge[],
): Promise<AxiosResponse<VerticesOrderTypeAPI>> {
  // nodeId is optional and is a query parameter
  // if nodeId is not provided, the API will return all vertices
  const config: AxiosRequestConfig<any> = {};
  if (stopNodeId) {
    config["params"] = { stop_component_id: stopNodeId };
  } else if (startNodeId) {
    config["params"] = { start_component_id: startNodeId };
  }
  const data = {
    data: {},
  };
  if (nodes && Edges) {
    data["data"]["nodes"] = nodes;
    data["data"]["edges"] = Edges;
  }
  return await api.post(
    `${BASE_URL_API}build/${flowId}/vertices`,
    data,
    config,
  );
}

export async function postBuildVertex(
  flowId: string,
  vertexId: string,
  input_value: string,
  files?: string[],
): Promise<AxiosResponse<VertexBuildTypeAPI>> {
  // input_value is optional and is a query parameter
  const data = {};
  if (typeof input_value !== "undefined") {
    data["inputs"] = { input_value: input_value };
  }
  if (data && files) {
    data["files"] = files;
  }
  return await api.post(
    `${BASE_URL_API}build/${flowId}/vertices/${vertexId}`,
    data,
  );
}
