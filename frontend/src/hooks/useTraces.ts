import { useQuery } from "@tanstack/react-query";

import {
  fetchTraces,
  fetchTraceById,
  fetchTracesByAction,
  fetchTraceMetrics,
  type TraceFilters,
} from "../api/traces";

export const traceQueryKeys = {
  all: ["traces"] as const,

  list: (filters: TraceFilters) =>
    ["traces", "list", filters] as const,

  detail: (traceId: string) =>
    ["traces", "detail", traceId] as const,

  byAction: (actionId: string) =>
    ["traces", "byAction", actionId] as const,

  metrics: (windowMinutes: number, bucketSeconds: number) =>
    ["traces", "metrics", windowMinutes, bucketSeconds] as const,
};

export function useTraces(filters: TraceFilters = {}) {
  return useQuery({
    queryKey: traceQueryKeys.list(filters),
    queryFn: () => fetchTraces(filters),
  });
}

export function useTrace(traceId: string) {
  return useQuery({
    queryKey: traceQueryKeys.detail(traceId),
    queryFn: () => fetchTraceById(traceId),
    enabled: traceId.trim().length > 0,
  });
}

export function useTracesByAction(actionId: string) {
  return useQuery({
    queryKey: traceQueryKeys.byAction(actionId),
    queryFn: () => fetchTracesByAction(actionId),
    enabled: actionId.trim().length > 0,
  });
}

export function useTraceMetrics(
  windowMinutes = 60,
  bucketSeconds = 60
) {
  return useQuery({
    queryKey: traceQueryKeys.metrics(windowMinutes, bucketSeconds),
    queryFn: () => fetchTraceMetrics(windowMinutes, bucketSeconds),
  });
}
