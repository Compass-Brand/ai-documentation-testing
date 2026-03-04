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
  const lastEventIdRef = useRef(0);
  const lastInvalidation = useRef(0);
  const lastEventTime = useRef(Date.now());
  const qc = useQueryClient();

  // Stable refs for callbacks to avoid tearing down EventSource on callback identity changes
  const onTrialCompleteRef = useRef(onTrialComplete);
  const onRunCompleteRef = useRef(onRunComplete);
  const onErrorRef = useRef(onError);
  const onAlertRef = useRef(onAlert);

  useEffect(() => { onTrialCompleteRef.current = onTrialComplete; }, [onTrialComplete]);
  useEffect(() => { onRunCompleteRef.current = onRunComplete; }, [onRunComplete]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onAlertRef.current = onAlert; }, [onAlert]);

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!runId) return;
    reconnectCountRef.current = 0;
    lastEventIdRef.current = 0;

    const baseUrl = import.meta.env.VITE_API_URL ?? "";
    const source = new EventSource(
      `${baseUrl}/api/runs/${runId}/stream`,
    );
    sourceRef.current = source;

    source.addEventListener("trial_completed", (e: MessageEvent) => {
      const eventId = parseInt(e.lastEventId, 10);
      if (!isNaN(eventId) && eventId <= lastEventIdRef.current) return;
      lastEventIdRef.current = eventId;

      reconnectCountRef.current = 0;
      lastEventTime.current = Date.now();
      try {
        const trial: Trial = JSON.parse(e.data);
        onTrialCompleteRef.current?.(trial);
        // Throttle query invalidation to at most once per 5 seconds
        const now = Date.now();
        if (now - lastInvalidation.current > 5000) {
          lastInvalidation.current = now;
          qc.invalidateQueries({ queryKey: ["run", runId] });
        }
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
          onAlertRef.current?.({ type: alertType, data });
        } catch (err) {
          console.error(`[useSSE] malformed JSON in ${alertType} event, skipping:`, err);
        }
      });
    }

    // Backend does not emit a run_complete event.
    // Poll the run summary to detect completion instead.
    // Skip poll when SSE is healthy (received an event within the last 10 seconds).
    const pollInterval = setInterval(async () => {
      if (Date.now() - lastEventTime.current < 10000) return;
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
            onRunCompleteRef.current?.();
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
        clearInterval(pollInterval);
        disconnect();
        onErrorRef.current?.("SSE connection failed after maximum reconnection attempts.");
      } else {
        onErrorRef.current?.("SSE connection lost. Reconnecting...");
      }
    });

    return () => {
      clearInterval(pollInterval);
      disconnect();
    };
  }, [runId, qc, disconnect]);

  return { disconnect };
}
