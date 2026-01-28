import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

// Dummy data
const tracesOverviewData = [
  { date: "Jan 15", value: 25 },
  { date: "Jan 18", value: 18 },
  { date: "Jan 21", value: 32 },
  { date: "Jan 24", value: 28 },
  { date: "Jan 27", value: 35 },
  { date: "Jan 30", value: 22 },
  { date: "Feb 02", value: 28 },
  { date: "Feb 05", value: 25 },
];

const tracesTimeData = [
  { date: "Jan 15 00:00", value: 2 },
  { date: "Jan 20 00:00", value: 5 },
  { date: "Jan 25 00:00", value: 3 },
  { date: "Jan 30 00:00", value: 7 },
  { date: "Feb 04 00:00", value: 4 },
  { date: "Feb 09 00:00", value: 6 },
];

const modelUsageData = [
  { date: "Jan 15 00:00", value: 180000 },
  { date: "Jan 20 00:00", value: 220000 },
  { date: "Jan 25 00:00", value: 250000 },
  { date: "Jan 30 00:00", value: 280000 },
  { date: "Feb 04 00:00", value: 310000 },
  { date: "Feb 09 00:00", value: 350000 },
];

const userConsumptionData = [
  { user: "user1@example.com", value: 850 },
  { user: "user2@example.com", value: 720 },
  { user: "user3@example.com", value: 650 },
  { user: "user4@example.com", value: 580 },
  { user: "user5@example.com", value: 420 },
];

const scoresData = [
  { date: "Jan 15", score1: 0.85, score2: 0.72, score3: 0.68, score4: 0.90, score5: 0.75 },
  { date: "Jan 20", score1: 0.82, score2: 0.75, score3: 0.70, score4: 0.88, score5: 0.78 },
  { date: "Jan 25", score1: 0.88, score2: 0.78, score3: 0.72, score4: 0.92, score5: 0.80 },
  { date: "Jan 30", score1: 0.86, score2: 0.80, score3: 0.75, score4: 0.90, score5: 0.82 },
  { date: "Feb 04", score1: 0.90, score2: 0.82, score3: 0.78, score4: 0.94, score5: 0.85 },
];

const latencyData = [
  { date: "Jan 15 00:00", value: 145 },
  { date: "Jan 20 00:00", value: 180 },
  { date: "Jan 25 00:00", value: 165 },
  { date: "Jan 30 00:00", value: 195 },
  { date: "Feb 04 00:00", value: 220 },
  { date: "Feb 09 00:00", value: 190 },
];

