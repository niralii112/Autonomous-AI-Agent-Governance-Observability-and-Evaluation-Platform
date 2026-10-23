import { useQuery } from "@tanstack/react-query";

import {
  fetchAgents,
  fetchAgentById,
} from "../api/agents";

export const agentQueryKeys = {
  all: ["agents"] as const,
  list: () => ["agents", "list"] as const,
  detail: (agentId: string) =>
    ["agents", "detail", agentId] as const,
};

export function useAgents() {
  return useQuery({
    queryKey: agentQueryKeys.list(),
    queryFn: fetchAgents,
  });
}

export function useAgent(agentId: string) {
  return useQuery({
    queryKey: agentQueryKeys.detail(agentId),
    queryFn: () => fetchAgentById(agentId),
    enabled: agentId.trim().length > 0,
  });
}
