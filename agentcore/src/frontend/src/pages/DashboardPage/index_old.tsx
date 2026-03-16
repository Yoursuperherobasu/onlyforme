import {
  Activity,
  BarChart3,
  LineChart,
  TrendingUp,
  TrendingDown,
  Minus,
  ShieldCheck,
  Zap,
  Database,
  Users,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  Layers,
  Bot,
  GitBranch,
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
  Area,
  AreaChart,
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
import { api } from "@/controllers/API/api";

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
  trend?: "up" | "down" | "neutral";
  delta?: string;
  status?: "good" | "warn" | "bad" | "neutral";
};

type ChartType = "line" | "bar" | "donut" | "area";

type LineConfig = {
  key: string;
  color: string;
};

type SectionChart = {
  title: string;
  subtitle: string;
  type: ChartType;
  data: { label: string; value?: number; [key: string]: number | string | undefined }[];
  lines?: LineConfig[];
  xKey?: string;
  xType?: "number" | "category";
  xTickFormatter?: (value: number) => string;
  placeholder?: boolean;
};

type SectionConfig = {
  id: SectionId;
  label: string;
  headline: string;
  description?: string;
  icon?: string;
  summaryStats?: { label: string; value: string; sub?: string }[];
  kpis: SectionKpi[];
  charts: SectionChart[];
};

type DashboardKpiApi = {
  id: string;
  label: string;
  value: number;
  unit?: string | null;
};

type DashboardSectionApiResponse = {
  section: string;
  kpis: DashboardKpiApi[];
};

type PendingSeriesPoint = {
  date: string;
  value: number;
};

type PendingSeriesResponse = {
  range: string;
  series: PendingSeriesPoint[];
};

type HitlSeriesResponse = {
  range: string;
  series: PendingSeriesPoint[];
};

