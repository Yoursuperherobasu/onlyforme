import type { AgentType } from "../../../types/agent";

export type FolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string;
  agents: AgentType[];
  components: string[];
};

export type PaginatedFolderType = {
  folder: {
    name: string;
    description: string;
    id?: string | null;
    parent_id: string;
    components: string[];
  };
  agents: {
    items: AgentType[];
    total: number;
    page: number;
    size: number;
    pages: number;
  };
};

export type AddFolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string | null;
  agents?: string[];
  components?: string[];
};

export type StarterProjectsType = {
  name?: string;
  description?: string;
  agents?: AgentType[];
  id: string;
  parent_id: string;
};
