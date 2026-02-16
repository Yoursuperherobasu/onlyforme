import { api } from "./api";

export interface Score {
  id: string;
  trace_id: string;
  agent_name?: string;
  name: string;
  value: number;
  source: string;
  comment?: string;
  created_at?: string;
  user_id?: string;
}

export interface AnalyticsMetric {
  name: string;
  count: number;
  average: number;
  min: number;
  max: number;
  p50?: number;
  p90?: number;
}

export interface EvaluationAnalytics {
  total_scores: number;
  by_name: AnalyticsMetric[];
}

export interface EvaluationStatus {
  langfuse_available: boolean;
  llm_judge_available: boolean;
  user_id?: string;
}

export interface TraceForReview {
  id: string;
  name?: string | null;
  timestamp?: string | null;
  input?: unknown;
  output?: unknown;
  session_id?: string | null;
  flow_name?: string | null;
  has_scores: boolean;
  score_count: number;
}

export const getEvaluationScores = async (params: {
  limit?: number;
  page?: number;
  trace_id?: string;
  name?: string;
}) => {
  const response = await api.get("/api/evaluation/scores", { params });
  return response.data;
};

export const createEvaluationScore = async (data: {
  trace_id: string;
  name: string;
  value: number;
  comment?: string;
  observation_id?: string;
}) => {
  const response = await api.post("/api/evaluation/create", data);
  return response.data;
};

export const runLLMJudge = async (data: {
  trace_id: string;
  criteria: string;
  model?: string;
  name?: string;
}) => {
  const response = await api.post("/api/evaluation/judge", data);
  return response.data;
};

export const getEvaluationAnalytics = async () => {
  const response = await api.get("/api/evaluation/analytics");
  return response.data;
};

export const getEvaluationStatus = async () => {
  const response = await api.get("/api/evaluation/status");
  return response.data;
};

export const getPendingReviews = async (params: {
  limit?: number;
  trace_id?: string;
  flow_name?: string;
  session_id?: string;
  user_id_filter?: string;
  ts_from?: string;
  ts_to?: string;
} = { limit: 20 }) => {
  const response = await api.get("/api/evaluation/traces/pending", { params });
  return response.data;
};

export interface EvaluatorConfig {
  id: string;
  name: string;
  criteria: string;
  model: string;
  preset_id?: string;
  target?: string[];
  ground_truth?: string;
  trace_id?: string;
  agent_id?: string;
  agent_ids?: string[];
  flow_id?: string;
  flow_ids?: string[];
  flow_name?: string;
  session_id?: string;
  project_name?: string;
  ts_from?: string;
  ts_to?: string;
}

export interface EvaluationPreset {
  id: string;
  name: string;
  description?: string;
  criteria: string;
  requires_ground_truth?: boolean;
}

export const createEvaluator = async (data: any) => {
  const response = await api.post("/api/evaluation/configs", data);
  return response.data as EvaluatorConfig;
};

export const getFlows = async () => {
  const response = await api.get("/api/evaluation/models");
  return response.data;
};

export const listEvaluators = async () => {
  const response = await api.get("/api/evaluation/configs");
  return response.data as EvaluatorConfig[];
};

export const getEvaluationPresets = async () => {
  const response = await api.get("/api/evaluation/presets");
  return response.data as EvaluationPreset[];
};

export const previewEvaluation = async (data: { trace_id: string; criteria: string; model?: string }) => {
  const response = await api.post("/api/evaluation/preview", data);
  return response.data as { system_prompt: string; user_prompt: string; trace: any };
};

export const getAvailableModels = async () => {
  // Use the backend evaluation models proxy which uses standard app auth (cookie/JWT)
  const response = await api.get("/api/evaluation/models");
  // returns { object: 'list', data: [...] }
  return response.data;
};

export const updateEvaluator = async (id: string, data: any) => {
  const response = await api.put(`/api/evaluation/configs/${id}`, data);
  return response.data as EvaluatorConfig;
};

export const deleteEvaluator = async (id: string) => {
  const response = await api.delete(`/api/evaluation/configs/${id}`);
  return response.data as { status: string };
};
