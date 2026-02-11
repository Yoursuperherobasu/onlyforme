import React, { useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Play, Plus } from "lucide-react";
import {
  getEvaluationAnalytics,
  getEvaluationScores,
  getEvaluationStatus,
  getPendingReviews,
  getAvailableModels,
  runLLMJudge,
  createEvaluationScore,
  createEvaluator,
  getFlows,
  getEvaluationPresets,
  listEvaluators,
  previewEvaluation,
  updateEvaluator,
  deleteEvaluator,
  EvaluationAnalytics,
  EvaluationPreset,
  EvaluationStatus,
  Score,
  TraceForReview,
} from "../../controllers/API/evaluation";
import useAlertStore from "@/stores/alertStore";
import { useModelStore } from "@/stores/modelStore";

const FALLBACK_PRESETS: EvaluationPreset[] = [
  {
    id: "correctness",
    name: "Correctness",
    criteria: "Evaluate the correctness of the generation against the ground truth on a scale 0-1.",
    requires_ground_truth: true,
  },
  {
    id: "helpfulness",
    name: "Helpfulness",
    criteria: "Evaluate how helpful the output is in addressing the user's input on a scale 0-1.",
    requires_ground_truth: false,
  },
];

export default function EvaluationPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [analytics, setAnalytics] = useState<EvaluationAnalytics | null>(null);
  const [status, setStatus] = useState<EvaluationStatus | null>(null);
  const [recentScores, setRecentScores] = useState<Score[]>([]);
  const [pendingTraces, setPendingTraces] = useState<TraceForReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [scoreFilters, setScoreFilters] = useState({ trace_id: "", name: "" });
  const [presets, setPresets] = useState<EvaluationPreset[]>([]);
  const [savedEvaluators, setSavedEvaluators] = useState<Array<any>>([]);
  const [editingEvaluator, setEditingEvaluator] = useState<string | null>(null);
  
  // Dialog States
  const [isJudgeDialogOpen, setIsJudgeDialogOpen] = useState(false);
  const [isScoreDialogOpen, setIsScoreDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [availableModels, setAvailableModels] = useState<any[]>([]);
  const [modelApiKey, setModelApiKey] = useState<string>("");
  const [flowList, setFlowList] = useState<any[]>([]);
  const storeModels = useModelStore((s) => s.models);
  const [savedModelKeys, setSavedModelKeys] = useState<Record<string, string>>({});
  const loadSavedModelKeys = () => {
    try {
      const raw = localStorage.getItem('evaluation_model_keys');
      if (!raw) return {} as Record<string,string>;
      const parsed = JSON.parse(raw || '{}');
      setSavedModelKeys(parsed || {});
      return parsed || {};
    } catch (e) {
      return {} as Record<string,string>;
    }
  };
  const saveModelKey = (modelId: string, key: string) => {
    const next = { ...(savedModelKeys || {}), [modelId]: key };
    setSavedModelKeys(next);
    try { localStorage.setItem('evaluation_model_keys', JSON.stringify(next)); } catch (e) { console.debug(e); }
  };
  
  const [selectedFlowIds, setSelectedFlowIds] = useState<string[]>([]);
  const [filterSessionId, setFilterSessionId] = useState<string>('');
  const [filterTraceId, setFilterTraceId] = useState<string>('');
  const [runOnNew, setRunOnNew] = useState<boolean>(true);
  const [runOnExisting, setRunOnExisting] = useState<boolean>(true);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  // Form Data
  const [judgeForm, setJudgeForm] = useState({ trace_id: "", criteria: "", model: "gpt-4o", name: "", preset_id: "", saved_evaluator_id: "", model_name: "" });
  const [groundTruth, setGroundTruth] = useState("");
  const [scoreForm, setScoreForm] = useState({ trace_id: "", name: "", value: "0.5", comment: "" });
  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === judgeForm.preset_id),
    [presets, judgeForm.preset_id],
  );
  const requiresGroundTruth = Boolean(selectedPreset?.requires_ground_truth);

  const resetForms = () => {
    setJudgeForm({ trace_id: "", criteria: "", model: "gpt-4o", name: "", preset_id: "", saved_evaluator_id: "", model_name: "" });
    setGroundTruth("");
    setSelectedFlowIds([]);
    setFilterSessionId("");
    setFilterTraceId("");
    setRunOnNew(true);
    setRunOnExisting(true);
    setScoreForm({ trace_id: "", name: "", value: "0.5", comment: "" });
  };

  const shortId = (id?: string | null) => (id ? `${id.substring(0, 8)}...` : "-");
  const safePendingTraces = Array.isArray(pendingTraces) ? pendingTraces.filter((trace) => Boolean(trace?.id)) : [];

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  const pollScoresForTrace = async (traceId: string, attempts = 5, delayMs = 2000) => {
    for (let i = 0; i < attempts; i += 1) {
      await sleep(delayMs);
      try {
        const scoresData = await getEvaluationScores({ trace_id: traceId, limit: 5 });
        if (scoresData?.items?.length) {
          await fetchData();
          return true;
        }
      } catch {
        // ignore and continue polling
      }
    }
    return false;
  };

  useEffect(() => {
    fetchData();
    getEvaluationPresets()
      .then((items) => {
        if (Array.isArray(items)) {
          setPresets(items.length ? items : FALLBACK_PRESETS);
        } else {
          setPresets(FALLBACK_PRESETS);
        }
      })
      .catch(() => {
        setPresets(FALLBACK_PRESETS);
      });
    // load saved evaluators (normalize response shapes)
    listEvaluators()
      .then((items) => {
        if (Array.isArray(items)) return setSavedEvaluators(items as any);
        if (items && Array.isArray((items as any).items)) return setSavedEvaluators((items as any).items);
        if (items && Array.isArray((items as any).data)) return setSavedEvaluators((items as any).data);
        return setSavedEvaluators([]);
      })
      .catch(() => {
        setSavedEvaluators([]);
      });
  }, []);

  // Refresh pending traces when opening the Run Judge dialog to ensure dropdown is populated
  useEffect(() => {
    if (!isJudgeDialogOpen) return;
    let mounted = true;
    (async () => {
      try {
        console.debug("Fetching pending reviews for judge dialog");
        const val = await getPendingReviews({ limit: 100 });
        if (!mounted) return;
        if (Array.isArray(val)) {
          setPendingTraces(val);
          console.debug("Pending traces fetched:", val.length);
        } else if (val && Array.isArray((val as any).items)) {
          setPendingTraces((val as any).items);
          console.debug("Pending traces fetched (items):", (val as any).items.length);
        } else if (val && Array.isArray((val as any).data)) {
          setPendingTraces((val as any).data);
          console.debug("Pending traces fetched (data):", (val as any).data.length);
        } else {
          setPendingTraces([]);
        }
        // Load flows (also used as model catalogue). Fetch only once to avoid duplicate requests.
        try {
          const flows = await getFlows();
          const normalized = flows && Array.isArray(flows.data) ? flows.data : Array.isArray(flows) ? flows : [];
          setFlowList(normalized);
          // For availableModels, prefer storeModels fallback; if flows look like models, expose them too
          if (normalized.length > 0) {
            setAvailableModels(normalized);
          } else if (storeModels?.length) {
            setAvailableModels(storeModels);
          } else {
            setAvailableModels([]);
          }
        } catch (e) {
          console.debug("Failed to load flows/models", e);
          setFlowList([]);
          setAvailableModels(storeModels?.length ? storeModels : []);
        }
        // load saved model API keys and prefill if available
        try {
          const keys = loadSavedModelKeys();
          const modelName = (judgeForm.model_name && judgeForm.model_name.trim()) || judgeForm.model;
          if (keys && modelName && keys[modelName]) {
            setModelApiKey(keys[modelName]);
          }
        } catch (e) { /* ignore */ }
      } catch (e) {
        console.error("Failed fetching pending traces:", e);
        setPendingTraces([]);
      }
    })();
    return () => { mounted = false; };
  }, [isJudgeDialogOpen]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [analyticsResult, scoresResult, pendingResult, statusResult] = await Promise.allSettled([
        getEvaluationAnalytics(),
        getEvaluationScores({ limit: 20, ...scoreFilters }),
        getPendingReviews({ limit: 20 }),
        getEvaluationStatus(),
      ]);

      if (analyticsResult.status === "fulfilled") {
        setAnalytics(analyticsResult.value);
      }
      if (scoresResult.status === "fulfilled") {
        setRecentScores(scoresResult.value.items ?? []);
      }
      if (pendingResult.status === "fulfilled") {
        const val = pendingResult.value;
        if (Array.isArray(val)) {
          setPendingTraces(val);
        } else if (val && Array.isArray((val as any).items)) {
          setPendingTraces((val as any).items);
        } else if (val && Array.isArray((val as any).data)) {
          setPendingTraces((val as any).data);
        } else {
          setPendingTraces([]);
        }
      }
      if (statusResult.status === "fulfilled") {
        setStatus(statusResult.value);
      }
    } catch (error) {
      console.error("Failed to fetch evaluation data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRunJudge = async () => {
    // For this UI change we only support creating/running evaluators for 'new' and/or 'existing' traces
    if (!runOnNew && !runOnExisting) {
      setErrorData({ title: 'Select at least one target: New Traces or Existing Traces.' });
      return;
    }
    if (!judgeForm.criteria || judgeForm.criteria.trim() === "") {
      setErrorData({ title: 'Provide evaluation criteria.' });
      return;
    }
    if (requiresGroundTruth && !groundTruth.trim()) {
      setErrorData({ title: 'Ground truth is required for the selected preset.' });
      return;
    }
    setIsSubmitting(true);
    try {
      // If both selected, create evaluator targeting both (backend should accept array or handle 'both')
      const targets: string[] = [];
      if (runOnExisting) targets.push('existing');
      if (runOnNew) targets.push('new');

      const modelName = (judgeForm.model_name && judgeForm.model_name.trim()) || judgeForm.model;
      const payload: any = {
        name: judgeForm.name?.trim() || `LLM Judge - ${new Date().toISOString()}`,
        criteria: judgeForm.criteria || '',
        model: modelName,
        preset_id: judgeForm.preset_id || undefined,
        target: targets.length === 1 ? targets[0] : targets,
      };
      if (groundTruth.trim()) payload.ground_truth = groundTruth.trim();
      if (modelApiKey) {
        payload.model_api_key = modelApiKey;
        // persist locally under the chosen model name
        if (modelName) saveModelKey(modelName, modelApiKey);
      }
      if (selectedFlowIds && selectedFlowIds.length) payload.agent_ids = selectedFlowIds;
      if (filterSessionId) payload.session_id = filterSessionId;
      if (filterTraceId) payload.trace_id = filterTraceId;

      // optional filters are currently not exposed in this simplified dialog
      await createEvaluator(payload);
      setIsJudgeDialogOpen(false);
      resetForms();
      // Refresh saved evaluators list
      try {
        const items = await listEvaluators();
        if (Array.isArray(items)) setSavedEvaluators(items as any);
        else if (items && Array.isArray((items as any).items)) setSavedEvaluators((items as any).items);
        else if (items && Array.isArray((items as any).data)) setSavedEvaluators((items as any).data);
      } catch (e) {
        // ignore
      }
      if (runOnExisting && !runOnNew) {
        setNoticeData({ title: 'Evaluator created and existing traces queued for evaluation.' });
      } else if (runOnNew && !runOnExisting) {
        setSuccessData({ title: 'Evaluator saved and will apply to new traces.' });
      } else {
        setSuccessData({ title: 'Evaluator created for selected targets.' });
      }
    } catch (error) {
      console.error('Failed to run judge', error);
      setErrorData({ title: 'Failed to run LLM Judge' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<{ system_prompt?: string; user_prompt?: string; trace?: any } | null>(null);

  const handlePreview = async () => {
    if (!judgeForm.trace_id || !judgeForm.criteria) {
      setErrorData({ title: "Provide trace ID and criteria to preview" });
      return;
    }
    try {
      const modelName = (judgeForm.model_name && judgeForm.model_name.trim()) || judgeForm.model;
      const data = await previewEvaluation({ trace_id: judgeForm.trace_id, criteria: judgeForm.criteria, model: modelName });
      setPreviewData(data);
      setIsPreviewOpen(true);
    } catch (e) {
      setErrorData({ title: "Preview failed" });
    }
  };

  const handleSaveEvaluator = async () => {
    if (!judgeForm.name || !judgeForm.criteria) {
      setErrorData({ title: "Provide a name and criteria to save evaluator" });
      return;
    }
    if (requiresGroundTruth && !groundTruth.trim()) {
      setErrorData({ title: "Ground truth is required for the selected preset." });
      return;
    }
    try {
      const targets: string[] = [];
      if (runOnExisting) targets.push('existing');
      if (runOnNew) targets.push('new');
      const modelName = (judgeForm.model_name && judgeForm.model_name.trim()) || judgeForm.model;
      const payload: any = {
        name: judgeForm.name,
        criteria: judgeForm.criteria,
        model: modelName,
      };
      if (targets.length === 1) payload.target = targets[0];
      else if (targets.length > 1) payload.target = targets;
      if (judgeForm.preset_id) payload.preset_id = judgeForm.preset_id;
      if (groundTruth.trim()) payload.ground_truth = groundTruth.trim();
      if (selectedFlowIds && selectedFlowIds.length) payload.agent_ids = selectedFlowIds;
      if (filterSessionId) payload.session_id = filterSessionId;
      if (filterTraceId) payload.trace_id = filterTraceId;
      if (modelApiKey && modelName) {
        payload.model_api_key = modelApiKey;
        saveModelKey(modelName, modelApiKey);
      }

      if (editingEvaluator) {
        const updated = await updateEvaluator(editingEvaluator, payload);
        setSavedEvaluators((s) => s.map((it) => (it.id === updated.id ? updated : it)));
        setSuccessData({ title: "Evaluator updated" });
        setEditingEvaluator(null);
      } else {
        const created = await createEvaluator(payload);
          // Refresh saved evaluators from server to ensure list is consistent
          try {
            const items = await listEvaluators();
            if (Array.isArray(items)) setSavedEvaluators(items as any);
            else if (items && Array.isArray((items as any).items)) setSavedEvaluators((items as any).items);
            else if (items && Array.isArray((items as any).data)) setSavedEvaluators((items as any).data);
          } catch (e) {
            // fallback to adding created item
            setSavedEvaluators((s) => [created, ...s]);
          }
          setSuccessData({ title: "Evaluator saved" });
      }
    } catch (e) {
      setErrorData({ title: "Failed to save evaluator" });
    }
  };

  const handleEditEvaluator = (id: string) => {
    const s = savedEvaluators.find((x) => x.id === id);
    if (!s) return;
    setJudgeForm({
      ...judgeForm,
      criteria: s.criteria,
      name: s.name,
      model: s.model,
      model_name: s.model,
      preset_id: s.preset_id || "",
    });
    setGroundTruth(s.ground_truth || "");
    const target = Array.isArray(s.target) ? s.target : [];
    if (target.length === 0) {
      setRunOnExisting(true);
      setRunOnNew(false);
    } else {
      setRunOnExisting(target.includes("existing"));
      setRunOnNew(target.includes("new"));
    }
    // Load from agent_ids (new) or flow_ids (old) for backward compatibility
    const flowIds = Array.isArray(s.agent_ids) ? s.agent_ids : (Array.isArray(s.flow_ids) ? s.flow_ids : []);
    setSelectedFlowIds(flowIds);
    setFilterSessionId(s.session_id || "");
    setFilterTraceId(s.trace_id || "");
    try {
      const keys = loadSavedModelKeys();
      setModelApiKey((s.model && keys[s.model]) || "");
    } catch {
      setModelApiKey("");
    }
    setEditingEvaluator(id);
    setIsJudgeDialogOpen(true);
  };

  const handleDeleteEvaluator = async (id: string) => {
    try {
      await deleteEvaluator(id);
      setSavedEvaluators((s) => s.filter((it) => it.id !== id));
      setSuccessData({ title: "Evaluator deleted" });
    } catch (e) {
      setErrorData({ title: "Failed to delete evaluator" });
    }
  };

  const handleCreateScore = async () => {
    if (!scoreForm.trace_id || !scoreForm.name) return;
    setIsSubmitting(true);
    try {
      await createEvaluationScore({
        trace_id: scoreForm.trace_id,
        name: scoreForm.name,
        value: parseFloat(scoreForm.value),
        comment: scoreForm.comment
      });
      setIsScoreDialogOpen(false);
      resetForms();
      fetchData(); // Refresh list
      setSuccessData({ title: "Score added successfully" });
    } catch (error) {
      console.error("Failed to create score", error);
      setErrorData({ title: "Failed to create score" });
    } finally {
      setIsSubmitting(false);
    }
  };

  // --- Render Helpers ---

  const renderOverview = () => {
    if (!analytics) return <div>Loading...</div>;
    const metrics = analytics?.by_name ?? [];

    return (
      <div className="flex flex-col gap-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Evaluations</h3>
            <p className="text-3xl font-bold mt-2">{analytics.total_scores}</p>
          </div>
          <div className="p-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Metrics Tracked</h3>
            <p className="text-3xl font-bold mt-2">{metrics.length}</p>
          </div>
          <div className="p-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Avg Quality</h3>
            <p className="text-3xl font-bold mt-2">
              {(
                metrics.reduce((acc, curr) => acc + curr.average, 0) /
                (metrics.length || 1)
              ).toFixed(2)}
            </p>
          </div>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="p-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-lg font-semibold mb-4">Average Scores by Metric</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 1]} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff' }}
                  />
                  <Bar dataKey="average" fill="#4f46e5" radius={[4, 4, 0, 0]}>
                    {metrics.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.average > 0.7 ? "#10b981" : entry.average > 0.4 ? "#f59e0b" : "#ef4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="p-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-lg font-semibold mb-4">Evaluation Volume</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', color: '#fff' }}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderScoresList = () => {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800">
          <h3 className="font-medium">Recent Scores</h3>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={fetchData}
            >
              Refresh
            </Button>
            <Button 
              size="sm" 
              onClick={() => setIsScoreDialogOpen(true)}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" /> Add Score
            </Button>
          </div>
        </div>
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input
              placeholder="Filter by Trace ID"
              value={scoreFilters.trace_id}
              onChange={(e) => setScoreFilters({ ...scoreFilters, trace_id: e.target.value })}
            />
            <Input
              placeholder="Filter by Metric Name"
              value={scoreFilters.name}
              onChange={(e) => setScoreFilters({ ...scoreFilters, name: e.target.value })}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={fetchData}
                className="flex-1"
              >
                Apply Filters
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setScoreFilters({ trace_id: "", name: "" });
                  fetchData();
                }}
              >
                Clear
              </Button>
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
              <tr>
                <th className="px-6 py-3">Timestamp</th>
                <th className="px-6 py-3">Trace ID</th>
                <th className="px-6 py-3">Metric</th>
                <th className="px-6 py-3">Value</th>
                <th className="px-6 py-3">Source</th>
                  <th className="px-6 py-3">Comment</th>
                  <th className="px-6 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {recentScores.map((score) => (
                  <tr key={score.id ?? `${score.trace_id}-${score.name}-${score.created_at ?? ""}`} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="px-6 py-4">
                    {score.created_at ? new Date(score.created_at).toLocaleString() : "-"}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-blue-600 dark:text-blue-400">
                    {shortId(score.trace_id)}
                  </td>
                  <td className="px-6 py-4 font-medium">{score.name}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      score.value > 0.7 ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" :
                      score.value > 0.4 ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200" :
                      "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                    }`}>
                      {score.value.toFixed(2)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 rounded text-xs bg-gray-100 dark:bg-gray-700">
                      {score.source}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-500 truncate max-w-xs" title={score.comment}>
                    {score.comment || "-"}
                  </td>
                  <td className="px-6 py-4">
                    <Button
                      size="sm"
                      onClick={() => {
                        setJudgeForm({ ...judgeForm, trace_id: score.trace_id || "", criteria: "", name: "" });
                        setIsJudgeDialogOpen(true);
                      }}
                    >
                      Judge
                    </Button>
                  </td>
                </tr>
              ))}
              {recentScores.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    No evaluation scores found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background">
      <div className="flex flex-none flex-col justify-between border-b px-6 py-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-semibold tracking-tight">Evaluation</h2>
          <p className="text-sm text-muted-foreground">Monitor quality metrics, run LLM judges, and review traces.</p>
        </div>
      </div>
      <div className="flex-1 overflow-hidden p-6">
        <div className="flex flex-col h-full w-full max-w-[1600px] mx-auto">
        {/* Tabs Header */}
        <div className="flex border-b border-gray-200 dark:border-gray-700 mb-6">
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "overview"
                ? "border-blue-500 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
            }`}
            onClick={() => setActiveTab("overview")}
          >
            Overview
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "scores"
                ? "border-blue-500 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
            }`}
            onClick={() => setActiveTab("scores")}
          >
            Scores
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "judges"
                ? "border-blue-500 text-blue-600 dark:text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
            }`}
            onClick={() => setActiveTab("judges")}
          >
            LLM Judges
          </button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : (
            <>
              {activeTab === "overview" && renderOverview()}
              {activeTab === "scores" && renderScoresList()}
              {activeTab === "judges" && (
                <div className="flex flex-col gap-6">
                  <div className="p-8 text-center bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                    <h3 className="text-lg font-medium mb-2">LLM Judges Configuration</h3>
                    <p className="text-gray-500 mb-6">
                      Configure automated evaluators to grade your traces based on custom criteria.
                    </p>
                    {status && !status.langfuse_available && (
                      <p className="text-sm text-red-600 dark:text-red-400 mb-4">
                        Langfuse is not configured. Please set LANGFUSE_* environment variables.
                      </p>
                    )}
                    {status && !status.llm_judge_available && (
                      <p className="text-sm text-amber-600 dark:text-amber-400 mb-4">
                        LLM Judge is unavailable. Please install LiteLLM in the backend.
                      </p>
                    )}
                    <button 
                      onClick={() => {
                        setEditingEvaluator(null);
                        resetForms();
                        setIsJudgeDialogOpen(true);
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex items-center gap-2 mx-auto"
                    >
                      <Play className="h-4 w-4" />
                      Create New Judge
                    </button>
                  </div>

                  {/* Saved Evaluators List */}
                  <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800">
                      <h3 className="font-medium">Saved Evaluators</h3>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" onClick={async () => {
                          try { const items = await listEvaluators(); if (Array.isArray(items)) setSavedEvaluators(items as any); else if (items && Array.isArray((items as any).items)) setSavedEvaluators((items as any).items); else if (items && Array.isArray((items as any).data)) setSavedEvaluators((items as any).data); } catch { }
                        }}>Refresh</Button>
                      </div>
                    </div>
                    <div className="overflow-x-auto p-4">
                      {savedEvaluators.length === 0 ? (
                        <div className="text-sm text-gray-500">No saved evaluators.</div>
                      ) : (
                        <table className="w-full text-sm text-left">
                          <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th className="px-4 py-2">Name</th>
                              <th className="px-4 py-2">Model</th>
                              <th className="px-4 py-2">Criteria</th>
                              <th className="px-4 py-2">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {savedEvaluators.map((ev) => (
                              <tr key={ev.id} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                                <td className="px-4 py-3 font-medium">{ev.name}</td>
                                <td className="px-4 py-3">{ev.model}</td>
                                <td className="px-4 py-3 truncate max-w-xl" title={ev.criteria}>{ev.criteria}</td>
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-2">
                                    <Button size="sm" onClick={() => handleEditEvaluator(ev.id)}>Edit</Button>
                                    <Button size="sm" variant="outline" onClick={async () => {
                                      // Run evaluator immediately by creating a config that targets existing traces
                                      try {
                                        const payload: any = { name: ev.name, criteria: ev.criteria, model: ev.model, target: 'existing' };
                                        if ((ev as any).flow_ids) payload.flow_ids = (ev as any).flow_ids;
                                        if ((ev as any).flow_id) payload.flow_id = (ev as any).flow_id;
                                        if ((ev as any).flow_name) payload.flow_name = (ev as any).flow_name;
                                        if ((ev as any).session_id) payload.session_id = (ev as any).session_id;
                                        if ((ev as any).trace_id) payload.trace_id = (ev as any).trace_id;
                                        if ((ev as any).preset_id) payload.preset_id = (ev as any).preset_id;
                                        if ((ev as any).ground_truth) payload.ground_truth = (ev as any).ground_truth;
                                        await createEvaluator(payload);
                                        setSuccessData({ title: 'Evaluator queued for existing traces' });
                                        // refresh saved list
                                        try { const items = await listEvaluators(); if (Array.isArray(items)) setSavedEvaluators(items as any); } catch (e) {}
                                      } catch (e) { setErrorData({ title: 'Failed to run evaluator' }); }
                                    }}>Run</Button>
                                    <Button size="sm" variant="ghost" onClick={async () => { try { await handleDeleteEvaluator(ev.id); } catch { } }}>Delete</Button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </div>

                  <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
                    <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800">
                      <h3 className="font-medium">Pending Traces</h3>
                      <Button size="sm" onClick={fetchData} variant="outline">Refresh</Button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                          <tr>
                            <th className="px-6 py-3">Trace ID</th>
                            <th className="px-6 py-3">Name</th>
                            <th className="px-6 py-3">Flow</th>
                            <th className="px-6 py-3">Scores</th>
                            <th className="px-6 py-3">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {safePendingTraces.map((trace) => (
                            <tr key={trace.id} className="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                              <td className="px-6 py-4 font-mono text-xs text-blue-600 dark:text-blue-400">
                                {shortId(trace.id)}
                              </td>
                              <td className="px-6 py-4">{trace.name || "-"}</td>
                              <td className="px-6 py-4">{trace.flow_name || "-"}</td>
                              <td className="px-6 py-4">
                                {trace.has_scores ? `${trace.score_count} scores` : "No scores"}
                              </td>
                              <td className="px-6 py-4">
                                <Button
                                  size="sm"
                                  onClick={() => {
                                    setJudgeForm({ ...judgeForm, trace_id: trace.id });
                                    setIsJudgeDialogOpen(true);
                                  }}
                                >
                                  Judge
                                </Button>
                              </td>
                            </tr>
                          ))}
                          {safePendingTraces.length === 0 && (
                            <tr>
                              <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                                No pending traces found.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        </div>
      </div>

      {/* Run Judge Dialog */}
      <Dialog open={isJudgeDialogOpen} onOpenChange={setIsJudgeDialogOpen}>
        <DialogContent className="max-w-2xl w-full">
          <DialogHeader>
            <DialogTitle>Run LLM Judge</DialogTitle>
            <DialogDescription>
              Evaluate a specific trace using an LLM based on your criteria.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <p className="text-sm text-gray-600">Choose where the evaluator should run.</p>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={runOnNew} onChange={(e) => setRunOnNew(e.target.checked)} className="form-checkbox" />
                <span className="text-sm">Run on New Traces</span>
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={runOnExisting} onChange={(e) => setRunOnExisting(e.target.checked)} className="form-checkbox" />
                <span className="text-sm">Run on Existing Traces</span>
              </label>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">Use a Preset</label>
                <Select value={judgeForm.preset_id} onValueChange={(val) => {
                  const p = presets.find((x) => x.id === val);
                  if (p) setJudgeForm({ ...judgeForm, criteria: p.criteria, name: p.name, preset_id: val, saved_evaluator_id: "" });
                }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a preset" />
                  </SelectTrigger>
                  <SelectContent>
                    {presets.map((p) => (
                      <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedPreset?.requires_ground_truth && (
                  <p className="text-xs text-amber-600">This preset requires ground truth.</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Flows</label>
                <div className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm max-h-44 overflow-y-auto">
                  {flowList && flowList.length > 0 ? (
                    flowList.map((f: any) => {
                      const fid = f.metadata?.flow_id || f.metadata?.agent_id || f.id || f.metadata?.endpoint_name || "";
                      if (!fid) return null;
                      const label = f.metadata?.display_name || f.name || f.metadata?.endpoint_name || f.id || fid;
                      const checked = selectedFlowIds.includes(fid);
                      return (
                        <label key={fid} className="flex items-center gap-2 py-1">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedFlowIds((s) => Array.from(new Set([...s, fid])));
                              } else {
                                setSelectedFlowIds((s) => s.filter((x) => x !== fid));
                              }
                            }}
                            className="form-checkbox"
                          />
                          <span className="text-sm">{label}</span>
                        </label>
                      );
                    })
                  ) : (
                    <div className="text-sm text-gray-500 py-2">No flows available</div>
                  )}
                </div>
                <p className="text-xs text-gray-500">Select one or more flows (agents) to target.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">Judge Model Name</label>
                <Input placeholder="e.g. gpt-4o or custom" value={judgeForm.model_name} onChange={(e) => setJudgeForm({ ...judgeForm, model_name: e.target.value })} />
                <p className="text-xs text-gray-500">Name of the LLM to use as judge. If empty, a default model will be used.</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Model API Key (optional)</label>
                <div className="flex gap-2">
                  <Input placeholder="sk-..." value={modelApiKey} onChange={(e) => setModelApiKey(e.target.value)} />
                </div>
                <p className="text-xs text-gray-500">API key is stored locally in your browser only and will be saved when you Save or Run the evaluator.</p>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Evaluation Criteria</label>
              <textarea 
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. Is the answer helpful and accurate?"
                value={judgeForm.criteria}
                onChange={(e) => setJudgeForm({...judgeForm, criteria: e.target.value})}
              />
            </div>

            {requiresGroundTruth && (
              <div className="space-y-2">
                <label className="text-sm font-medium">Ground Truth</label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  placeholder="Provide expected answer/output used as reference for evaluation."
                  value={groundTruth}
                  onChange={(e) => setGroundTruth(e.target.value)}
                />
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="outline" onClick={handlePreview}>Preview</Button>
              <Button variant="outline" onClick={handleSaveEvaluator}>Save Evaluator</Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setEditingEvaluator(null);
              setIsJudgeDialogOpen(false);
            }}>Cancel</Button>
            <Button onClick={handleRunJudge} disabled={isSubmitting}>
              {isSubmitting ? "Starting..." : "Run Evaluation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Evaluation Preview</DialogTitle>
            <DialogDescription>Preview the evaluation prompt that will be sent to the LLM.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <h4 className="font-medium">System Prompt</h4>
              <pre className="whitespace-pre-wrap text-xs p-3 bg-gray-100 rounded mt-2">{previewData?.system_prompt}</pre>
            </div>
            <div>
              <h4 className="font-medium">User Prompt (with trace)</h4>
              <pre className="whitespace-pre-wrap text-xs p-3 bg-gray-100 rounded mt-2">{previewData?.user_prompt}</pre>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsPreviewOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Score Dialog */}
      <Dialog open={isScoreDialogOpen} onOpenChange={setIsScoreDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Manual Score</DialogTitle>
            <DialogDescription>
              Manually evaluate a trace.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Trace ID</label>
              <Input 
                placeholder="Trace ID" 
                value={scoreForm.trace_id}
                onChange={(e) => setScoreForm({...scoreForm, trace_id: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Metric Name</label>
              <Input 
                placeholder="e.g. Accuracy, User Satisfaction" 
                value={scoreForm.name}
                onChange={(e) => setScoreForm({...scoreForm, name: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Score (0.0 - 1.0)</label>
              <Input 
                type="number" 
                min="0" max="1" step="0.1"
                value={scoreForm.value}
                onChange={(e) => setScoreForm({...scoreForm, value: e.target.value})}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Comment (Optional)</label>
              <Input 
                placeholder="Reasoning..." 
                value={scoreForm.comment}
                onChange={(e) => setScoreForm({...scoreForm, comment: e.target.value})}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsScoreDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleCreateScore} disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Save Score"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
