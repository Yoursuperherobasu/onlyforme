import {
  Activity,
  BarChart3,
  LineChart,
} from "lucide-react";
import { useContext, useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart as ReLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart as ReBarChart,
  Bar,
  PieChart as RePieChart,
  Pie,
  Cell,
} from "recharts";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTranslation } from "react-i18next";
import { AuthContext } from "@/contexts/authContext";

type SectionId =
  | "platform"
  | "governance"
  | "cost"
  | "lifecycle"
  | "usage"
  | "approval"
  | "hitl"
  | "rag"
  | "quality"
  | "performance"
  | "code"
  | "productivity"
  | "experience"
  | "roi"
  | "maturity"
  | "risk";

type SectionKpi = {
  name: string;
  value: string;
};

type ChartType = "line" | "bar" | "donut";

type SectionChart = {
  title: string;
  subtitle: string;
  type: ChartType;
  data: { label: string; value: number }[];
};

type SectionConfig = {
  id: SectionId;
  label: string;
  headline: string;
  kpis: SectionKpi[];
  charts: SectionChart[];
};

const sections: SectionConfig[] = [
  {
    id: "platform",
    label: " Platform Health & Reliability",
    headline: "Platform Health & Reliability KPIs",
    kpis: [
      { name: "Platform Uptime", value: "99.96%" },
      { name: "API Latency P95", value: "212ms" },
      { name: "API Latency P99", value: "460ms" },
      { name: "Error Rate %", value: "0.38%" },
      { name: "Concurrent Agent Runs", value: "148" },
      { name: "AKS Pod Scaling Events", value: "26" },
    ],
    charts: [
      {
        title: "Latency Trend",
        subtitle: "P95 over last 24 hours",
        type: "line",
        data: [
          { label: "00", value: 240 },
          { label: "04", value: 228 },
          { label: "08", value: 215 },
          { label: "12", value: 220 },
          { label: "16", value: 210 },
          { label: "20", value: 198 },
        ],
      },
      {
        title: "Error Mix",
        subtitle: "Top error families",
        type: "donut",
        data: [
          { label: "Timeouts", value: 42 },
          { label: "Rate limits", value: 28 },
          { label: "Downstream 5xx", value: 18 },
          { label: "Client 4xx", value: 12 },
        ],
      },
      {
        title: "Scaling Events",
        subtitle: "Pods added by hour",
        type: "bar",
        data: [
          { label: "00", value: 1 },
          { label: "04", value: 2 },
          { label: "08", value: 6 },
          { label: "12", value: 5 },
          { label: "16", value: 7 },
          { label: "20", value: 5 },
        ],
      },
    ],
  },
  {
    id: "governance",
    label: " Governance & Guardrail",
    headline: "Governance & Guardrail KPIs",
    kpis: [
      { name: "Guardrail Violation Rate", value: "0.7%" },
      { name: "Policy Breach Attempts", value: "41" },
      { name: "Data Leakage Prevention Count", value: "18" },
      { name: "Unsafe Content Interception", value: "63" },
      { name: "Escalation to Human Review", value: "96" },
      { name: "% Agents Without Guardrails", value: "12%" },
    ],
    charts: [
      {
        title: "Violation Rate",
        subtitle: "Weekly trend",
        type: "line",
        data: [
          { label: "Mon", value: 0.6 },
          { label: "Tue", value: 0.7 },
          { label: "Wed", value: 0.5 },
          { label: "Thu", value: 0.9 },
          { label: "Fri", value: 0.7 },
          { label: "Sat", value: 0.4 },
          { label: "Sun", value: 0.5 },
        ],
      },
      {
        title: "Breach Attempts",
        subtitle: "Daily counts",
        type: "bar",
        data: [
          { label: "Mon", value: 6 },
          { label: "Tue", value: 8 },
          { label: "Wed", value: 5 },
          { label: "Thu", value: 9 },
          { label: "Fri", value: 7 },
          { label: "Sat", value: 3 },
          { label: "Sun", value: 3 },
        ],
      },
      {
        title: "Guardrail Coverage",
        subtitle: "Agents by policy status",
        type: "donut",
        data: [
          { label: "Full", value: 68 },
          { label: "Partial", value: 20 },
          { label: "Missing", value: 12 },
        ],
      },
    ],
  },
  {
    id: "cost",
    label: " Cost & Financial",
    headline: "Cost & Financial KPIs",
    kpis: [
      { name: "Total Token Consumption", value: "92.4M" },
      { name: "Cost per Agent Run (Avg)", value: "$0.21" },
      { name: "Cost per Run P95", value: "$0.39" },
      { name: "Cost per Run P99", value: "$0.62" },
      { name: "Monthly Cost Trend", value: "+6.2%" },
      { name: "Cost per Successful Task", value: "$1.14" },
      { name: "Embedding Storage Growth", value: "+18%" },
      { name: "Pinecone Query Cost P95", value: "$0.08" },
    ],
    charts: [
      {
        title: "Token Consumption",
        subtitle: "Last 7 days",
        type: "line",
        data: [
          { label: "Mon", value: 12 },
          { label: "Tue", value: 14 },
          { label: "Wed", value: 13 },
          { label: "Thu", value: 16 },
          { label: "Fri", value: 15 },
          { label: "Sat", value: 11 },
          { label: "Sun", value: 11 },
        ],
      },
      {
        title: "Cost per Run",
        subtitle: "Distribution",
        type: "bar",
        data: [
          { label: "P50", value: 18 },
          { label: "P75", value: 26 },
          { label: "P95", value: 39 },
          { label: "P99", value: 62 },
        ],
      },
      {
        title: "Cost Drivers",
        subtitle: "Spend by source",
        type: "donut",
        data: [
          { label: "LLM Calls", value: 52 },
          { label: "RAG Queries", value: 24 },
          { label: "Storage", value: 14 },
          { label: "Infra", value: 10 },
        ],
      },
    ],
  },
  {
    id: "lifecycle",
    label: " Environment & Lifecycle",
    headline: "Environment & Lifecycle Governance",
    kpis: [
      { name: "Agents in UAT", value: "18" },
      { name: "UAT to Prod Conversion Rate", value: "72%" },
      { name: "Avg UAT Duration", value: "5.6 days" },
      { name: "Deprecated Agents Count", value: "9" },
      { name: "Version Rollbacks", value: "3" },
    ],
    charts: [
      {
        title: "Environment Flow",
        subtitle: "Agents by stage",
        type: "bar",
        data: [
          { label: "Dev", value: 32 },
          { label: "UAT", value: 18 },
          { label: "Staging", value: 14 },
          { label: "Prod", value: 62 },
        ],
      },
      {
        title: "UAT Duration",
        subtitle: "Average days",
        type: "line",
        data: [
          { label: "W1", value: 6.2 },
          { label: "W2", value: 5.8 },
          { label: "W3", value: 5.6 },
          { label: "W4", value: 5.2 },
        ],
      },
      {
        title: "Rollback Reasons",
        subtitle: "Top causes",
        type: "donut",
        data: [
          { label: "Quality", value: 40 },
          { label: "Policy", value: 22 },
          { label: "Latency", value: 20 },
          { label: "Infra", value: 18 },
        ],
      },
    ],
  },
];

