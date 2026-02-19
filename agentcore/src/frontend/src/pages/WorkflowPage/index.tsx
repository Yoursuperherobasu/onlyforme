import {
  Search,
  X
} from "lucide-react";
import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import { useEffect, useMemo, useState } from "react";

type EnvironmentTab = "UAT" | "PROD";

interface WorkagentType {
  id: string;
  name: string;
  description: string;
  user: string;
  department: string;
  created: string;
  lastRun: string;
  failedRuns: number | null;
  status: boolean;
  enabled: boolean;
}

interface WorkflowsViewProps {
  workflows?: WorkagentType[];
  setSearch: (search: string) => void;
  onWorkagentClick?: (workflow: WorkagentType) => void;
}

const DUMMY_WORKAGENTS_UAT: WorkagentType[] = [
  {
    id: "uat-1",
    name: "Customer Support Chatbot",
    description: "Intelligent chatbot for customer inquiries",
    user: "Sarah Mitchell",
    department: "Customer Support",
    created: "Aug 28, 10:26 AM",
    lastRun: "Jan 20, 8:34 AM",
    failedRuns: 5,
    status: false,
    enabled: true,
  },
  {
    id: "uat-2",
    name: "Document Analysis Pipeline",
    description: "Extract insights from PDF documents",
    user: "Michael Chen",
    department: "Data Science",
    created: "Aug 15, 2:14 PM",
    lastRun: "Jan 20, 10:34 AM",
    failedRuns: 2,
    status: true,
    enabled: true,
  },
  {
    id: "uat-3",
    name: "Content Generation Agent",
    description: "Multi-agent system for generating blog posts",
    user: "Emily Rodriguez",
    department: "Marketing",
    created: "Jul 22, 9:45 AM",
    lastRun: "Jan 20, 10:29 AM",
    failedRuns: 18,
    status: false,
    enabled: false,
  },
  {
    id: "uat-4",
    name: "Data Processing Workagent",
    description: "Automated ETL pipeline with AI-powered data cleaning",
    user: "David Kumar",
    department: "Data Engineering",
    created: "Jul 10, 4:30 PM",
    lastRun: "Jan 20, 9:15 AM",
    failedRuns: 7,
    status: true,
    enabled: true,
  },
  {
    id: "uat-5",
    name: "Sentiment Analysis API",
    description: "Real-time sentiment analysis for customer feedback",
    user: "Jessica Park",
    department: "Analytics",
    created: "Jun 18, 11:20 AM",
    lastRun: "Jan 20, 9:34 AM",
    failedRuns: null,
    status: false,
    enabled: true,
  },
];

const DUMMY_WORKAGENTS_PROD: WorkagentType[] = [
  {
    id: "prod-1",
    name: "Fraud Detection Agent",
    description: "Real-time transaction risk analysis",
    user: "Noah Thompson",
    department: "Risk",
    created: "Sep 03, 1:40 PM",
    lastRun: "Jan 20, 10:40 AM",
    failedRuns: 1,
    status: true,
    enabled: true,
  },
  {
    id: "prod-2",
    name: "Invoice Reconciliation",
    description: "Auto-match invoice records across systems",
    user: "Priya Menon",
    department: "Finance",
    created: "Aug 11, 11:00 AM",
    lastRun: "Jan 20, 9:52 AM",
    failedRuns: 0,
    status: true,
    enabled: true,
  },
  {
    id: "prod-3",
    name: "Legal Policy Reviewer",
    description: "Detects policy conflicts and compliance gaps",
    user: "Liam Foster",
    department: "Legal",
    created: "Jul 30, 5:05 PM",
    lastRun: "Jan 20, 9:08 AM",
    failedRuns: 3,
    status: false,
    enabled: true,
  },
  {
    id: "prod-4",
    name: "Ops Alert Summarizer",
    description: "Summarizes high-volume operational alerts",
    user: "Ava Brooks",
    department: "Operations",
    created: "Jun 27, 8:20 AM",
    lastRun: "Jan 20, 10:11 AM",
    failedRuns: null,
    status: true,
    enabled: false,
  },
  {
    id: "prod-5",
    name: "Sales Forecasting Assistant",
    description: "Generates weekly sales demand forecasts",
    user: "Ethan Reed",
    department: "Sales",
    created: "May 14, 2:50 PM",
    lastRun: "Jan 20, 8:56 AM",
    failedRuns: 2,
    status: false,
    enabled: true,
  },
];