const sections: SectionConfig[] = [
  {
    id: "platform",
    label: " Platform Health & Reliability",
    headline: "Platform Health & Reliability KPIs",
    description: "Real-time observability of infrastructure uptime, latency, and resource saturation across your AKS cluster.",
    summaryStats: [
      { label: "Cluster Status", value: "Healthy", sub: "All nodes operational" },
      { label: "SLA Target", value: "99.9%", sub: "30-day rolling" },
      { label: "Last Incident", value: "12 days ago", sub: "P2 resolved" },
    ],
    kpis: [
      { name: "Platform Uptime %", value: "--", status: "good" },
      { name: "API Latency P95", value: "--", status: "neutral" },
      { name: "API Latency P99", value: "--", status: "neutral" },
      { name: "Error Rate %", value: "--", status: "neutral" },
      { name: "AKS Pod Scaling Events", value: "--", status: "neutral" },
      { name: "CPU/Memory Saturation %", value: "--", status: "neutral" },
    ],
    charts: [
      {
        title: "API Latency P95 vs P99",
        subtitle: "Latency comparison (24h)",
        type: "line",
        data: [],
        lines: [
          { key: "p95", color: "#2563eb" },
          { key: "p99", color: "#f97316" },
        ],
        xKey: "ts",
        xType: "number",
        xTickFormatter: (value) =>
          new Date(value * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      },
      {
        title: "Error Rate Trend",
        subtitle: "Error rate over time (24h)",
        type: "area",
        data: [],
        xKey: "ts",
        xType: "number",
        xTickFormatter: (value) =>
          new Date(value * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      },
      {
        title: "CPU & Memory Saturation",
        subtitle: "Cluster utilization (24h)",
        type: "line",
        data: [],
        lines: [
          { key: "cpu", color: "#0ea5e9" },
          { key: "memory", color: "#14b8a6" },
        ],
        xKey: "ts",
        xType: "number",
        xTickFormatter: (value) =>
          new Date(value * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      },
    ],
  },
  {
    id: "governance",
    label: " Governance & Guardrail",
    headline: "Governance & Guardrail KPIs",
    description: "Monitor policy enforcement, unsafe content interception, and the percentage of agents operating without guardrails.",
    summaryStats: [
      { label: "Policy Status", value: "Enforced", sub: "All critical policies active" },
      { label: "Agents Compliant", value: "88%", sub: "Target: 95%" },
      { label: "Review Queue", value: "96 items", sub: "Avg resolution 4h" },
    ],
    kpis: [
      { name: "Guardrail Violation Rate", value: "0.7%", trend: "down", delta: "-0.2%", status: "good" },
      { name: "Policy Breach Attempts", value: "41", trend: "up", delta: "+7", status: "warn" },
      { name: "Unsafe Content Interception", value: "63", trend: "neutral", status: "neutral" },
      { name: "Escalation to Human Review", value: "96", trend: "up", delta: "+12", status: "warn" },
      { name: "% Agents Without Guardrails", value: "12%", trend: "down", delta: "-3%", status: "warn" },
    ],
    charts: [],
  },
  {
    id: "lifecycle",
    label: " Environment & Lifecycle",
    headline: "Environment & Lifecycle Governance",
    description: "Track agent promotion across UAT, staging, and production environments with deprecation and conversion metrics.",
    summaryStats: [
      { label: "Environments", value: "3 Active", sub: "Dev · UAT · Prod" },
      { label: "Pipeline Health", value: "Nominal", sub: "CI/CD gates passing" },
      { label: "Deprecated Agents", value: "Tracked", sub: "Cleanup in progress" },
    ],
    kpis: [],
    charts: [],
  },
];

const departmentSections: SectionConfig[] = [
  {
    id: "usage",
    label: " Department Usage",
    headline: "Department Usage KPIs",
    description: "Operational overview of active agents, success rates, token consumption, and response performance for your department.",
    summaryStats: [
      { label: "Total Active Agents", value: "60", sub: "42 UAT · 18 Prod" },
      { label: "Success Rate", value: "94%", sub: "+2% vs last week" },
      { label: "Token Consumption", value: "8.6M", sub: "This billing cycle" },
    ],
    kpis: [
      { name: "Active Agents in Dept (UAT)", value: "42", trend: "up", status: "good" },
      { name: "Active Agents in Dept (PROD)", value: "18", trend: "neutral", status: "neutral" },
      { name: "Agent Success Rate", value: "94%", trend: "up", delta: "+2%", status: "good" },
      { name: "Department Token Usage", value: "8.6M", trend: "up", delta: "+1.2M", status: "neutral" },
      { name: "Avg Response Time", value: "--", status: "neutral" },
    ],
    charts: [
      {
        title: "Response Time Trend",
        subtitle: "Avg response time over time",
        type: "area",
        data: [],
      },
    ],
  },
  {
    id: "approval",
    label: " Approval & Governance",
    headline: "Approval & Governance KPIs",
    description: "Track the approval pipeline — pending reviews, rejection rates, and time-to-decision for agent change requests.",
    summaryStats: [
      { label: "Queue Health", value: "Moderate", sub: "31 pending at peak" },
      { label: "Avg Cycle Time", value: "~6h", sub: "Target: <4h" },
      { label: "Rejection Rate", value: "Tracked", sub: "Review trends weekly" },
    ],
    kpis: [
      { name: "Pending Approvals", value: "--", status: "neutral" },
      { name: "Rejection Rate", value: "--", status: "neutral" },
      { name: "Avg Approval Time", value: "--", status: "neutral" },
    ],
    charts: [
      {
        title: "Pending Approvals",
        subtitle: "Queue trend",
        type: "area",
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
    ],
  },
  {
    id: "hitl",
    label: " HITL Governance",
    headline: "HITL Governance KPIs",
    description: "Human-in-the-loop invocation patterns, response time benchmarks, and escalation trends across automated agent workflows.",
    summaryStats: [
      { label: "Automation Rate", value: "96.4%", sub: "3.6% escalated to humans" },
      { label: "Avg Resolution", value: "12 min", sub: "Within SLA target" },
      { label: "Weekly Trend", value: "Stable", sub: "±0.2% variance" },
    ],
    kpis: [
      { name: "HITL Invocation Rate", value: "3.6%", trend: "down", delta: "-0.3%", status: "good" },
      { name: "Avg HITL Response Time", value: "12 min", trend: "neutral", status: "neutral" },
    ],
    charts: [
      {
        title: "Invocation Rate",
        subtitle: "Daily trend",
        type: "area",
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
    ],
  },
  {
    id: "rag",
    label: " RAG Governance",
    headline: "RAG Governance KPIs",
    description: "Document indexing health, retrieval accuracy, vector DB growth, and data governance compliance for your RAG pipeline.",
    summaryStats: [
      { label: "Index Health", value: "Healthy", sub: "420K docs indexed" },
      { label: "Retrieval Accuracy", value: "91%", sub: "+3% vs baseline" },
      { label: "Sensitive Data", value: "2.4%", sub: "Flagged & classified" },
    ],
    kpis: [
      { name: "Total Documents Indexed", value: "420K", trend: "up", delta: "+12%", status: "good" },
      { name: "Vector DB Growth Rate", value: "+12%", trend: "up", status: "neutral" },
      { name: "RAG Retrieval Accuracy", value: "91%", trend: "up", delta: "+1%", status: "good" },
      { name: "Sensitive Data Classification", value: "2.4%", trend: "neutral", status: "warn" },
      { name: "Data Deletion Requests", value: "14", trend: "neutral", status: "neutral" },
      { name: "Pinecone Query Latency P95", value: "190ms", trend: "down", delta: "-10ms", status: "good" },
    ],
    charts: [
      {
        title: "Retrieval Accuracy",
        subtitle: "Weekly trend",
        type: "area",
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
    description: "LLM evaluation scores tracking hallucination rates, RAG relevance, and tool call precision across deployed agents.",
    summaryStats: [
      { label: "Eval Coverage", value: "100%", sub: "All agents instrumented" },
      { label: "Overall Score", value: "A-", sub: "Above baseline threshold" },
      { label: "Last Eval Run", value: "2h ago", sub: "Scheduled: every 6h" },
    ],
    kpis: [
      { name: "Hallucination Score", value: "2.1%", trend: "down", delta: "-0.4%", status: "good" },
      { name: "RAG Relevance Score", value: "0.84", trend: "up", delta: "+0.03", status: "good" },
      { name: "Tool Call Accuracy", value: "96%", trend: "up", delta: "+1%", status: "good" },
    ],
    charts: [],
  },
  {
    id: "performance",
    label: " Performance",
    headline: "Performance KPIs",
    description: "Agent response latency profiles including average, P95, and P99 percentiles to identify tail latency issues.",
    summaryStats: [
      { label: "Latency SLA", value: "Meeting", sub: "P95 within target" },
      { label: "Outlier Agents", value: "2", sub: "Under investigation" },
      { label: "Benchmark", value: "Stable", sub: "No regressions detected" },
    ],
    kpis: [
      { name: "Avg Agent Latency", value: "--", status: "neutral" },
      { name: "Latency P95", value: "--", status: "neutral" },
      { name: "Latency P99", value: "--", status: "neutral" },
    ],
    charts: [
      {
        title: "API Latency P95 vs P99",
        subtitle: "Latency comparison",
        type: "line",
        data: [],
        lines: [
          { key: "p95", color: "#2563eb" },
          { key: "p99", color: "#f97316" },
        ],
        xKey: "ts",
        xType: "number",
        xTickFormatter: (value) =>
          new Date(value * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      },
    ],
  },
  {
    id: "code",
    label: " Code & Version Governance",
    headline: "Code & Version Governance KPIs",
    description: "Version control discipline, branching patterns, and agent code lifecycle management across the development org.",
    summaryStats: [
      { label: "Active Versions", value: "Tracked", sub: "Per agent versioning" },
      { label: "Rollback Events", value: "3 this month", sub: "All successful" },
      { label: "Deprecation Queue", value: "7 agents", sub: "Awaiting sign-off" },
    ],
    kpis: [
      { name: "Avg. Version Count of Agents", value: "--", status: "neutral" },
    ],
    charts: [],
  },
];

const businessSections: SectionConfig[] = [
  {
    id: "productivity",
    label: " Productivity",
    headline: "Productivity KPIs",
    description: "Business-level impact of AI automation — task throughput, hours saved, and workforce efficiency metrics.",
    summaryStats: [
      { label: "Automation Rate", value: "High", sub: "Above industry avg" },
      { label: "Hours Saved", value: "1,420 hrs", sub: "This quarter" },
      { label: "ROI Ratio", value: "2.6x", sub: "vs manual baseline" },
    ],
    kpis: [],
    charts: [],
  },
  {
    id: "experience",
    label: " Experience",
    headline: "Experience KPIs",
    description: "End-user experience signals — response speed, satisfaction scores, and escalation frequency to human agents.",
    summaryStats: [
      { label: "User Sentiment", value: "Positive", sub: "Based on satisfaction score" },
      { label: "Escalation Rate", value: "Tracked", sub: "Trending downward" },
      { label: "Response SLA", value: "Monitored", sub: "Live metric below" },
    ],
    kpis: [
      { name: "Avg Response Time", value: "--", status: "neutral" },
      { name: "User Satisfaction Score", value: "--", status: "neutral" },
      { name: "Escalation to Human", value: "--", status: "neutral" },
    ],
    charts: [
      {
        title: "Response Time",
        subtitle: "Daily trend",
        type: "area",
        data: [],
      },
    ],
  },
];

const rootSections: SectionConfig[] = [
  {
    id: "roi",
    label: " ROI & Financial Health",
    headline: "ROI & Financial Health",
    description: "Cost-efficiency ratios, automation savings, spend drivers, and model dependency risk for executive oversight.",
    summaryStats: [
      { label: "ROI Ratio", value: "2.6x", sub: "+0.1x vs last quarter" },
      { label: "Hours Automated", value: "1,420", sub: "Across all departments" },
      { label: "LLM Cost Share", value: "52%", sub: "Of total AI spend" },
    ],
    kpis: [
      { name: "Cost vs Productivity Gain", value: "2.6x", trend: "up", delta: "+0.1x", status: "good" },
      { name: "Automation Savings", value: "1,420 hrs", trend: "up", status: "good" },
      { name: "Cost Trend (Monthly)", value: "+4.1%", trend: "up", status: "warn" },
      { name: "Single Model Dependency %", value: "38%", trend: "down", delta: "-5%", status: "warn" },
    ],
    charts: [
      {
        title: "ROI Ratio",
        subtitle: "Quarterly trend",
        type: "area",
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
    description: "Adoption depth of governance capabilities — guardrails, RAG, and HITL — as signals of enterprise AI maturity.",
    summaryStats: [
      { label: "Maturity Level", value: "Level 3", sub: "Out of 5 — Defined" },
      { label: "Guardrail Coverage", value: "88%", sub: "+5% vs last quarter" },
      { label: "Full-Stack Agents", value: "37%", sub: "RAG + HITL + Guardrails" },
    ],
    kpis: [
      { name: "% Agents with Guardrails", value: "88%", trend: "up", delta: "+5%", status: "good" },
      { name: "% Agents with RAG", value: "64%", trend: "up", delta: "+8%", status: "good" },
      { name: "% Agents with HITL", value: "41%", trend: "up", delta: "+4%", status: "neutral" },
    ],
    charts: [],
  },
  {
    id: "risk",
    label: " Enterprise Risk Indicators",
    headline: "Enterprise Risk Indicators",
    description: "High-risk autonomous agents, guardrail bypass attempts, data leakage incidents, and audit readiness posture.",
    summaryStats: [
      { label: "Risk Posture", value: "Moderate", sub: "2 open high-risk items" },
      { label: "Audit Readiness", value: "92%", sub: "Above 90% target" },
      { label: "Open Incidents", value: "2", sub: "Data leakage — under review" },
    ],
    kpis: [
      { name: "High-Risk Autonomous Agents", value: "6", trend: "down", delta: "-2", status: "warn" },
      { name: "Guardrail Bypass Attempts", value: "14", trend: "up", delta: "+3", status: "bad" },
      { name: "Data Leakage Incidents", value: "2", trend: "neutral", status: "bad" },
      { name: "Audit Readiness Score", value: "92%", trend: "up", delta: "+3%", status: "good" },
    ],
    charts: [
      {
        title: "Risk Events",
        subtitle: "Monthly trend",
        type: "area",
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
  "from-sky-50 via-white to-white ring-sky-200/60 dark:from-card dark:via-card dark:to-card dark:ring-border",
  "from-emerald-50 via-white to-white ring-emerald-200/60 dark:from-card dark:via-card dark:to-card dark:ring-border",
  "from-amber-50 via-white to-white ring-amber-200/60 dark:from-card dark:via-card dark:to-card dark:ring-border",
  "from-violet-50 via-white to-white ring-violet-200/60 dark:from-card dark:via-card dark:to-card dark:ring-border",
];

const kpiAccentColors = ["#0ea5e9", "#10b981", "#f59e0b", "#8b5cf6"];

const sectionThemes: Record<SectionId, { glow: string; badge: string; accent: string }> = {
  platform: { glow: "from-sky-500/25 via-indigo-500/15 to-transparent", badge: "bg-sky-100 text-sky-700", accent: "#0ea5e9" },
  governance: { glow: "from-emerald-500/25 via-cyan-500/15 to-transparent", badge: "bg-emerald-100 text-emerald-700", accent: "#10b981" },
  cost: { glow: "from-amber-500/25 via-orange-500/15 to-transparent", badge: "bg-amber-100 text-amber-700", accent: "#f59e0b" },
  lifecycle: { glow: "from-violet-500/25 via-fuchsia-500/15 to-transparent", badge: "bg-violet-100 text-violet-700", accent: "#8b5cf6" },
  usage: { glow: "from-sky-500/20 via-blue-500/15 to-transparent", badge: "bg-sky-100 text-sky-700", accent: "#0ea5e9" },
  approval: { glow: "from-amber-500/20 via-orange-500/15 to-transparent", badge: "bg-amber-100 text-amber-700", accent: "#f59e0b" },
  hitl: { glow: "from-emerald-500/20 via-teal-500/15 to-transparent", badge: "bg-emerald-100 text-emerald-700", accent: "#10b981" },
  rag: { glow: "from-violet-500/20 via-fuchsia-500/15 to-transparent", badge: "bg-violet-100 text-violet-700", accent: "#8b5cf6" },
  quality: { glow: "from-sky-500/20 via-blue-500/15 to-transparent", badge: "bg-sky-100 text-sky-700", accent: "#0ea5e9" },
  performance: { glow: "from-emerald-500/20 via-teal-500/15 to-transparent", badge: "bg-emerald-100 text-emerald-700", accent: "#10b981" },
  code: { glow: "from-amber-500/20 via-orange-500/15 to-transparent", badge: "bg-amber-100 text-amber-700", accent: "#f59e0b" },
  productivity: { glow: "from-sky-500/20 via-blue-500/15 to-transparent", badge: "bg-sky-100 text-sky-700", accent: "#0ea5e9" },
  experience: { glow: "from-emerald-500/20 via-teal-500/15 to-transparent", badge: "bg-emerald-100 text-emerald-700", accent: "#10b981" },
  roi: { glow: "from-sky-500/20 via-blue-500/15 to-transparent", badge: "bg-sky-100 text-sky-700", accent: "#0ea5e9" },
  maturity: { glow: "from-emerald-500/20 via-teal-500/15 to-transparent", badge: "bg-emerald-100 text-emerald-700", accent: "#10b981" },
  risk: { glow: "from-amber-500/20 via-orange-500/15 to-transparent", badge: "bg-amber-100 text-amber-700", accent: "#f59e0b" },
};

const statusStyles: Record<string, { dot: string; text: string; bg: string }> = {
  good: { dot: "bg-emerald-400", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-900/20" },
  warn: { dot: "bg-amber-400", text: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-900/20" },
  bad: { dot: "bg-red-400", text: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-900/20" },
  neutral: { dot: "bg-slate-400", text: "text-muted-foreground", bg: "" },
};

function TrendBadge({ trend, delta }: { trend?: "up" | "down" | "neutral"; delta?: string }) {
  if (!trend || trend === "neutral" || !delta) return null;
  const isUp = trend === "up";
  return (
    <span className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${isUp ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"}`}>
      {isUp ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
      {delta}
    </span>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number; name?: string; dataKey?: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow">
      <p className="font-semibold text-foreground">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey ?? entry.name ?? entry.value} className="text-muted-foreground">
          {(entry.name ?? entry.dataKey ?? "value")}: {entry.value}
        </p>
      ))}
    </div>
  );
}

function DonutTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow">
      <p className="font-semibold text-foreground">{payload[0].name}</p>
      <p className="text-muted-foreground">{payload[0].value}</p>
    </div>
  );
}

function ChartBlock({ chart, accentColor }: { chart: SectionChart; accentColor?: string }) {
  const color = accentColor ?? "#2563eb";

  if (chart.type === "area") {
    const xKey = chart.xKey ?? "label";
    const xType = chart.xType ?? "category";
    return (
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chart.data} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id={`areaGrad-${chart.title}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.18} />
                <stop offset="95%" stopColor={color} stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey={xKey}
              type={xType}
              domain={xType === "number" ? ["dataMin", "dataMax"] : undefined}
              tickFormatter={xType === "number" ? chart.xTickFormatter : undefined}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
            <Tooltip content={<ChartTooltip />} labelFormatter={xType === "number" && chart.xTickFormatter ? chart.xTickFormatter : undefined} />
            <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={`url(#areaGrad-${chart.title})`} dot={false} connectNulls />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.type === "line") {
    const xKey = chart.xKey ?? "label";
    const xType = chart.xType ?? "category";
    return (
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <ReLineChart data={chart.data} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey={xKey}
              type={xType}
              domain={xType === "number" ? ["dataMin", "dataMax"] : undefined}
              tickFormatter={xType === "number" ? chart.xTickFormatter : undefined}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
            <Tooltip content={<ChartTooltip />} labelFormatter={xType === "number" && chart.xTickFormatter ? chart.xTickFormatter : undefined} />
            {chart.lines?.length ? (
              chart.lines.map((line) => (
                <Line key={line.key} type="monotone" dataKey={line.key} stroke={line.color} strokeWidth={2} dot={false} connectNulls />
              ))
            ) : (
              <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} connectNulls />
            )}
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
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
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
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: chartColors[index % chartColors.length] }} />
            <span className="text-muted-foreground">{slice.label}</span>
            <span className="font-semibold">{slice.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Section insight panel — fills space when KPIs/charts are few
function SectionInsightPanel({ section, theme }: { section: SectionConfig; theme: { accent: string; badge: string } }) {
  if (!section.summaryStats?.length && !section.description) return null;
  return (
    <div className="mt-5 rounded-2xl border border-border bg-card/60 p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
        {section.description && (
          <div className="flex-1">
            <p className="text-sm font-medium text-muted-foreground leading-relaxed">{section.description}</p>
          </div>
        )}
        {section.summaryStats && section.summaryStats.length > 0 && (
          <div className="flex flex-wrap gap-4 lg:flex-nowrap lg:shrink-0">
            {section.summaryStats.map((stat, i) => (
              <div key={stat.label} className="flex items-start gap-3 rounded-xl border border-border bg-background px-4 py-3 min-w-[140px]">
                <div className="mt-0.5 h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: theme.accent }} />
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{stat.label}</p>
                  <p className="mt-0.5 text-base font-bold text-foreground">{stat.value}</p>
                  {stat.sub && <p className="text-[10px] text-muted-foreground mt-0.5">{stat.sub}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Activity feed placeholder for sparse sections
function ActivityFeedPlaceholder({ sectionId, theme }: { sectionId: SectionId; theme: { accent: string } }) {
  const feeds: Partial<Record<SectionId, { icon: React.ReactNode; text: string; time: string; type: "info" | "warn" | "good" }[]>> = {
    governance: [
      { icon: <ShieldCheck className="h-3.5 w-3.5" />, text: "Policy enforcement active on 88% of agents", time: "Just now", type: "good" },
      { icon: <AlertTriangle className="h-3.5 w-3.5" />, text: "3 new policy breach attempts detected", time: "12 min ago", type: "warn" },
      { icon: <CheckCircle2 className="h-3.5 w-3.5" />, text: "Guardrail sweep completed — 0 critical gaps", time: "1h ago", type: "good" },
      { icon: <ArrowUpRight className="h-3.5 w-3.5" />, text: "96 escalations queued for human review", time: "2h ago", type: "info" },
    ],
    lifecycle: [
      { icon: <GitBranch className="h-3.5 w-3.5" />, text: "7 agents promoted from UAT to production", time: "30 min ago", type: "good" },
      { icon: <Layers className="h-3.5 w-3.5" />, text: "UAT environment refresh completed", time: "2h ago", type: "info" },
      { icon: <Bot className="h-3.5 w-3.5" />, text: "4 deprecated agents scheduled for cleanup", time: "Yesterday", type: "warn" },
      { icon: <CheckCircle2 className="h-3.5 w-3.5" />, text: "CI/CD gates passing — no pipeline failures", time: "Yesterday", type: "good" },
    ],
    quality: [
      { icon: <CheckCircle2 className="h-3.5 w-3.5" />, text: "Hallucination score improved to 2.1% this week", time: "1h ago", type: "good" },
      { icon: <Zap className="h-3.5 w-3.5" />, text: "Langfuse eval run completed — 100% agent coverage", time: "2h ago", type: "good" },
      { icon: <AlertTriangle className="h-3.5 w-3.5" />, text: "1 agent flagged for low tool call accuracy (89%)", time: "4h ago", type: "warn" },
      { icon: <ArrowUpRight className="h-3.5 w-3.5" />, text: "RAG relevance up 0.03 vs baseline", time: "6h ago", type: "info" },
    ],
    code: [
      { icon: <GitBranch className="h-3.5 w-3.5" />, text: "Agent v2.4.1 successfully deployed to prod", time: "45 min ago", type: "good" },
      { icon: <AlertTriangle className="h-3.5 w-3.5" />, text: "3 agents on outdated runtime version", time: "3h ago", type: "warn" },
      { icon: <CheckCircle2 className="h-3.5 w-3.5" />, text: "Rollback for agent-sales-v2.1 completed", time: "Yesterday", type: "good" },
      { icon: <Layers className="h-3.5 w-3.5" />, text: "7 agents awaiting deprecation sign-off", time: "2 days ago", type: "info" },
    ],
    productivity: [
      { icon: <TrendingUp className="h-3.5 w-3.5" />, text: "2.6x ROI ratio maintained for 3rd consecutive quarter", time: "Today", type: "good" },
      { icon: <CheckCircle2 className="h-3.5 w-3.5" />, text: "1,420 hours automated this billing cycle", time: "Today", type: "good" },
      { icon: <Zap className="h-3.5 w-3.5" />, text: "Ops department leads automation at 420hrs saved", time: "This week", type: "info" },
      { icon: <ArrowUpRight className="h-3.5 w-3.5" />, text: "New workflow automation deployed for sales team", time: "Yesterday", type: "good" },
    ],
    maturity: [
      { icon: <ShieldCheck className="h-3.5 w-3.5" />, text: "Guardrail coverage up 5% — now at 88%", time: "This week", type: "good" },
      { icon: <Database className="h-3.5 w-3.5" />, text: "RAG adoption reached 64% across all agents", time: "This week", type: "good" },
      { icon: <Users className="h-3.5 w-3.5" />, text: "HITL integration growing — now at 41%", time: "This month", type: "info" },
      { icon: <ArrowUpRight className="h-3.5 w-3.5" />, text: "AI Maturity score advanced to Level 3 — Defined", time: "This quarter", type: "good" },
    ],
  };

  const items = feeds[sectionId];
  if (!items) return null;

  const typeColors: Record<string, { dot: string; bg: string }> = {
    good: { dot: "bg-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-900/20" },
    warn: { dot: "bg-amber-400", bg: "bg-amber-50 dark:bg-amber-900/20" },
    info: { dot: "bg-sky-400", bg: "bg-sky-50 dark:bg-sky-900/20" },
  };

  return (
    <div className="mt-5 rounded-2xl border border-border bg-card/60 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Activity className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Recent Activity</h3>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {items.map((item, i) => (
          <div key={i} className={`flex items-start gap-3 rounded-xl ${typeColors[item.type].bg} px-3.5 py-2.5`}>
            <span className={`mt-0.5 ${typeColors[item.type].dot === "bg-emerald-400" ? "text-emerald-600" : typeColors[item.type].dot === "bg-amber-400" ? "text-amber-600" : "text-sky-600"}`}>
              {item.icon}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-foreground leading-snug">{item.text}</p>
              <p className="mt-0.5 text-[10px] text-muted-foreground flex items-center gap-1">
                <Clock className="h-2.5 w-2.5" />{item.time}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Maturity progress bars for maturity section
function MaturityProgressBars({ kpis, accent }: { kpis: SectionKpi[]; accent: string }) {
  if (!kpis.length) return null;
  return (
    <div className="mt-5 rounded-2xl border border-border bg-card/60 p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Adoption Depth</h3>
      <div className="space-y-5">
        {kpis.map((kpi) => {
          const numericMatch = kpi.value.match(/(\d+)/);
          const pct = numericMatch ? parseInt(numericMatch[1]) : 0;
          return (
            <div key={kpi.name}>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{kpi.name}</span>
                <span className="text-sm font-bold text-foreground">{kpi.value}</span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-2.5 rounded-full transition-all duration-700"
                  style={{ width: `${pct}%`, backgroundColor: accent }}
                />
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
                <span>0%</span>
                <span>Target: 100%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DashboardAdmin(): JSX.Element {
  const { t } = useTranslation();
  const { role, userData } = useContext(AuthContext);
  const normalizedRole = (role ?? "").toLowerCase().trim().replace(/\s+/g, "_");
  const isDepartmentAdmin = normalizedRole === "department_admin";
  const isDeveloper = normalizedRole === "developer";
  const isBusinessUser = normalizedRole === "business_user";
  const isRootAdmin = normalizedRole === "root";
  const isSuperAdmin = normalizedRole === "super_admin";
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
  const [lifecycleKpis, setLifecycleKpis] = useState<SectionKpi[] | null>(null);
  const [governanceKpis, setGovernanceKpis] = useState<SectionKpi[] | null>(null);
  const [deptUsageKpis, setDeptUsageKpis] = useState<SectionKpi[] | null>(null);
  const [deptApprovalKpis, setDeptApprovalKpis] = useState<SectionKpi[] | null>(null);
  const [deptResponseTimeSeries, setDeptResponseTimeSeries] = useState<PendingSeriesPoint[] | null>(null);
  const [approvalRange, setApprovalRange] = useState<"7d" | "30d" | "12w">("7d");
  const [approvalPendingSeries, setApprovalPendingSeries] = useState<PendingSeriesPoint[] | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [deptHitlKpis, setDeptHitlKpis] = useState<SectionKpi[] | null>(null);
  const [hitlRange, setHitlRange] = useState<"7d" | "30d" | "12w">("7d");
  const [hitlInvocationSeries, setHitlInvocationSeries] = useState<PendingSeriesPoint[] | null>(null);
  const [hitlResponseSeries, setHitlResponseSeries] = useState<PendingSeriesPoint[] | null>(null);
  const [devCodeKpis, setDevCodeKpis] = useState<SectionKpi[] | null>(null);
  const [businessMaturityKpis, setBusinessMaturityKpis] = useState<SectionKpi[] | null>(null);
  const [rootMaturityKpis, setRootMaturityKpis] = useState<SectionKpi[] | null>(null);
  const [platformKpis, setPlatformKpis] = useState<SectionKpi[] | null>(null);
  const [platformLatencySeries, setPlatformLatencySeries] = useState<Array<{ label: string; ts: number; p95?: number; p99?: number }> | null>(null);
  const [platformErrorSeries, setPlatformErrorSeries] = useState<Array<{ label: string; ts: number; value?: number }> | null>(null);
  const [platformCpuMemSeries, setPlatformCpuMemSeries] = useState<Array<{ label: string; ts: number; cpu?: number; memory?: number }> | null>(null);
  const [devPerformanceKpis, setDevPerformanceKpis] = useState<SectionKpi[] | null>(null);
  const [devLatencySeries, setDevLatencySeries] = useState<Array<{ label: string; p95?: number; p99?: number }> | null>(null);
  const [businessExperienceKpis, setBusinessExperienceKpis] = useState<SectionKpi[] | null>(null);
  const [businessResponseTimeSeries, setBusinessResponseTimeSeries] = useState<PendingSeriesPoint[] | null>(null);

  const lifecycleKpiFallback: SectionKpi[] = [
    { name: "Agents in UAT", value: "--" },
    { name: "UAT to PROD Conversion Rate", value: "--" },
    { name: "Deprecated Agent Count", value: "--" },
  ];
  const governanceKpiFallback: SectionKpi[] = [
    { name: "Escalation to Human Review", value: "--" },
    { name: "% Agents Without Guardrails", value: "--" },
  ];
  const deptUsageKpiFallback: SectionKpi[] = [
    { name: "Active Agents in Dept (UAT)", value: "--" },
    { name: "Active Agents in Dept (PROD)", value: "--" },
    { name: "Avg Response Time", value: "--" },
  ];
  const deptApprovalKpiFallback: SectionKpi[] = [
    { name: "Pending Approvals", value: "--" },
    { name: "Rejection Rate", value: "--" },
    { name: "Avg Approval Time", value: "--" },
  ];
  const deptHitlKpiFallback: SectionKpi[] = [
    { name: "HITL Invocation Rate", value: "--" },
    { name: "Avg HITL Response Time", value: "--" },
  ];
  const devCodeKpiFallback: SectionKpi[] = [{ name: "Avg. Version Count of Agents", value: "--" }];
  const businessMaturityFallback: SectionKpi[] = [
    { name: "% Agents with Guardrails", value: "--" },
    { name: "% Agents with RAG", value: "--" },
    { name: "% Agents with HITL", value: "--" },
  ];
  const rootMaturityFallback: SectionKpi[] = [
    { name: "% Agents with Guardrails", value: "--" },
    { name: "% Agents with RAG", value: "--" },
    { name: "% Agents with HITL", value: "--" },
  ];
  const platformKpiFallback: SectionKpi[] = [
    { name: "Platform Uptime %", value: "--" },
    { name: "API Latency P95", value: "--" },
    { name: "API Latency P99", value: "--" },
    { name: "Error Rate %", value: "--" },
    { name: "AKS Pod Scaling Events", value: "--" },
    { name: "CPU/Memory Saturation %", value: "--" },
  ];
  const devPerformanceFallback: SectionKpi[] = [
    { name: "Avg Agent Latency", value: "--" },
    { name: "Latency P95", value: "--" },
    { name: "Latency P99", value: "--" },
  ];
  const businessExperienceFallback: SectionKpi[] = [
    { name: "Avg Response Time", value: "--" },
    { name: "Escalation to Human", value: "--" },
    { name: "User Satisfaction Score", value: "--" },
  ];
  const approvalRangeOptions = [
    { value: "7d", label: "Last 7 days" },
    { value: "30d", label: "Last 30 days" },
    { value: "12w", label: "Last 12 weeks" },
  ];

  useEffect(() => {
    const id = setInterval(() => setRefreshTick((tick) => tick + 1), 60 * 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => { setSectionId(defaultSectionId); }, [defaultSectionId]);

  // ---- All existing useEffect API calls preserved exactly ----
  useEffect(() => {
    if (!isSuperAdmin) return;
    const orgId = userData?.organization_id || null;
    const params = orgId ? { params: { org_id: orgId } } : undefined;
    api.get<DashboardSectionApiResponse>("/api/dashboard/sections/environment-lifecycle", params)
      .then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? lifecycleKpiFallback; setLifecycleKpis(next); })
      .catch(() => { setLifecycleKpis(lifecycleKpiFallback); });
  }, [isSuperAdmin, refreshTick, userData?.organization_id]);

  useEffect(() => {
    if (!isSuperAdmin) return;
    const getValue = (payload: any) => { const result = payload?.data?.result; const value = Array.isArray(result) && result.length > 0 ? result[0]?.value?.[1] : null; const parsed = value != null ? Number(value) : null; return Number.isFinite(parsed) ? parsed : null; };
    const getSeriesValues = (seriesPayload: any, label: string) => { const series = seriesPayload?.series ?? []; const entry = series.find((s: any) => s?.label === label); const values = entry?.prometheus?.data?.result?.[0]?.values ?? []; return values.map((v: any) => Number(v?.[1] ?? 0)).filter((v: any) => Number.isFinite(v)); };
    const now = Math.floor(Date.now() / 1000); const start = now - 24 * 60 * 60;
    Promise.all([api.get(`/api/metrics-dashboard/query-preset/platform_uptime`), api.get(`/api/metrics-dashboard/query-preset/api_latency_p95`), api.get(`/api/metrics-dashboard/query-preset/api_latency_p99`), api.get(`/api/metrics-dashboard/query-preset/error_rate`), api.get(`/api/metrics-dashboard/query-preset/cpu_saturation`), api.get(`/api/metrics-dashboard/query-preset/memory_saturation`), api.get(`/api/metrics-dashboard/query-preset-range/pod_scaling_activity`, { params: { start, end: now, step: "3600s" } })])
      .then(([uptime, p95, p99, errorRate, cpu, mem, scaling]) => {
        const uptimeVal = getValue(uptime?.data?.prometheus); const p95Val = getValue(p95?.data?.prometheus); const p99Val = getValue(p99?.data?.prometheus); const errorVal = getValue(errorRate?.data?.prometheus); const cpuVal = getValue(cpu?.data?.prometheus); const memVal = getValue(mem?.data?.prometheus);
        const desiredValues = getSeriesValues(scaling?.data, "Desired Replicas (HPA)"); let scalingEvents = 0; if (desiredValues.length > 1) { for (let i = 1; i < desiredValues.length; i += 1) { if (desiredValues[i] !== desiredValues[i - 1]) scalingEvents += 1; } }
        const cpuMem = cpuVal != null && memVal != null ? `${Math.round(cpuVal)}% / ${Math.round(memVal)}%` : "--";
        setPlatformKpis([{ name: "Platform Uptime %", value: uptimeVal != null ? `${uptimeVal.toFixed(2)}%` : "--" }, { name: "API Latency P95", value: p95Val != null ? `${Math.round(p95Val)}ms` : "--" }, { name: "API Latency P99", value: p99Val != null ? `${Math.round(p99Val)}ms` : "--" }, { name: "Error Rate %", value: errorVal != null ? `${errorVal.toFixed(2)}%` : "--" }, { name: "AKS Pod Scaling Events", value: `${scalingEvents}` }, { name: "CPU/Memory Saturation %", value: cpuMem }]);
      }).catch(() => { setPlatformKpis(platformKpiFallback); });
  }, [isSuperAdmin, refreshTick]);

  useEffect(() => {
    if (!isSuperAdmin) return;
    const now = Math.floor(Date.now() / 1000); const start = now - 24 * 60 * 60;
    const formatLabel = (ts: number) => new Date(ts * 1000).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    Promise.all([api.get(`/api/metrics-dashboard/query-preset-range/api_latency_comparison`, { params: { start, end: now, step: "60s" } }), api.get(`/api/metrics-dashboard/query-preset-range/error_rate_trend`, { params: { start, end: now, step: "120s" } }), api.get(`/api/metrics-dashboard/query-preset-range/cpu_memory_saturation`, { params: { start, end: now, step: "120s" } })])
      .then(([latency, errorRate, cpuMem]) => {
        const latencySeries = latency?.data?.series ?? []; const latencyMerged: Record<number, { label: string; ts: number; p95?: number; p99?: number }> = {};
        for (const s of latencySeries) { const lineKey = s?.label === "P95" ? "p95" : s?.label === "P99" ? "p99" : null; if (!lineKey) continue; const values = s?.prometheus?.data?.result?.[0]?.values ?? []; for (const v of values) { const ts = Number(v?.[0] ?? 0); const val = Number(v?.[1] ?? 0); if (!Number.isFinite(ts)) continue; if (!latencyMerged[ts]) latencyMerged[ts] = { label: formatLabel(ts), ts }; if (Number.isFinite(val)) latencyMerged[ts][lineKey] = val; } }
        const latencySorted = Object.entries(latencyMerged).sort(([a], [b]) => Number(a) - Number(b)).map(([, point]) => point);
        setPlatformLatencySeries(latencySorted);
        const errorSeries = errorRate?.data?.series ?? []; const errorTarget = errorSeries.find((s: any) => s?.label === "Error Rate") ?? errorSeries[0]; const errorValues = errorTarget?.prometheus?.data?.result?.[0]?.values ?? [];
        const errorPoints = errorValues.map((v: any) => { const ts = Number(v?.[0] ?? 0); const val = Number(v?.[1] ?? 0); if (!Number.isFinite(ts) || !Number.isFinite(val)) return null; return { label: formatLabel(ts), ts, value: val }; }).filter(Boolean) as Array<{ label: string; ts: number; value?: number }>;
        setPlatformErrorSeries(errorPoints);
        const cpuMemSeries = cpuMem?.data?.series ?? []; const cpuMemMerged: Record<number, { label: string; ts: number; cpu?: number; memory?: number }> = {};
        for (const s of cpuMemSeries) { const lineKey = s?.label === "CPU %" ? "cpu" : s?.label === "Memory %" ? "memory" : null; if (!lineKey) continue; const values = s?.prometheus?.data?.result?.[0]?.values ?? []; for (const v of values) { const ts = Number(v?.[0] ?? 0); const val = Number(v?.[1] ?? 0); if (!Number.isFinite(ts)) continue; if (!cpuMemMerged[ts]) cpuMemMerged[ts] = { label: formatLabel(ts), ts }; if (Number.isFinite(val)) cpuMemMerged[ts][lineKey] = val; } }
        const cpuMemSorted = Object.entries(cpuMemMerged).sort(([a], [b]) => Number(a) - Number(b)).map(([, point]) => point);
        setPlatformCpuMemSeries(cpuMemSorted);
      }).catch(() => { setPlatformLatencySeries([]); setPlatformErrorSeries([]); setPlatformCpuMemSeries([]); });
  }, [isSuperAdmin, refreshTick]);

  useEffect(() => { if (!isDepartmentAdmin) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/department-usage").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? deptUsageKpiFallback; setDeptUsageKpis(next); }).catch(() => { setDeptUsageKpis(deptUsageKpiFallback); }); }, [isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; api.get(`/api/metrics-dashboard/query-preset/avg_response_time`).then((response) => { const result = response?.data?.prometheus?.data?.result; const value = Array.isArray(result) && result.length > 0 ? result[0]?.value?.[1] : null; const parsed = value != null ? Number(value) : null; if (Number.isFinite(parsed)) { setDeptUsageKpis((prev) => { const next = prev ? [...prev] : [...deptUsageKpiFallback]; const index = next.findIndex((kpi) => kpi.name === "Avg Response Time"); const display = `${Math.round(parsed)}ms`; if (index >= 0) { next[index] = { ...next[index], value: display }; } else { next.push({ name: "Avg Response Time", value: display }); } return next; }); } }).catch(() => { setDeptUsageKpis((prev) => prev ?? deptUsageKpiFallback); }); }, [isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; const now = Math.floor(Date.now() / 1000); const start = now - 7 * 24 * 60 * 60; api.get(`/api/metrics-dashboard/query-preset-range/response_time_trend`, { params: { start, end: now, step: "3600s" } }).then((response) => { const series = response?.data?.series ?? []; const values = series?.[0]?.prometheus?.data?.result?.[0]?.values ?? []; const normalized = values.map((v: any) => { const ts = Number(v?.[0] ?? 0); const val = Number(v?.[1] ?? 0); const date = new Date(ts * 1000).toISOString().slice(0, 10); return { date, value: Number.isFinite(val) ? val : 0 }; }); setDeptResponseTimeSeries(normalized); }).catch(() => { setDeptResponseTimeSeries([]); }); }, [isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/department-approval").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? deptApprovalKpiFallback; setDeptApprovalKpis(next); }).catch(() => { setDeptApprovalKpis(deptApprovalKpiFallback); }); }, [isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/department-hitl").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? deptHitlKpiFallback; setDeptHitlKpis(next); }).catch(() => { setDeptHitlKpis(deptHitlKpiFallback); }); }, [isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDeveloper) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/developer-code").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? devCodeKpiFallback; setDevCodeKpis(next); }).catch(() => { setDevCodeKpis(devCodeKpiFallback); }); }, [isDeveloper, refreshTick]);
  useEffect(() => {
    if (!isDeveloper) return;
    Promise.all([api.get(`/api/metrics-dashboard/query-preset/avg_agent_latency`), api.get(`/api/metrics-dashboard/query-preset/api_latency_p95`), api.get(`/api/metrics-dashboard/query-preset/api_latency_p99`)])
      .then(([avgLatency, p95, p99]) => { const getValue = (payload: any) => { const result = payload?.data?.result; const value = Array.isArray(result) && result.length > 0 ? result[0]?.value?.[1] : null; const parsed = value != null ? Number(value) : null; return Number.isFinite(parsed) ? parsed : null; }; const avgVal = getValue(avgLatency?.data?.prometheus); const p95Val = getValue(p95?.data?.prometheus); const p99Val = getValue(p99?.data?.prometheus); setDevPerformanceKpis([{ name: "Avg Agent Latency", value: avgVal != null ? `${Math.round(avgVal)}ms` : "--" }, { name: "Latency P95", value: p95Val != null ? `${Math.round(p95Val)}ms` : "--" }, { name: "Latency P99", value: p99Val != null ? `${Math.round(p99Val)}ms` : "--" }]); })
      .catch(() => { setDevPerformanceKpis(devPerformanceFallback); });
  }, [isDeveloper, refreshTick]);
  useEffect(() => {
    if (!isDeveloper) return;
    const now = Math.floor(Date.now() / 1000); const start = now - 24 * 60 * 60;
    api.get(`/api/metrics-dashboard/query-preset-range/api_latency_comparison`, { params: { start, end: now, step: "60s" } })
      .then((response) => { const series = response?.data?.series ?? []; const merged: Record<number, { label: string; ts: number; p95?: number; p99?: number }> = {}; for (const s of series) { const values = s?.prometheus?.data?.result?.[0]?.values ?? []; const lineKey = s?.label === "P95" ? "p95" : s?.label === "P99" ? "p99" : null; if (!lineKey) continue; for (const v of values) { const ts = Number(v?.[0] ?? 0); const val = Number(v?.[1] ?? 0); if (!Number.isFinite(ts)) continue; const date = new Date(ts * 1000); const label = date.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); if (!merged[ts]) merged[ts] = { label, ts }; if (Number.isFinite(val)) { merged[ts][lineKey] = val; } } } const sorted = Object.entries(merged).sort(([a], [b]) => Number(a) - Number(b)).map(([, point]) => point); setDevLatencySeries(sorted); })
      .catch(() => { setDevLatencySeries([]); });
  }, [isDeveloper, refreshTick]);
  useEffect(() => { if (!isBusinessUser) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/business-maturity").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? businessMaturityFallback; setBusinessMaturityKpis(next); }).catch(() => { setBusinessMaturityKpis(businessMaturityFallback); }); }, [isBusinessUser, refreshTick]);
  useEffect(() => { if (!isBusinessUser) return; api.get(`/api/metrics-dashboard/query-preset/avg_response_time`).then((response) => { const result = response?.data?.prometheus?.data?.result; const value = Array.isArray(result) && result.length > 0 ? result[0]?.value?.[1] : null; const parsed = value != null ? Number(value) : null; if (!Number.isFinite(parsed)) { setBusinessExperienceKpis((prev) => prev ?? businessExperienceFallback); return; } const display = `${Math.round(parsed)}ms`; setBusinessExperienceKpis((prev) => { const next = prev ? [...prev] : [...businessExperienceFallback]; const index = next.findIndex((kpi) => kpi.name === "Avg Response Time"); if (index >= 0) { next[index] = { ...next[index], value: display }; } else { next.push({ name: "Avg Response Time", value: display }); } return next; }); }).catch(() => { setBusinessExperienceKpis((prev) => prev ?? businessExperienceFallback); }); }, [isBusinessUser, refreshTick]);
  useEffect(() => { if (!isBusinessUser) return; const now = Math.floor(Date.now() / 1000); const start = now - 7 * 24 * 60 * 60; api.get(`/api/metrics-dashboard/query-preset-range/response_time_trend`, { params: { start, end: now, step: "3600s" } }).then((response) => { const series = response?.data?.series ?? []; const values = series?.[0]?.prometheus?.data?.result?.[0]?.values ?? []; const normalized = values.map((v: any) => { const ts = Number(v?.[0] ?? 0); const val = Number(v?.[1] ?? 0); const date = new Date(ts * 1000).toISOString().slice(0, 10); return { date, value: Number.isFinite(val) ? val : 0 }; }); setBusinessResponseTimeSeries(normalized); }).catch(() => { setBusinessResponseTimeSeries([]); }); }, [isBusinessUser, refreshTick]);
  useEffect(() => { if (!isBusinessUser) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/business-experience").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? []; setBusinessExperienceKpis((prev) => { const merged = new Map((prev ?? businessExperienceFallback).map((kpi) => [kpi.name, kpi.value])); for (const kpi of next) { merged.set(kpi.name, kpi.value); } return Array.from(merged.entries()).map(([name, value]) => ({ name, value })); }); }).catch(() => { setBusinessExperienceKpis((prev) => prev ?? businessExperienceFallback); }); }, [isBusinessUser, refreshTick]);
  useEffect(() => { if (!isRootAdmin) return; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/root-maturity").then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? rootMaturityFallback; setRootMaturityKpis(next); }).catch(() => { setRootMaturityKpis(rootMaturityFallback); }); }, [isRootAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; api.get<PendingSeriesResponse>("/api/dashboard/sections/department-approval/pending-series", { params: { range: approvalRange } }).then((response) => { setApprovalPendingSeries(response.data?.series ?? []); }).catch(() => { setApprovalPendingSeries([]); }); }, [approvalRange, isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; api.get<HitlSeriesResponse>("/api/dashboard/sections/department-hitl/invocation-series", { params: { range: hitlRange } }).then((response) => { setHitlInvocationSeries(response.data?.series ?? []); }).catch(() => { setHitlInvocationSeries([]); }); }, [hitlRange, isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isDepartmentAdmin) return; api.get<HitlSeriesResponse>("/api/dashboard/sections/department-hitl/response-time-series", { params: { range: hitlRange } }).then((response) => { setHitlResponseSeries(response.data?.series ?? []); }).catch(() => { setHitlResponseSeries([]); }); }, [hitlRange, isDepartmentAdmin, refreshTick]);
  useEffect(() => { if (!isSuperAdmin) return; const orgId = userData?.organization_id || null; const params = orgId ? { params: { org_id: orgId } } : undefined; api.get<DashboardSectionApiResponse>("/api/dashboard/sections/governance-guardrail", params).then((response) => { const next = response.data?.kpis?.map((kpi) => ({ name: kpi.label, value: kpi.unit ? `${kpi.value}${kpi.unit}` : `${kpi.value}` })) ?? governanceKpiFallback; setGovernanceKpis(next); }).catch(() => { setGovernanceKpis(governanceKpiFallback); }); }, [isSuperAdmin, refreshTick, userData?.organization_id]);

  const sectionsToRender = isDepartmentAdmin ? departmentSections : isDeveloper ? developerSections : isBusinessUser ? businessSections : isRootAdmin ? rootSections : sections;
  const activeSection = useMemo(() => sectionsToRender.find((section) => section.id === sectionId) ?? sectionsToRender[0], [sectionId, sectionsToRender]);
  const kpisToRender = isSuperAdmin && activeSection.id === "lifecycle" ? lifecycleKpis ?? lifecycleKpiFallback : activeSection.kpis;

  const displayKpis = useMemo(() => {
    let overrides: Map<string, string> | null = null;
    if (isSuperAdmin && activeSection.id === "governance" && governanceKpis?.length) overrides = new Map(governanceKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isDepartmentAdmin && activeSection.id === "usage" && deptUsageKpis?.length) overrides = new Map(deptUsageKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isDepartmentAdmin && activeSection.id === "approval" && deptApprovalKpis?.length) overrides = new Map(deptApprovalKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isDepartmentAdmin && activeSection.id === "hitl" && deptHitlKpis?.length) overrides = new Map(deptHitlKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isDeveloper && activeSection.id === "code" && devCodeKpis?.length) overrides = new Map(devCodeKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isBusinessUser && activeSection.id === "maturity" && businessMaturityKpis?.length) overrides = new Map(businessMaturityKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isRootAdmin && activeSection.id === "maturity" && rootMaturityKpis?.length) overrides = new Map(rootMaturityKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isSuperAdmin && activeSection.id === "platform" && platformKpis?.length) overrides = new Map(platformKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isDeveloper && activeSection.id === "performance" && devPerformanceKpis?.length) overrides = new Map(devPerformanceKpis.map((kpi) => [kpi.name, kpi.value]));
    if (isBusinessUser && activeSection.id === "experience" && businessExperienceKpis?.length) overrides = new Map(businessExperienceKpis.map((kpi) => [kpi.name, kpi.value]));
    if (!overrides) return kpisToRender;
    return kpisToRender.map((kpi) => { const value = overrides.get(kpi.name); return value ? { ...kpi, value } : kpi; });
  }, [activeSection.id, deptApprovalKpis, deptHitlKpis, deptUsageKpis, devCodeKpis, businessMaturityKpis, rootMaturityKpis, platformKpis, devPerformanceKpis, businessExperienceKpis, governanceKpis, isDepartmentAdmin, isDeveloper, isBusinessUser, isRootAdmin, isSuperAdmin, kpisToRender]);

  const approvalPendingChartData = useMemo(() => { const days = approvalRange === "7d" ? 7 : approvalRange === "30d" ? 30 : 84; const fallbackSeries = Array.from({ length: days }, (_, idx) => { const date = new Date(); date.setUTCDate(date.getUTCDate() - (days - 1 - idx)); return { date: date.toISOString().slice(0, 10), value: 0 }; }); const source = approvalPendingSeries && approvalPendingSeries.length > 0 ? approvalPendingSeries : fallbackSeries; return source.map((point) => { const date = new Date(`${point.date}T00:00:00Z`); const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }); return { label, value: point.value }; }); }, [approvalPendingSeries, approvalRange]);
  const hitlInvocationChartData = useMemo(() => { const days = hitlRange === "7d" ? 7 : hitlRange === "30d" ? 30 : 84; const fallbackSeries = Array.from({ length: days }, (_, idx) => { const date = new Date(); date.setUTCDate(date.getUTCDate() - (days - 1 - idx)); return { date: date.toISOString().slice(0, 10), value: 0 }; }); const source = hitlInvocationSeries && hitlInvocationSeries.length > 0 ? hitlInvocationSeries : fallbackSeries; return source.map((point) => { const date = new Date(`${point.date}T00:00:00Z`); const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }); return { label, value: point.value }; }); }, [hitlInvocationSeries, hitlRange]);
  const hitlResponseChartData = useMemo(() => { const days = hitlRange === "7d" ? 7 : hitlRange === "30d" ? 30 : 84; const fallbackSeries = Array.from({ length: days }, (_, idx) => { const date = new Date(); date.setUTCDate(date.getUTCDate() - (days - 1 - idx)); return { date: date.toISOString().slice(0, 10), value: 0 }; }); const source = hitlResponseSeries && hitlResponseSeries.length > 0 ? hitlResponseSeries : fallbackSeries; return source.map((point) => { const date = new Date(`${point.date}T00:00:00Z`); const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }); return { label, value: point.value }; }); }, [hitlResponseSeries, hitlRange]);
  const deptResponseTimeChartData = useMemo(() => { const days = 7; const fallbackSeries = Array.from({ length: days }, (_, idx) => { const date = new Date(); date.setUTCDate(date.getUTCDate() - (days - 1 - idx)); return { date: date.toISOString().slice(0, 10), value: 0 }; }); const source = deptResponseTimeSeries && deptResponseTimeSeries.length > 0 ? deptResponseTimeSeries : fallbackSeries; return source.map((point) => { const date = new Date(`${point.date}T00:00:00Z`); const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }); return { label, value: point.value }; }); }, [deptResponseTimeSeries]);
  const businessResponseTimeChartData = useMemo(() => { const days = 7; const fallbackSeries = Array.from({ length: days }, (_, idx) => { const date = new Date(); date.setUTCDate(date.getUTCDate() - (days - 1 - idx)); return { date: date.toISOString().slice(0, 10), value: 0 }; }); const source = businessResponseTimeSeries && businessResponseTimeSeries.length > 0 ? businessResponseTimeSeries : fallbackSeries; return source.map((point) => { const date = new Date(`${point.date}T00:00:00Z`); const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" }); return { label, value: point.value }; }); }, [businessResponseTimeSeries]);
  const platformLatencyChartData = useMemo(() => { if (platformLatencySeries && platformLatencySeries.length > 0) return platformLatencySeries; return Array.from({ length: 8 }, (_, idx) => { const ts = Math.floor(Date.now() / 1000) - (7 - idx) * 3600; return { label: new Date(ts * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }), ts, p95: 0, p99: 0 }; }); }, [platformLatencySeries]);
  const platformErrorChartData = useMemo(() => { if (platformErrorSeries && platformErrorSeries.length > 0) return platformErrorSeries; return Array.from({ length: 8 }, (_, idx) => { const ts = Math.floor(Date.now() / 1000) - (7 - idx) * 3600; return { label: new Date(ts * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }), ts, value: 0 }; }); }, [platformErrorSeries]);
  const platformCpuMemChartData = useMemo(() => { if (platformCpuMemSeries && platformCpuMemSeries.length > 0) return platformCpuMemSeries; return Array.from({ length: 8 }, (_, idx) => { const ts = Math.floor(Date.now() / 1000) - (7 - idx) * 3600; return { label: new Date(ts * 1000).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }), ts, cpu: 0, memory: 0 }; }); }, [platformCpuMemSeries]);
  const devLatencyChartData = useMemo(() => { if (!devLatencySeries || devLatencySeries.length === 0) return []; return devLatencySeries; }, [devLatencySeries]);

  const chartsToRender = useMemo(() => {
    if (activeSection.id === "maturity" && isRootAdmin) return [];
    if (activeSection.id === "experience" && isBusinessUser) return activeSection.charts.map((chart) => { if (chart.title !== "Response Time") return chart; return { ...chart, data: businessResponseTimeChartData }; });
    if (!isDepartmentAdmin) return activeSection.charts;
    if (activeSection.id === "usage") return activeSection.charts.map((chart) => { if (chart.title !== "Response Time Trend") return chart; return { ...chart, data: deptResponseTimeChartData }; });
    if (activeSection.id === "approval") return activeSection.charts.map((chart) => { if (chart.title !== "Pending Approvals") return chart; return { ...chart, data: approvalPendingChartData ?? [] }; });
    if (activeSection.id === "hitl") return activeSection.charts.map((chart) => { if (chart.title === "Invocation Rate") return { ...chart, data: hitlInvocationChartData ?? [] }; if (chart.title === "Response Time") return { ...chart, data: hitlResponseChartData ?? [] }; return chart; });
    if (activeSection.id === "platform" && isSuperAdmin) return activeSection.charts.map((chart) => { if (chart.title === "API Latency P95 vs P99") return { ...chart, data: platformLatencyChartData }; if (chart.title === "Error Rate Trend") return { ...chart, data: platformErrorChartData }; if (chart.title === "CPU & Memory Saturation") return { ...chart, data: platformCpuMemChartData }; return chart; });
    if (activeSection.id === "performance") return activeSection.charts.map((chart) => { if (chart.title !== "API Latency P95 vs P99") return chart; return { ...chart, data: devLatencyChartData }; });
    return activeSection.charts.map((chart) => chart);
  }, [activeSection.charts, activeSection.id, approvalPendingChartData, businessResponseTimeChartData, deptResponseTimeChartData, devLatencyChartData, hitlInvocationChartData, hitlResponseChartData, isDepartmentAdmin, isBusinessUser, isSuperAdmin, isRootAdmin, platformCpuMemChartData, platformErrorChartData, platformLatencyChartData]);

  const theme = sectionThemes[activeSection.id];
  const isLifecycleSection = activeSection.id === "lifecycle";
  const isMaturitySection = activeSection.id === "maturity";
  const isSparseSection = displayKpis.length <= 3;

  // KPI grid: always at least 4 columns on xl for density, but lifecycle stays 3-col
  const kpiGridClass = isLifecycleSection
    ? "mt-5 grid grid-cols-1 gap-5 md:grid-cols-3"
    : "mt-5 grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4";

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border bg-card">
        <div className="px-8 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-foreground">{t("Dashboard")}</h1>
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${theme.badge}`}>
                {t(activeSection.label)}
              </span>
            </div>
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

      {/* Body */}
      <div className="flex-1 overflow-auto bg-background px-8 py-6">
        <div className="relative">
          <div className="pointer-events-none absolute inset-0 rounded-3xl bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.12),_transparent_55%),radial-gradient(circle_at_80%_20%,_rgba(16,185,129,0.12),_transparent_50%)]" />
          <div className="relative rounded-3xl border border-border bg-card/90 p-6 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">

            {/* Section headline + description strip */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-foreground">{t(activeSection.headline)}</h2>
                {activeSection.description && (
                  <p className="mt-1 text-xs text-muted-foreground max-w-2xl leading-relaxed">{activeSection.description}</p>
                )}
              </div>
              {/* Live pulse indicator */}
              <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                <span className="text-[10px] font-medium text-muted-foreground">Live</span>
              </div>
            </div>

            {/* KPI Cards */}
            {displayKpis.length > 0 && (
              <div className={kpiGridClass}>
                {displayKpis.map((kpi, index) => {
                  const st = statusStyles[(kpi as any).status ?? "neutral"] ?? statusStyles.neutral;
                  const accentColor = kpiAccentColors[index % kpiAccentColors.length];
                  return (
                    <div
                      key={kpi.name}
                      className={`group relative overflow-hidden rounded-2xl border bg-gradient-to-br ${kpiCardStyles[index % kpiCardStyles.length]} ${isLifecycleSection ? "p-6 min-h-[160px]" : "p-4"} ring-1 border-border shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md`}
                    >
                      {/* Top accent bar with color */}
                      <div className="h-1 w-10 rounded-full" style={{ background: `linear-gradient(90deg, ${accentColor}, ${accentColor}60)` }} />

                      {/* Status dot */}
                      <div className="mt-3 flex items-center gap-2">
                        <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium flex-1">{t(kpi.name)}</p>
                      </div>

                      <div className="mt-2 flex items-end justify-between gap-2">
                        <p className={`font-bold text-foreground leading-none ${isLifecycleSection ? "text-3xl" : "text-2xl"}`}>
                          {t(kpi.value)}
                        </p>
                        <TrendBadge trend={(kpi as any).trend} delta={(kpi as any).delta} />
                      </div>

                      {/* Subtle bg decoration */}
                      <div
                        className="pointer-events-none absolute -right-4 -bottom-4 h-16 w-16 rounded-full opacity-[0.07] group-hover:opacity-[0.12] transition-opacity"
                        style={{ backgroundColor: accentColor }}
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {/* Maturity progress bars */}
            {isMaturitySection && displayKpis.length > 0 && (
              <MaturityProgressBars kpis={displayKpis} accent={theme.accent} />
            )}

            {/* Summary insight panel (for sparse sections) */}
            {(isSparseSection || displayKpis.length === 0) && activeSection.summaryStats && (
              <SectionInsightPanel section={activeSection} theme={theme} />
            )}

            {/* Activity feed for sections with no/few charts */}
            {chartsToRender.length === 0 && (
              <ActivityFeedPlaceholder sectionId={activeSection.id} theme={theme} />
            )}

            {/* Charts */}
            {chartsToRender.length > 0 && (
              <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-3">
                {chartsToRender.map((chart, index) => (
                  <div
                    key={chart.placeholder ? `placeholder-${index}` : chart.title}
                    className="rounded-2xl border border-border bg-card/90 p-5 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="text-sm font-semibold text-foreground">{t(chart.title)}</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">{t(chart.subtitle)}</p>
                      </div>
                      {isDepartmentAdmin && activeSection.id === "approval" && chart.title === "Pending Approvals" ? (
                        <Select value={approvalRange} onValueChange={(value) => setApprovalRange(value as "7d" | "30d" | "12w")}>
                          <SelectTrigger className="h-7 w-[140px] text-xs"><SelectValue placeholder="Range" /></SelectTrigger>
                          <SelectContent>{approvalRangeOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
                        </Select>
                      ) : isDepartmentAdmin && activeSection.id === "hitl" && (chart.title === "Invocation Rate" || chart.title === "Response Time") ? (
                        <Select value={hitlRange} onValueChange={(value) => setHitlRange(value as "7d" | "30d" | "12w")}>
                          <SelectTrigger className="h-7 w-[140px] text-xs"><SelectValue placeholder="Range" /></SelectTrigger>
                          <SelectContent>{approvalRangeOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
                        </Select>
                      ) : (
                        <div className="rounded-full bg-slate-100 dark:bg-slate-800 p-2">
                          {chart.type === "line" || chart.type === "area" ? <LineChart className="h-4 w-4 text-slate-500" /> : chart.type === "bar" ? <BarChart3 className="h-4 w-4 text-slate-500" /> : <Activity className="h-4 w-4 text-slate-500" />}
                        </div>
                      )}
                    </div>
                    <div className="mt-4">
                      {chart.placeholder ? (
                        <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-slate-50/50 dark:bg-slate-900/20 text-sm text-muted-foreground">
                          <BarChart3 className="h-8 w-8 opacity-20" />
                          <span className="text-xs">{t("More insights coming soon")}</span>
                        </div>
                      ) : (
                        <ChartBlock chart={chart} accentColor={theme.accent} />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}