const departmentSections: SectionConfig[] = [
  {
    id: "usage",
    label: " Department Usage",
    headline: "Department Usage KPIs",
    kpis: [
      { name: "Active Agents in Dept", value: "42" },
      { name: "Agent Success Rate", value: "94%" },
      { name: "Department Token Usage", value: "8.6M" },
      { name: "Avg Response Time", value: "640ms" },
      { name: "Run/Stop Frequency", value: "128" },
    ],
    charts: [
      {
        title: "Token Usage",
        subtitle: "Last 7 days",
        type: "line",
        data: [
          { label: "Mon", value: 1.1 },
          { label: "Tue", value: 1.3 },
          { label: "Wed", value: 1.2 },
          { label: "Thu", value: 1.5 },
          { label: "Fri", value: 1.4 },
          { label: "Sat", value: 1.0 },
          { label: "Sun", value: 1.1 },
        ],
      },
      {
        title: "Agent Success",
        subtitle: "Completion rate",
        type: "bar",
        data: [
          { label: "P50", value: 90 },
          { label: "P75", value: 93 },
          { label: "P95", value: 96 },
          { label: "P99", value: 98 },
        ],
      },
      {
        title: "Run/Stop Mix",
        subtitle: "Operational pattern",
        type: "donut",
        data: [
          { label: "Runs", value: 78 },
          { label: "Stops", value: 22 },
        ],
      },
    ],
  },
  {
    id: "approval",
    label: " Approval & Governance",
    headline: "Approval & Governance KPIs",
    kpis: [
      { name: "Pending Approvals", value: "31" },
      { name: "Avg Approval Time", value: "4.6 hrs" },
      { name: "Rejection Rate", value: "7.4%" },
      { name: "Rework Cycles", value: "2.1" },
      { name: "Escalations to Super Admin", value: "6" },
    ],
    charts: [
      {
        title: "Pending Approvals",
        subtitle: "Queue trend",
        type: "line",
        data: [
          { label: "Mon", value: 22 },
          { label: "Tue", value: 24 },
          { label: "Wed", value: 28 },
          { label: "Thu", value: 31 },
          { label: "Fri", value: 27 },
          { label: "Sat", value: 19 },
          { label: "Sun", value: 21 },
        ],
      },
      {
        title: "Approval Time",
        subtitle: "Hours by stage",
        type: "bar",
        data: [
          { label: "Review", value: 2.1 },
          { label: "QA", value: 1.4 },
          { label: "Legal", value: 0.7 },
          { label: "Sign-off", value: 0.4 },
        ],
      },
      {
        title: "Outcome Mix",
        subtitle: "Approval outcomes",
        type: "donut",
        data: [
          { label: "Approved", value: 78 },
          { label: "Rejected", value: 12 },
          { label: "Rework", value: 10 },
        ],
      },
    ],
  },
  {
    id: "hitl",
    label: " HITL Governance",
    headline: "HITL Governance KPIs",
    kpis: [
      { name: "HITL Invocation Rate", value: "3.6%" },
      { name: "Avg HITL Response Time", value: "12 min" },
      { name: "HITL Override Rate", value: "1.1%" },
    ],
    charts: [
      {
        title: "Invocation Rate",
        subtitle: "Daily trend",
        type: "line",
        data: [
          { label: "Mon", value: 3.9 },
          { label: "Tue", value: 3.7 },
          { label: "Wed", value: 3.5 },
          { label: "Thu", value: 3.8 },
          { label: "Fri", value: 3.6 },
          { label: "Sat", value: 3.2 },
          { label: "Sun", value: 3.4 },
        ],
      },
      {
        title: "Response Time",
        subtitle: "Minutes by day",
        type: "bar",
        data: [
          { label: "Mon", value: 14 },
          { label: "Tue", value: 12 },
          { label: "Wed", value: 11 },
          { label: "Thu", value: 13 },
          { label: "Fri", value: 12 },
        ],
      },
      {
        title: "Override Mix",
        subtitle: "Override outcomes",
        type: "donut",
        data: [
          { label: "Accepted", value: 68 },
          { label: "Modified", value: 22 },
          { label: "Rejected", value: 10 },
        ],
      },
    ],
  },
  {
    id: "rag",
    label: " RAG Governance",
    headline: "RAG Governance KPIs",
    kpis: [
      { name: "Total Documents Indexed", value: "420K" },
      { name: "Vector DB Growth Rate", value: "+12%" },
      { name: "RAG Retrieval Accuracy", value: "91%" },
      { name: "Sensitive Data Classification", value: "2.4%" },
      { name: "Data Deletion Requests", value: "14" },
      { name: "Pinecone Query Latency P95", value: "190ms" },
    ],
    charts: [
      {
        title: "Retrieval Accuracy",
        subtitle: "Weekly trend",
        type: "line",
        data: [
          { label: "W1", value: 88 },
          { label: "W2", value: 89 },
          { label: "W3", value: 90 },
          { label: "W4", value: 91 },
        ],
      },
      {
        title: "Index Growth",
        subtitle: "Docs per week",
        type: "bar",
        data: [
          { label: "W1", value: 90 },
          { label: "W2", value: 110 },
          { label: "W3", value: 120 },
          { label: "W4", value: 100 },
        ],
      },
      {
        title: "Data Requests",
        subtitle: "Request types",
        type: "donut",
        data: [
          { label: "Deletion", value: 14 },
          { label: "Correction", value: 9 },
          { label: "Access", value: 6 },
        ],
      },
    ],
  },
];

