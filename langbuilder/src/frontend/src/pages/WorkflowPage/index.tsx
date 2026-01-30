import {
  Search,
  Workflow,
  X
} from "lucide-react";
import { useEffect, useState } from "react";

interface WorkflowType {
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
  workflows?: WorkflowType[];
  setSearch: (search: string) => void;
  onWorkflowClick?: (workflow: WorkflowType) => void;
}

export default function WorkflowsView({
  workflows,
  setSearch,
  onWorkflowClick,
}: WorkflowsViewProps): JSX.Element {
  const [searchQuery, setSearchQuery] = useState("");
  const [workflowStates, setWorkflowStates] = useState<{
    [key: string]: { status: boolean; enabled: boolean };
  }>({});

  /* ---------------------------------- Dummy Workflows ---------------------------------- */

  const DUMMY_WORKFLOWS: WorkflowType[] = [
    {
      id: "1",
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
      id: "2",
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
      id: "3",
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
      id: "4",
      name: "Data Processing Workflow",
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
      id: "5",
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
    {
      id: "6",
      name: "Research Agent",
      description: "Deep research and knowledge synthesis",
      user: "Thomas Anderson",
      department: "R&D",
      created: "May 5, 3:15 PM",
      lastRun: "Jan 20, 10:24 AM",
      failedRuns: 23,
      status: false,
      enabled: false,
    },
    {
      id: "7",
      name: "Email Marketing Automation",
      description: "Personalized email campaigns with A/B testing",
      user: "Amanda Wilson",
      department: "Marketing",
      created: "Apr 12, 1:45 PM",
      lastRun: "Jan 17, 2:20 PM",
      failedRuns: 1,
      status: false,
      enabled: true,
    },
    {
      id: "8",
      name: "Code Review Assistant",
      description: "Automated code analysis and suggestions",
      user: "Robert Taylor",
      department: "Engineering",
      created: "Mar 8, 9:30 AM",
      lastRun: "Jan 20, 10:15 AM",
      failedRuns: 34,
      status: true,
      enabled: true,
    },
    {
      id: "9",
      name: "Image Classification Bot",
      description: "Visual recognition and categorization",
      user: "Olivia Martinez",
      department: "Machine Learning",
      created: "Feb 14, 3:00 PM",
      lastRun: "Jan 20, 10:04 AM",
      failedRuns: 11,
      status: false,
      enabled: true,
    },
    {
      id: "10",
      name: "Sales Lead Qualifier",
      description: "Intelligent lead scoring and qualification",
      user: "James Patterson",
      department: "Sales",
      created: "Jan 5, 11:15 AM",
      lastRun: "Jan 20, 8:45 AM",
      failedRuns: null,
      status: true,
      enabled: true,
    },
  ];

  const displayWorkflows = workflows?.length ? workflows : DUMMY_WORKFLOWS;

  /* ---------------------------------- Initialize States ---------------------------------- */

  useEffect(() => {
    const initialStates: { [key: string]: { status: boolean; enabled: boolean } } = {};
    displayWorkflows.forEach((workflow) => {
      initialStates[workflow.id] = {
        status: workflow.status,
        enabled: workflow.enabled,
      };
    });
    setWorkflowStates(initialStates);
  }, []);

  /* ---------------------------------- Toggle Handlers ---------------------------------- */

  const handleStatusToggle = (workflowId: string) => {
    setWorkflowStates((prev) => ({
      ...prev,
      [workflowId]: {
        ...prev[workflowId],
        status: !prev[workflowId]?.status,
      },
    }));
  };

  const handleEnabledToggle = (workflowId: string) => {
    setWorkflowStates((prev) => ({
      ...prev,
      [workflowId]: {
        ...prev[workflowId],
        enabled: !prev[workflowId]?.enabled,
      },
    }));
  };

  /* ---------------------------------- Filtering ---------------------------------- */

  const filteredWorkflows = displayWorkflows.filter((workflow) => {
    const matchesSearch =
      !searchQuery ||
      workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      workflow.department.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesSearch;
  });

  /* ---------------------------------- Debounced Search ---------------------------------- */

  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, setSearch]);

  /* ---------------------------------- JSX ---------------------------------- */

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex-shrink-0 px-8 py-6 border-b">
        <div className="flex items-center gap-3 mb-6">
          
          <h1 className="text-2xl font-semibold">Agent Control Panel</h1>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border bg-card py-2.5 pl-10 pr-4 text-sm"
          />
        </div>
      </div>

      {/* Table - Scrollable */}
      <div className="flex-1 overflow-auto p-8">
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted/50 border-b">
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
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Start/Stop
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold uppercase">
                  Enable/Disable
                </th>
              </tr>
            </thead>

            <tbody className="divide-y">
              {filteredWorkflows.map((workflow) => (
                <tr
                  key={workflow.id}
                  className="hover:bg-muted/50 transition-colors cursor-pointer"
                  onClick={() => onWorkflowClick?.(workflow)}
                >
                  <td className="px-6 py-4">
                    <div className="font-semibold">{workflow.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {workflow.description}
                    </div>
                  </td>

                  <td className="px-6 py-4 text-sm">
                    {workflow.user}
                  </td>

                  <td className="px-6 py-4 text-sm">
                    {workflow.department}
                  </td>

                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {workflow.created}
                  </td>

                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {workflow.lastRun}
                  </td>

                  <td className="px-6 py-4">
                    {workflow.failedRuns !== null ? (
                      <div className="flex items-center gap-1.5 text-sm text-red-500">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full border border-red-500">
                         <X className="h-3 w-3" />
                        </span>
                        <span className="font-medium">{workflow.failedRuns}</span>
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </td>

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
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Rows per page
          </div>
          <div className="flex items-center gap-2">
            <button className="px-4 py-2 rounded-lg border bg-card hover:bg-muted text-sm">
              Previous
            </button>
            <button className="px-4 py-2 rounded-lg border bg-card hover:bg-muted text-sm">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}