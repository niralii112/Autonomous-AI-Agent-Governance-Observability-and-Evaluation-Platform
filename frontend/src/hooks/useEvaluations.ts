import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchEvaluations,
  fetchEvaluationById,
  postRunEvaluation,
  fetchOverviewMetrics,
  fetchAgentPerformance,
  type EvaluationFilterParams,
  type RunEvaluationBody,
} from "../api/evaluations";

export const evaluationQueryKeys = {
  all: ["evaluations"] as const,
  list: (params: EvaluationFilterParams) => ["evaluations", "list", params] as const,
  detail: (id: string) => ["evaluations", "detail", id] as const,
  overview: (windowHours: number) => ["evaluations", "overview", windowHours] as const,
  agentPerformance: (agentId: string) => ["evaluations", "agentPerformance", agentId] as const,
};

export function useEvaluations(params: EvaluationFilterParams = {}) {
  return useQuery({
    queryKey: evaluationQueryKeys.list(params),
    queryFn: () => fetchEvaluations(params),
  });
}

export function useEvaluation(evaluationId: string) {
  return useQuery({
    queryKey: evaluationQueryKeys.detail(evaluationId),
    queryFn: () => fetchEvaluationById(evaluationId),
    enabled: Boolean(evaluationId && evaluationId.trim().length > 0),
  });
}

export function useRunEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RunEvaluationBody) => postRunEvaluation(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: evaluationQueryKeys.all });
    },
  });
}

export function useEvaluationOverview(windowHours = 24) {
  return useQuery({
    queryKey: evaluationQueryKeys.overview(windowHours),
    queryFn: () => fetchOverviewMetrics(windowHours),
  });
}

export function useAgentPerformance(agentId: string) {
  return useQuery({
    queryKey: evaluationQueryKeys.agentPerformance(agentId),
    queryFn: () => fetchAgentPerformance(agentId),
    enabled: Boolean(agentId && agentId.trim().length > 0),
  });
}