const developerSections: SectionConfig[] = [
  {
    id: "quality",
    label: " Agent Quality",
    headline: "Agent Quality KPIs (Langfuse Evaluations)",
    kpis: [
      { name: "Task Success Rate", value: "93%" },
      { name: "Hallucination Score", value: "2.1%" },
      { name: "RAG Relevance Score", value: "0.84" },
      { name: "Tool Call Accuracy", value: "96%" },
      { name: "Retry Rate", value: "3.4%" },
    ],
    charts: [
      {
        title: "Success Rate",
        subtitle: "Completion trend",
        type: "line",
        data: [
          { label: "Mon", value: 90 },
          { label: "Tue", value: 92 },
          { label: "Wed", value: 91 },
          { label: "Thu", value: 93 },
          { label: "Fri", value: 94 },
          { label: "Sat", value: 92 },
          { label: "Sun", value: 93 },
        ],
      },
      {
        title: "Hallucinations",
        subtitle: "Rate by day",
        type: "bar",
        data: [
          { label: "Mon", value: 2.6 },
          { label: "Tue", value: 2.4 },
          { label: "Wed", value: 2.2 },
          { label: "Thu", value: 2.1 },
          { label: "Fri", value: 2.0 },
        ],
      },
      {
        title: "Quality Mix",
        subtitle: "Eval buckets",
        type: "donut",
        data: [
          { label: "Pass", value: 78 },
          { label: "Needs review", value: 16 },
          { label: "Fail", value: 6 },
        ],
      },
    ],
  },
  {
    id: "performance",
    label: " Performance",
    headline: "Performance KPIs",
    kpis: [
      { name: "Avg Agent Latency", value: "610ms" },
      { name: "Latency P95", value: "920ms" },
      { name: "Latency P99", value: "1.4s" },
      { name: "Token Usage per Run", value: "2.1K" },
      { name: "Embedding Query Latency", value: "140ms" },
      { name: "Max Graph Depth", value: "18" },
    ],
    charts: [
      {
        title: "Latency Trend",
        subtitle: "P95 by day",
        type: "line",
        data: [
          { label: "Mon", value: 980 },
          { label: "Tue", value: 950 },
          { label: "Wed", value: 930 },
          { label: "Thu", value: 920 },
          { label: "Fri", value: 910 },
          { label: "Sat", value: 900 },
          { label: "Sun", value: 920 },
        ],
      },
      {
        title: "Token Usage",
        subtitle: "Tokens per run",
        type: "bar",
        data: [
          { label: "P50", value: 1.6 },
          { label: "P75", value: 1.9 },
          { label: "P95", value: 2.4 },
          { label: "P99", value: 2.9 },
        ],
      },
      {
        title: "Latency Budget",
        subtitle: "Component share",
        type: "donut",
        data: [
          { label: "LLM", value: 52 },
          { label: "RAG", value: 26 },
          { label: "Tools", value: 14 },
          { label: "Infra", value: 8 },
        ],
      },
    ],
  },
  {
    id: "code",
    label: " Code & Version Governance",
    headline: "Code & Version Governance KPIs",
    kpis: [
      { name: "Version Count per Agent", value: "7" },
      { name: "Rollback Count", value: "2" },
      { name: "Compilation Failure Rate", value: "1.8%" },
      { name: "Custom Components Used", value: "5" },
    ],
    charts: [
      {
        title: "Rollbacks",
        subtitle: "Weekly count",
        type: "line",
        data: [
          { label: "W1", value: 1 },
          { label: "W2", value: 2 },
          { label: "W3", value: 1 },
          { label: "W4", value: 2 },
        ],
      },
      {
        title: "Failures",
        subtitle: "Build failures",
        type: "bar",
        data: [
          { label: "Lint", value: 6 },
          { label: "Type", value: 4 },
          { label: "Test", value: 3 },
          { label: "Build", value: 2 },
        ],
      },
      {
        title: "Version Mix",
        subtitle: "Change types",
        type: "donut",
        data: [
          { label: "Patch", value: 56 },
          { label: "Minor", value: 28 },
          { label: "Major", value: 16 },
        ],
      },
    ],
  },
];

