import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { useActiveRuns, useRun, useTrials } from "../api/hooks";
import { useSSE, type SSEAlert } from "./useSSE";
import type { Trial } from "../api/client";
import type { AlertItem } from "../components/AlertsFeed";

const MAX_RECENT_TRIALS = 50;
const MAX_SCORES = 1000;
const MAX_TIMESTAMPS = 1000;
// Fallback for total gold tasks; should be replaced with API-provided value when available
const DEFAULT_TOTAL_TASKS = 355;

export interface LiveMonitorState {
  selectedRunId: string | null;
  setSelectedRunId: (id: string | null) => void;

  recentTrials: Trial[];
  alerts: AlertItem[];

  progress: number;
  trialsCompleted: number;
  trialsTotal: number;
  uniqueTasksSeen: number;
  totalTasks: number;
  trialsPerMin: number;
  estimatedRemainingMinutes: number | null;

  meanScore: number;
  totalCost: number;
  totalTokens: number;
  avgLatency: number;
  errorCount: number;

  byModel: Record<string, { mean_score: number; trial_count: number; cost: number }>;
  byVariant: Record<string, { mean_score: number; trial_count: number }>;

  isConnected: boolean;
  lastUpdated: Date | null;
  isLoading: boolean;

  scores: number[];
}

export function useLiveMonitorState(totalTasksOverride?: number): LiveMonitorState {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [recentTrials, setRecentTrials] = useState<Trial[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [scores, setScores] = useState<number[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const trialTimestamps = useRef<number[]>([]);

  const { data: activeRunsData } = useActiveRuns();
  const activeRuns = activeRunsData?.runs ?? [];

  // Auto-select first active run if none selected
  useEffect(() => {
    if (selectedRunId) return;
    if (activeRuns.length > 0) {
      setSelectedRunId(activeRuns[0].run_id);
    }
  }, [activeRuns, selectedRunId]);

  // Reset state when run changes
  useEffect(() => {
    setRecentTrials([]);
    setAlerts([]);
    setScores([]);
    setIsConnected(false);
    setLastUpdated(null);
    trialTimestamps.current = [];
  }, [selectedRunId]);

  const { data: summary, isLoading } = useRun(selectedRunId);
  const { data: trials } = useTrials(selectedRunId);

  const onTrialComplete = useCallback((trial: Trial) => {
    setRecentTrials((prev) => [trial, ...prev].slice(0, MAX_RECENT_TRIALS));
    setScores((prev) =>
      prev.length >= MAX_SCORES
        ? [...prev.slice(1), trial.score]
        : [...prev, trial.score],
    );
    setLastUpdated(new Date());
    setIsConnected(true);
    trialTimestamps.current.push(Date.now());
    if (trialTimestamps.current.length > MAX_TIMESTAMPS) {
      trialTimestamps.current = trialTimestamps.current.slice(-MAX_TIMESTAMPS);
    }
  }, []);

  const onRunComplete = useCallback(() => {
    setIsConnected(false);
  }, []);

  const onError = useCallback(() => {
    setIsConnected(false);
  }, []);

  const onAlert = useCallback((alert: SSEAlert) => {
    const message = formatAlertMessage(alert);
    setAlerts((prev) => [
      { type: alert.type, message, timestamp: new Date() },
      ...prev,
    ]);
    setLastUpdated(new Date());
  }, []);

  useSSE({
    runId: selectedRunId,
    onTrialComplete,
    onRunComplete,
    onError,
    onAlert,
  });

  const trialsCompleted = summary?.completed_trials ?? 0;
  const trialsTotal = summary?.total_trials ?? 0;
  const progress = trialsTotal > 0
    ? (trialsCompleted / trialsTotal) * 100
    : 0;

  const trialsPerMin = useMemo(() => {
    const timestamps = trialTimestamps.current;
    if (timestamps.length < 2) {
      // Fallback to summary-based calculation
      if (!summary?.run?.created_at || trialsCompleted === 0) return 0;
      const elapsedMs = Date.now() - new Date(summary.run.created_at).getTime();
      if (elapsedMs < 1000) return 0;
      return trialsCompleted / (elapsedMs / 60000);
    }
    const windowMs = timestamps[timestamps.length - 1] - timestamps[0];
    if (windowMs === 0) return 0;
    return ((timestamps.length - 1) / windowMs) * 60000;
  }, [summary, trialsCompleted, recentTrials]);

  const estimatedRemainingMinutes = useMemo(() => {
    if (trialsPerMin <= 0 || trialsCompleted >= trialsTotal) return null;
    const remaining = trialsTotal - trialsCompleted;
    return remaining / trialsPerMin;
  }, [trialsPerMin, trialsCompleted, trialsTotal]);

  const errorCount = useMemo(
    () => (trials ?? []).filter((t) => t.error !== null).length,
    [trials],
  );

  return {
    selectedRunId,
    setSelectedRunId,
    recentTrials,
    alerts,
    progress,
    trialsCompleted,
    trialsTotal,
    uniqueTasksSeen: summary?.unique_tasks ?? 0,
    totalTasks: totalTasksOverride ?? DEFAULT_TOTAL_TASKS,
    trialsPerMin,
    estimatedRemainingMinutes,
    meanScore: summary?.mean_score ?? 0,
    totalCost: summary?.total_cost ?? 0,
    totalTokens: summary?.total_tokens ?? 0,
    avgLatency: summary?.avg_latency ?? 0,
    errorCount,
    byModel: summary?.by_model ?? {},
    byVariant: summary?.by_variant ?? {},
    isConnected,
    lastUpdated,
    isLoading,
    scores,
  };
}

function formatAlertMessage(alert: SSEAlert): string {
  const d = alert?.data ?? {};
  switch (alert.type) {
    case "anomaly_alert":
      return `Cost anomaly on ${d.model ?? "unknown"}: $${Number(d.cost ?? 0).toFixed(3)} (${Number(d.multiplier ?? 0).toFixed(1)}x average)`;
    case "model_budget_exceeded":
      return `Budget exceeded for ${d.model ?? "unknown"}: $${Number(d.spent ?? 0).toFixed(2)} / $${Number(d.budget ?? 0).toFixed(2)}`;
    case "burn_rate_alert":
      return `High burn rate on ${d.model ?? "unknown"}: $${Number(d.burn_rate_per_minute ?? 0).toFixed(2)}/min`;
    default:
      return `${alert.type}: ${JSON.stringify(d)}`;
  }
}
