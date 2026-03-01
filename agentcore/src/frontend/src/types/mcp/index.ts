export type MCPServerInfoType = {
  id?: string;
  name: string;
  description?: string;
  mode: string | null;
  toolsCount: number | null;
  error?: string;
};

export type MCPServerType = {
  name: string;
  command?: string;
  url?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
};

// --- MCP Registry types (PostgreSQL-backed) ---

export interface McpRegistryType {
  id: string;
  server_name: string;
  description?: string | null;
  mode: "sse" | "stdio";
  url?: string | null;
  command?: string | null;
  args?: string[] | null;
  has_env_vars: boolean;
  has_headers: boolean;
  is_active: boolean;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface McpRegistryCreateRequest {
  server_name: string;
  description?: string | null;
  mode: "sse" | "stdio";
  url?: string | null;
  command?: string | null;
  args?: string[] | null;
  env_vars?: Record<string, string> | null;
  headers?: Record<string, string> | null;
  is_active?: boolean;
  created_by?: string | null;
}

export interface McpRegistryUpdateRequest {
  server_name?: string;
  description?: string | null;
  mode?: "sse" | "stdio";
  url?: string | null;
  command?: string | null;
  args?: string[] | null;
  env_vars?: Record<string, string> | null;
  headers?: Record<string, string> | null;
  is_active?: boolean;
}

export interface McpTestConnectionRequest {
  mode: "sse" | "stdio";
  url?: string | null;
  command?: string | null;
  args?: string[] | null;
  env_vars?: Record<string, string> | null;
  headers?: Record<string, string> | null;
}

export interface McpTestConnectionResponse {
  success: boolean;
  message: string;
  tools_count?: number;
}

export interface McpToolInfo {
  name: string;
  description: string;
}

export interface McpProbeResponse {
  success: boolean;
  message: string;
  tools_count?: number;
  tools?: McpToolInfo[];
}