const businessSections: SectionConfig[] = [
  {
    id: "productivity",
    label: " Productivity",
    headline: "Productivity KPIs",
    kpis: [
      { name: "Tasks Completed", value: "1,240" },
      { name: "Avg Task Completion Time", value: "6.4 min" },
      { name: "Task Completion Without Escalation", value: "92%" },
      { name: "Time Saved Estimate", value: "4.8 hrs" },
    ],
    charts: [
      {
        title: "Tasks Completed",
        subtitle: "Weekly trend",
        type: "line",
        data: [
          { label: "Mon", value: 160 },
          { label: "Tue", value: 185 },
          { label: "Wed", value: 172 },
          { label: "Thu", value: 198 },
          { label: "Fri", value: 210 },
          { label: "Sat", value: 165 },
          { label: "Sun", value: 150 },
        ],
      },
      {
        title: "Completion Time",
        subtitle: "Minutes by day",
        type: "bar",
        data: [
          { label: "Mon", value: 6.8 },
          { label: "Tue", value: 6.4 },
          { label: "Wed", value: 6.2 },
          { label: "Thu", value: 6.0 },
          { label: "Fri", value: 5.9 },
        ],
      },
      {
        title: "Escalation Mix",
        subtitle: "With vs without escalation",
        type: "donut",
        data: [
          { label: "No escalation", value: 92 },
          { label: "Escalated", value: 8 },
        ],
      },
    ],
  },
  {
    id: "experience",
    label: " Experience",
    headline: "Experience KPIs",
    kpis: [
      { name: "Avg Response Time", value: "820ms" },
      { name: "User Satisfaction Score", value: "4.6/5" },
      { name: "Re-run Rate", value: "6.2%" },
      { name: "Escalation to Human", value: "3.1%" },
      { name: "Session Duration", value: "8.4 min" },
    ],
    charts: [
      {
        title: "Response Time",
        subtitle: "Daily trend",
        type: "line",
        data: [
          { label: "Mon", value: 920 },
          { label: "Tue", value: 880 },
          { label: "Wed", value: 860 },
          { label: "Thu", value: 840 },
          { label: "Fri", value: 820 },
          { label: "Sat", value: 800 },
          { label: "Sun", value: 810 },
        ],
      },
      {
        title: "Satisfaction Score",
        subtitle: "Avg rating",
        type: "bar",
        data: [
          { label: "Mon", value: 4.4 },
          { label: "Tue", value: 4.5 },
          { label: "Wed", value: 4.6 },
          { label: "Thu", value: 4.6 },
          { label: "Fri", value: 4.7 },
        ],
      },
      {
        title: "Experience Mix",
        subtitle: "Key outcomes",
        type: "donut",
        data: [
          { label: "Satisfied", value: 78 },
          { label: "Neutral", value: 16 },
          { label: "Unsatisfied", value: 6 },
        ],
      },
    ],
  },
];

