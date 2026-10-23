import {
  getOverviewMetrics,
  getAgentPerformance,
} from "./generated-services";

export async function fetchOverviewMetrics() {
  const { data, error } = await getOverviewMetrics();

  if (error) {
    throw new Error("Unable to load dashboard overview metrics.");
  }

  return data;
}

export async function fetchAgentPerformance(agentId: string) {
  const { data, error } = await getAgentPerformance({
    params: {
      query: {
        agent_id: agentId,
      },
    },
  });

  if (error) {
    throw new Error("Unable to load agent performance metrics.");
  }

  return data;
}
