import {
  listTraces,
  getTrace,
  getTracesByAction,
  getTraceMetrics,
} from "./generated-services";

export type TraceFilters = {
  agentId?: string;
  actionId?: string;
  hasError?: boolean;
  windowMinutes?: number;
  page?: number;
  pageSize?: number;
};

export async function fetchTraces(filters: TraceFilters = {}) {
  const { data, error } = await listTraces({
    params: {
      query: {
        agent_id: filters.agentId || undefined,
        action_id: filters.actionId || undefined,
        has_error: filters.hasError,
        window_minutes: filters.windowMinutes ?? 60,
        page: filters.page ?? 1,
        page_size: filters.pageSize ?? 25,
        sort_by: "start_time",
        sort_order: "desc",
      },
    },
  });

  if (error) {
    throw new Error("Unable to load traces.");
  }

  return data;
}

export async function fetchTraceById(traceId: string) {
  const { data, error } = await getTrace({
    params: {
      path: {
        trace_id: traceId,
      },
    },
  });

  if (error) {
    throw new Error("Unable to load trace details.");
  }

  return data;
}

export async function fetchTracesByAction(actionId: string) {
  const { data, error } = await getTracesByAction({
    params: {
      path: {
        action_id: actionId,
      },
    },
  });

  if (error) {
    throw new Error("Unable to load traces for this action.");
  }

  return data;
}

export async function fetchTraceMetrics(
  windowMinutes = 60,
  bucketSeconds = 60
) {
  const { data, error } = await getTraceMetrics({
    params: {
      query: {
        window_minutes: windowMinutes,
        bucket_seconds: bucketSeconds,
      },
    },
  });

  if (error) {
    throw new Error("Unable to load trace metrics.");
  }

  return data;
}