const rootSections: SectionConfig[] = [
  {
    id: "roi",
    label: " ROI & Financial Health",
    headline: "ROI & Financial Health",
    kpis: [
      { name: "Cost vs Productivity Gain", value: "2.6x" },
      { name: "Automation Savings", value: "1,420 hrs" },
      { name: "Cost Trend (Monthly)", value: "+4.1%" },
      { name: "Cost P95 Trends", value: "$0.42" },
      { name: "Single Model Dependency %", value: "38%" },
    ],
    charts: [
      {
        title: "ROI Ratio",
        subtitle: "Quarterly trend",
        type: "line",
        data: [
          { label: "Q1", value: 2.1 },
          { label: "Q2", value: 2.3 },
          { label: "Q3", value: 2.5 },
          { label: "Q4", value: 2.6 },
        ],
      },
      {
        title: "Automation Savings",
        subtitle: "Hours saved",
        type: "bar",
        data: [
          { label: "Ops", value: 420 },
          { label: "Support", value: 360 },
          { label: "Sales", value: 310 },
          { label: "IT", value: 330 },
        ],
      },
      {
        title: "Spend Drivers",
        subtitle: "Budget mix",
        type: "donut",
        data: [
          { label: "LLM", value: 52 },
          { label: "Infra", value: 24 },
          { label: "RAG", value: 14 },
          { label: "Other", value: 10 },
        ],
      },
    ],
  },
  {
    id: "maturity",
    label: " AI Maturity Indicators",
    headline: "AI Maturity Indicators",
    kpis: [
      { name: "% Agents with Guardrails", value: "88%" },
      { name: "% Agents with RAG", value: "64%" },
      { name: "% Agents with HITL", value: "41%" },
      { name: "Multi-Agent Adoption %", value: "36%" },
    ],
    charts: [
      {
        title: "Adoption Progress",
        subtitle: "Maturity trend",
        type: "line",
        data: [
          { label: "Q1", value: 22 },
          { label: "Q2", value: 28 },
          { label: "Q3", value: 33 },
          { label: "Q4", value: 36 },
        ],
      },
      {
        title: "Coverage Mix",
        subtitle: "Guardrails vs RAG",
        type: "bar",
        data: [
          { label: "Guardrails", value: 88 },
          { label: "RAG", value: 64 },
          { label: "HITL", value: 41 },
          { label: "Multi-agent", value: 36 },
        ],
      },
      {
        title: "Maturity Split",
        subtitle: "By category",
        type: "donut",
        data: [
          { label: "Compliance", value: 38 },
          { label: "Knowledge", value: 24 },
          { label: "Risk", value: 20 },
          { label: "Innovation", value: 18 },
        ],
      },
    ],
  },
  {
    id: "risk",
    label: " Enterprise Risk Indicators",
    headline: "Enterprise Risk Indicators",
    kpis: [
      { name: "High-Risk Autonomous Agents", value: "6" },
      { name: "Guardrail Bypass Attempts", value: "14" },
      { name: "Data Leakage Incidents", value: "2" },
      { name: "Audit Readiness Score", value: "92%" },
    ],
    charts: [
      {
        title: "Risk Events",
        subtitle: "Monthly trend",
        type: "line",
        data: [
          { label: "Jan", value: 4 },
          { label: "Feb", value: 6 },
          { label: "Mar", value: 5 },
          { label: "Apr", value: 3 },
        ],
      },
      {
        title: "Incident Types",
        subtitle: "Count by type",
        type: "bar",
        data: [
          { label: "Bypass", value: 14 },
          { label: "Leakage", value: 2 },
          { label: "Policy", value: 6 },
          { label: "Other", value: 4 },
        ],
      },
      {
        title: "Risk Mix",
        subtitle: "Severity split",
        type: "donut",
        data: [
          { label: "Low", value: 58 },
          { label: "Medium", value: 30 },
          { label: "High", value: 12 },
        ],
      },
    ],
  },
];

