import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Trial } from "../api/client";

interface UseSSEOptions {
  runId: string | null;
  onTrialComplete?: (trial: Trial) => void;
  onRunComplete?: () => void;
  onError?: (error: string) => void;
}

export function useSSE({
  runId,
  onTrialComplete,
  onRunComplete,
  onError,
}: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);
  const qc = useQueryClient();

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!runId) return;

    const baseUrl = import.meta.env.VITE_API_URL ?? "";
    const source = new EventSource(
      `${baseUrl}/api/runs/${runId}/stream`,
    );
    sourceRef.current = source;

    source.addEventListener("trial_completed", (e: MessageEvent) => {
      const trial: Trial = JSON.parse(e.data);
      onTrialComplete?.(trial);
      qc.invalidateQueries({ queryKey: ["run", runId] });
    });

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
            summary.status === "completed" ||
            summary.status === "failed"
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
      onError?.("SSE connection lost. Reconnecting...");
    });

    return () => {
      clearInterval(pollInterval);
      disconnect();
    };
  }, [runId, onTrialComplete, onRunComplete, onError, qc, disconnect]);

  return { disconnect };
}
