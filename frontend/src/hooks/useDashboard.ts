import { useQuery } from "@tanstack/react-query";

import {
  fetchOverviewMetrics,
  fetchAgentPerformance,
} from "../api/dashboard";

export const dashboardQueryKeys = {
  overview: ["dashboard", "overview"] as const,

  agentPerformance: (agentId: string) =>
    ["dashboard", "agentPerformance", agentId] as const,
};

export function useOverviewMetrics() {
  return useQuery({
    queryKey: dashboardQueryKeys.overview,
    queryFn: fetchOverviewMetrics,
  });
}

export function useAgentPerformance(agentId: string) {
  return useQuery({
    queryKey: dashboardQueryKeys.agentPerformance(agentId),
    queryFn: () => fetchAgentPerformance(agentId),
    enabled: agentId.trim().length > 0,
  });
}