const chartColors = ["#2563eb", "#14b8a6", "#f97316", "#a855f7"];

const kpiCardStyles = [
  "from-sky-50 via-white to-white ring-sky-200/60",
  "from-emerald-50 via-white to-white ring-emerald-200/60",
  "from-amber-50 via-white to-white ring-amber-200/60",
  "from-violet-50 via-white to-white ring-violet-200/60",
];

const sectionThemes: Record<SectionId, { glow: string; badge: string }> = {
  platform: {
    glow: "from-sky-500/25 via-indigo-500/15 to-transparent",
    badge: "bg-sky-100 text-sky-700",
  },
  governance: {
    glow: "from-emerald-500/25 via-cyan-500/15 to-transparent",
    badge: "bg-emerald-100 text-emerald-700",
  },
  cost: {
    glow: "from-amber-500/25 via-orange-500/15 to-transparent",
    badge: "bg-amber-100 text-amber-700",
  },
  lifecycle: {
    glow: "from-violet-500/25 via-fuchsia-500/15 to-transparent",
    badge: "bg-violet-100 text-violet-700",
  },
  usage: {
    glow: "from-sky-500/20 via-blue-500/15 to-transparent",
    badge: "bg-sky-100 text-sky-700",
  },
  approval: {
    glow: "from-amber-500/20 via-orange-500/15 to-transparent",
    badge: "bg-amber-100 text-amber-700",
  },
  hitl: {
    glow: "from-emerald-500/20 via-teal-500/15 to-transparent",
    badge: "bg-emerald-100 text-emerald-700",
  },
  rag: {
    glow: "from-violet-500/20 via-fuchsia-500/15 to-transparent",
    badge: "bg-violet-100 text-violet-700",
  },
  quality: {
    glow: "from-sky-500/20 via-blue-500/15 to-transparent",
    badge: "bg-sky-100 text-sky-700",
  },
  performance: {
    glow: "from-emerald-500/20 via-teal-500/15 to-transparent",
    badge: "bg-emerald-100 text-emerald-700",
  },
  code: {
    glow: "from-amber-500/20 via-orange-500/15 to-transparent",
    badge: "bg-amber-100 text-amber-700",
  },
  productivity: {
    glow: "from-sky-500/20 via-blue-500/15 to-transparent",
    badge: "bg-sky-100 text-sky-700",
  },
  experience: {
    glow: "from-emerald-500/20 via-teal-500/15 to-transparent",
    badge: "bg-emerald-100 text-emerald-700",
  },
  roi: {
    glow: "from-sky-500/20 via-blue-500/15 to-transparent",
    badge: "bg-sky-100 text-sky-700",
  },
  maturity: {
    glow: "from-emerald-500/20 via-teal-500/15 to-transparent",
    badge: "bg-emerald-100 text-emerald-700",
  },
  risk: {
    glow: "from-amber-500/20 via-orange-500/15 to-transparent",
    badge: "bg-amber-100 text-amber-700",
  },
};

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-white px-3 py-2 text-xs shadow">
      <p className="font-semibold text-slate-900">{label}</p>
      <p className="text-slate-600">{payload[0].value}</p>
    </div>
  );
}

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-white px-3 py-2 text-xs shadow">
      <p className="font-semibold text-slate-900">{payload[0].name}</p>
      <p className="text-slate-600">{payload[0].value}</p>
    </div>
  );
}