export default function WorkflowsView({
  workflows,
  setSearch,
  onWorkagentClick,
}: WorkflowsViewProps): JSX.Element {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<EnvironmentTab>("UAT");
  const [workflowStates, setWorkagentStates] = useState<{
    [key: string]: { status: boolean; enabled: boolean };
  }>({});
  const { permissions } = useContext(AuthContext);
  const can = (permissionKey: string) => permissions?.includes(permissionKey);

  const displayworkflows = useMemo(() => {
    if (workflows?.length) {
      return workflows;
    }

    return activeTab === "UAT" ? DUMMY_WORKAGENTS_UAT : DUMMY_WORKAGENTS_PROD;
  }, [activeTab, workflows]);

  useEffect(() => {
    const initialStates: { [key: string]: { status: boolean; enabled: boolean } } = {};
    displayworkflows.forEach((workflow) => {
      initialStates[workflow.id] = {
        status: workflow.status,
        enabled: workflow.enabled,
      };
    });
    setWorkagentStates(initialStates);
  }, [displayworkflows]);

  const handleStatusToggle = (workflowId: string) => {
    setWorkagentStates((prev) => ({
      ...prev,
      [workflowId]: {
        ...prev[workflowId],
        status: !prev[workflowId]?.status,
      },
    }));
  };

  const handleEnabledToggle = (workflowId: string) => {
    setWorkagentStates((prev) => ({
      ...prev,
      [workflowId]: {
        ...prev[workflowId],
        enabled: !prev[workflowId]?.enabled,
      },
    }));
  };

  const filteredworkflows = displayworkflows.filter((workflow) => {
    const matchesSearch =
      !searchQuery ||
      workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.department.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesSearch;
  });

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, setSearch]);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="flex-shrink-0 border-b px-8 py-6">
        <div className="mb-4 flex items-center gap-3">
          <h1 className="text-2xl font-semibold">Agent Control Panel</h1>
        </div>

        <div className="mb-6 inline-flex rounded-lg border bg-muted/30 p-1">
          <button
            type="button"
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === "UAT"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActiveTab("UAT")}
          >
            UAT
          </button>
          <button
            type="button"
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === "PROD"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActiveTab("PROD")}
          >
            PROD
          </button>
        </div>

        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border bg-card py-2.5 pl-10 pr-4 text-sm"
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        <div className="overflow-hidden rounded-lg border bg-card">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Agent Name
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Creater
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Department
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Created At
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Last Run
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Failed Runs
                </th>
                {can("start_stop_agent") && (
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                    Start/Stop
                  </th>
                )}
                {can("enable_disable_agent") && (
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                    Enable/Disable
                  </th>
                )}
              </tr>
            </thead>

            <tbody className="divide-y">
              {filteredworkflows.map((workflow) => (
                <tr
                  key={workflow.id}
                  className="cursor-pointer transition-colors hover:bg-muted/50"
                  onClick={() => onWorkagentClick?.(workflow)}
                >
                  <td className="px-6 py-4">
                    <div className="font-semibold">{workflow.name}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {workflow.description}
                    </div>
                  </td>

                  <td className="px-6 py-4 text-sm">{workflow.user}</td>

                  <td className="px-6 py-4 text-sm">{workflow.department}</td>

                  <td className="px-6 py-4 text-sm text-muted-foreground">{workflow.created}</td>

                  <td className="px-6 py-4 text-sm text-muted-foreground">{workflow.lastRun}</td>

                  <td className="px-6 py-4">
                    {workflow.failedRuns !== null ? (
                      <div className="flex items-center gap-1.5 text-sm text-red-500">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full border border-red-500">
                          <X className="h-3 w-3" />
                        </span>
                        <span className="font-medium">{workflow.failedRuns}</span>
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">-</span>
                    )}
                  </td>
                  {can("start_stop_agent") && (
                    <td className="px-6 py-4">
                      <button
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          workflowStates[workflow.id]?.status ? "bg-blue-600" : "bg-muted"
                        }`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStatusToggle(workflow.id);
                        }}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            workflowStates[workflow.id]?.status ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </td>
                  )}
                  {can("enable_disable_agent") && (
                    <td className="px-6 py-4">
                      <button
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          workflowStates[workflow.id]?.enabled ? "bg-green-500" : "bg-muted"
                        }`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEnabledToggle(workflow.id);
                        }}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            workflowStates[workflow.id]?.enabled ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-muted-foreground">Rows per page</div>
          <div className="flex items-center gap-2">
            <button className="rounded-lg border bg-card px-4 py-2 text-sm hover:bg-muted">
              Previous
            </button>
            <button className="rounded-lg border bg-card px-4 py-2 text-sm hover:bg-muted">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