export default function ObservabilityDashboard() {
  const [timeRange, setTimeRange] = useState("Last 7 days");

  return (
    <div className="flex h-full w-full flex-col overflow-auto bg-gray-50 dark:bg-background">
      {/* Top Bar */}
      <div className="border-b bg-white dark:bg-card px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-40 h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Last 7 days">Last 7 days</SelectItem>
                <SelectItem value="Last 30 days">Last 30 days</SelectItem>
                <SelectItem value="Last 90 days">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
           
          </div>
          <Button size="sm">Report Issue</Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto p-6">
        {/* Top Row - Traces and Stats */}
        <div className="mb-6 grid gap-6 lg:grid-cols-3">
          {/* Traces Card */}
          <div className="lg:col-span-2">
            <div className="rounded-lg border bg-white dark:bg-card p-6">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">Traces</h3>
                  <p className="text-3xl font-bold">32</p>
                  <p className="text-xs text-muted-foreground">Last hour: 6 traces</p>
                </div>
                
              </div>
              <ResponsiveContainer width="100%" height={120}>
                <AreaChart data={tracesOverviewData}>
                  <defs>
                    <linearGradient id="colorTraces" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#93C5FD" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#93C5FD" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="value" stroke="#3B82F6" fillOpacity={1} fill="url(#colorTraces)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="space-y-4">
            <div className="rounded-lg border bg-white dark:bg-card p-6">
              <h3 className="text-sm font-medium text-muted-foreground">Model costs</h3>
              <p className="text-3xl font-bold">$1,298042</p>
              <p className="text-xs text-muted-foreground">Total cost</p>
            </div>
            <div className="rounded-lg border bg-white dark:bg-card p-6">
              <h3 className="text-sm font-medium text-muted-foreground">Scores</h3>
              <p className="text-3xl font-bold">244</p>
              <p className="text-xs text-muted-foreground">Submitted total</p>
            </div>
          </div>
        </div>

        {/* Charts Row 1 */}
        <div className="mb-6 grid gap-6 lg:grid-cols-2">
          {/* Traces by Time */}
          <div className="rounded-lg border bg-white dark:bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold">Traces by time</h3>
                <p className="text-xs text-muted-foreground">32 total models</p>
              </div>
              <Button variant="ghost" size="sm">
                <ChevronDown className="h-4 w-4" />
              </Button>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={tracesTimeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <YAxis tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Model Usage */}
          <div className="rounded-lg border bg-white dark:bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold">Model Usage</h3>
                <p className="text-sm font-bold">$1,298042</p>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm">
                  Costs by model
                </Button>
                <Button variant="ghost" size="sm">
                  Usage by type
                </Button>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={modelUsageData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <YAxis tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Charts Row 2 */}
        <div className="mb-6 grid gap-6 lg:grid-cols-2">
          {/* User Consumption */}
          <div className="rounded-lg border bg-white dark:bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold">User consumption</h3>
                <p className="text-xs text-muted-foreground">$1,298042 total cost</p>
              </div>
              <Button variant="link" size="sm" className="text-xs">
                Show all
              </Button>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={userConsumptionData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <YAxis dataKey="user" type="category" tick={{ fontSize: 10 }} stroke="#9CA3AF" width={160} />
                <Tooltip />
                <Bar dataKey="value" fill="#93C5FD" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Scores */}
          <div className="rounded-lg border bg-white dark:bg-card p-6">
            <div className="mb-4">
              <h3 className="font-semibold">Scores</h3>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={scoresData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <YAxis tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <Tooltip />
                <Line type="monotone" dataKey="score1" stroke="#10B981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="score2" stroke="#3B82F6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="score3" stroke="#F59E0B" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="score4" stroke="#8B5CF6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="score5" stroke="#EF4444" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Latency Percentiles Tables */}
        <div className="mb-6 grid gap-6 lg:grid-cols-3">
          {["Trace latency percentiles", "Generation latency percentiles", "Span latency percentiles"].map((title) => (
            <div key={title} className="rounded-lg border bg-white dark:bg-card">
              <div className="border-b px-4 py-3">
                <h3 className="text-sm font-semibold">{title}</h3>
              </div>
              <div className="p-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Metric</th>
                      <th className="pb-2 text-right text-xs font-medium text-muted-foreground">ms</th>
                    </tr>
                  </thead>
                  <tbody className="text-xs">
                    <tr className="border-b">
                      <td className="py-2">p50</td>
                      <td className="py-2 text-right">145</td>
                    </tr>
                    <tr className="border-b">
                      <td className="py-2">p75</td>
                      <td className="py-2 text-right">280</td>
                    </tr>
                    <tr className="border-b">
                      <td className="py-2">p90</td>
                      <td className="py-2 text-right">450</td>
                    </tr>
                    <tr className="border-b">
                      <td className="py-2">p95</td>
                      <td className="py-2 text-right">620</td>
                    </tr>
                    <tr>
                      <td className="py-2">p99</td>
                      <td className="py-2 text-right">950</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>

        {/* Model Latencies Chart */}
        <div className="mb-6">
          <div className="rounded-lg border bg-white dark:bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold">Model latencies</h3>
              <div className="flex gap-2">
                {["50th Percentile", "75th Percentile", "90th Percentile", "95th Percentile", "99th Percentile"].map((p) => (
                  <Button key={p} variant="ghost" size="sm" className="text-xs h-7">
                    {p}
                  </Button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={latencyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <YAxis tick={{ fontSize: 11 }} stroke="#9CA3AF" />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Scores Analytics */}
        <div className="rounded-lg border bg-white dark:bg-card p-6">
          <h3 className="mb-2 font-semibold">Scores Analytics</h3>
          <p className="text-sm text-muted-foreground">Launch a score to view analytics</p>
        </div>
      </div>
    </div>
  );
}