function ChartBlock({ chart }: { chart: SectionChart }) {
  if (chart.type === "line") {
    return (
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <ReLineChart data={chart.data} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#64748b" }} />
            <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
            <Tooltip content={<ChartTooltip />} />
            <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={false} />
          </ReLineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "bar") {
    return (
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <ReBarChart data={chart.data} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#64748b" }} />
            <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
              {chart.data.map((entry, index) => (
                <Cell key={entry.label} fill={chartColors[index % chartColors.length]} />
              ))}
            </Bar>
          </ReBarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="flex h-48 items-center gap-4">
      <ResponsiveContainer width="55%" height="100%">
        <RePieChart>
          <Pie data={chart.data} dataKey="value" nameKey="label" innerRadius={40} outerRadius={68} paddingAngle={2}>
            {chart.data.map((entry, index) => (
              <Cell key={entry.label} fill={chartColors[index % chartColors.length]} />
            ))}
          </Pie>
          <Tooltip content={<DonutTooltip />} />
        </RePieChart>
      </ResponsiveContainer>
      <div className="space-y-2">
        {chart.data.map((slice, index) => (
          <div key={slice.label} className="flex items-center gap-2 text-sm">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: chartColors[index % chartColors.length] }}
            />
            <span className="text-muted-foreground">{slice.label}</span>
            <span className="font-semibold">{slice.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardAdmin(): JSX.Element {
  const { t } = useTranslation();
  const { role } = useContext(AuthContext);
  const normalizedRole = (role ?? "").toLowerCase().trim().replace(/\s+/g, "_");
  const isDepartmentAdmin = normalizedRole === "department_admin";
  const isDeveloper = normalizedRole === "developer";
  const isBusinessUser = normalizedRole === "business_user";
  const isRootAdmin = normalizedRole === "root";
  const defaultSectionId: SectionId = isDepartmentAdmin
    ? "usage"
    : isDeveloper
      ? "quality"
      : isBusinessUser
        ? "productivity"
        : isRootAdmin
          ? "roi"
          : "platform";
  const [sectionId, setSectionId] = useState<SectionId>(defaultSectionId);

  useEffect(() => {
    setSectionId(defaultSectionId);
  }, [defaultSectionId]);

  const sectionsToRender = isDepartmentAdmin
    ? departmentSections
    : isDeveloper
      ? developerSections
      : isBusinessUser
        ? businessSections
        : isRootAdmin
          ? rootSections
          : sections;
  const activeSection = useMemo(
    () => sectionsToRender.find((section) => section.id === sectionId) ?? sectionsToRender[0],
    [sectionId, sectionsToRender],
  );

  const theme = sectionThemes[activeSection.id];
  const headerSubtitle = isDepartmentAdmin
    ? "Department Admin - Operational Governance"
    : isDeveloper
      ? "Developer - Build & Optimize"
      : isBusinessUser
        ? "Business User - Productivity & Experience"
        : isRootAdmin
          ? "Executive - Strategic Oversight"
          : "Super Admin KPI view with role-based sections";
  const heroDescription = isDepartmentAdmin
    ? "Department-level performance, compliance enforcement, and budget control."
    : isDeveloper
      ? "Reliability, accuracy, performance, cost efficiency."
      : isBusinessUser
        ? "Efficiency, reliability, satisfaction."
        : isRootAdmin
          ? "ROI, maturity, risk posture, innovation velocity."
          : "Executive KPI snapshot with curated charts and metrics.";

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="flex-shrink-0 border-b bg-card">
        <div className="px-8 py-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold">{t("Dashboard")}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {t(headerSubtitle)}
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Select value={sectionId} onValueChange={(value) => setSectionId(value as SectionId)}>
                <SelectTrigger className="w-[280px]">
                  <SelectValue placeholder={t("Select KPI section")} />
                </SelectTrigger>
                <SelectContent>
                  {sectionsToRender.map((section) => (
                    <SelectItem key={section.id} value={section.id}>
                      {t(section.label)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-slate-50/60 px-8 py-6">
        <div className="relative">
          <div className="pointer-events-none absolute inset-0 rounded-3xl bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.12),_transparent_55%),radial-gradient(circle_at_80%_20%,_rgba(16,185,129,0.12),_transparent_50%)]" />
          <div className="relative rounded-3xl border bg-white/80 p-6 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="relative overflow-hidden rounded-2xl border bg-white p-6 text-slate-900">
              <div className={`absolute -right-24 -top-24 h-56 w-56 rounded-full bg-gradient-to-br ${theme.glow} blur-3xl`} />
              <div className="relative">
                <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${theme.badge}`}>
                  {t(activeSection.label)}
                </span>
                <h2 className="mt-3 text-3xl font-semibold">{t(activeSection.headline)}</h2>
                <p className="mt-2 text-sm text-slate-500">
                  {t(heroDescription)}
                </p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {activeSection.kpis.map((kpi, index) => (
                <div
                  key={kpi.name}
                  className={`rounded-2xl border bg-gradient-to-br ${kpiCardStyles[index % kpiCardStyles.length]} p-4 ring-1 shadow-sm`}
                >
                  <div className="h-1 w-10 rounded-full bg-gradient-to-r from-slate-900 via-slate-400 to-slate-100" />
                  <p className="mt-3 text-xs uppercase tracking-wide text-muted-foreground">
                    {t(kpi.name)}
                  </p>
                  <p className="mt-3 text-2xl font-semibold text-slate-900">{t(kpi.value)}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-3">
              {activeSection.charts.map((chart) => (
                <div
                  key={chart.title}
                  className="rounded-2xl border bg-white/90 p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">{t(chart.title)}</h3>
                      <p className="text-xs text-muted-foreground">{t(chart.subtitle)}</p>
                    </div>
                    <div className="rounded-full bg-slate-100 p-2">
                      {chart.type === "line" ? (
                        <LineChart className="h-4 w-4 text-slate-600" />
                      ) : chart.type === "bar" ? (
                        <BarChart3 className="h-4 w-4 text-slate-600" />
                      ) : (
                        <Activity className="h-4 w-4 text-slate-600" />
                      )}
                    </div>
                  </div>
                  <div className="mt-4">
                    <ChartBlock chart={chart} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
