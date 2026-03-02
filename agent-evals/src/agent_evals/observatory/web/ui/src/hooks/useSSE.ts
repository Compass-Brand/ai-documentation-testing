import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Trial } from "../api/client";

const MAX_RECONNECTS = 10;

export interface SSEAlert {
  type: string;
  data: Record<string, unknown>;
}

interface UseSSEOptions {
  runId: string | null;
  onTrialComplete?: (trial: Trial) => void;
  onRunComplete?: () => void;
  onError?: (error: string) => void;
  onAlert?: (alert: SSEAlert) => void;
}

export function useSSE({
  runId,
  onTrialComplete,
  onRunComplete,
  onError,
  onAlert,
}: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectCountRef = useRef(0);
  const qc = useQueryClient();

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!runId) return;
    reconnectCountRef.current = 0;

    const baseUrl = import.meta.env.VITE_API_URL ?? "";
    const source = new EventSource(
      `${baseUrl}/api/runs/${runId}/stream`,
    );
    sourceRef.current = source;

    source.addEventListener("trial_completed", (e: MessageEvent) => {
      reconnectCountRef.current = 0;
      try {
        const trial: Trial = JSON.parse(e.data);
        onTrialComplete?.(trial);
        qc.invalidateQueries({ queryKey: ["run", runId] });
      } catch (err) {
        console.error("[useSSE] malformed JSON in trial_completed event, skipping:", err);
      }
    });

    const alertTypes = [
      "anomaly_alert",
      "model_budget_exceeded",
      "burn_rate_alert",
    ];
    for (const alertType of alertTypes) {
      source.addEventListener(alertType, (e: MessageEvent) => {
        try {
          const data: Record<string, unknown> = JSON.parse(e.data);
          onAlert?.({ type: alertType, data });
        } catch (err) {
          console.error(`[useSSE] malformed JSON in ${alertType} event, skipping:`, err);
        }
      });
    }

    // Backend does not emit a run_complete event.
    // Poll the run summary to detect completion instead.
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(
          `${baseUrl}/api/runs/${runId}`,
        );
        if (res.ok) {
          const summary = await res.json();
          if (
            summary?.status === "completed" ||
            summary?.status === "failed"
          ) {
            onRunComplete?.();
            qc.invalidateQueries({ queryKey: ["run", runId] });
            qc.invalidateQueries({ queryKey: ["trials", runId] });
            clearInterval(pollInterval);
            disconnect();
          }
        }
      } catch {
        // Ignore poll errors; SSE reconnects handle transient failures
      }
    }, 5000);

    source.addEventListener("error", () => {
      reconnectCountRef.current += 1;
      if (reconnectCountRef.current >= MAX_RECONNECTS) {
        disconnect();
        onError?.("SSE connection failed after maximum reconnection attempts.");
      } else {
        onError?.("SSE connection lost. Reconnecting...");
      }
    });

    return () => {
      clearInterval(pollInterval);
      disconnect();
    };
  }, [runId, onTrialComplete, onRunComplete, onError, onAlert, qc, disconnect]);

  return { disconnect };
}
