export type ModelProvider = "google" | "openai" | "anthropic" | "meta";

export type ModelCategory = "Text" | "Multimodal" | "Vision";

export interface ModelType {
  id: string;

  name: string;
  description?: string | null;

  provider: ModelProvider;

  contextWindow: number;
  pricing: string;

  category: ModelCategory;

  isCustom: boolean;

  /* Optional backend fields (future-proof) */
  createdAt?: string;
  updatedAt?: string;
}
