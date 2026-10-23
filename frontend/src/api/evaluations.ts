import {
  listEvaluations,
  getEvaluation,
  runEvaluation,
  getOverviewMetrics,
  getAgentPerformance,
} from "./generated-services";
import type { components } from "../types/generated/api";

export type RunEvaluationBody = components["schemas"]["EvaluationRunRequest"];

export type EvaluationFilterParams = {
  agent_id?: string;
  evaluation_type?: string;
  page?: number;
  page_size?: number;
};

export async function fetchEvaluations(params: EvaluationFilterParams = {}) {
  const { data, error } = await listEvaluations({
    params: {
      query: {
        agent_id: params.agent_id,
        page: params.page ?? 1,
        page_size: params.page_size ?? 25,
      },
    },
  });

  if (error) {
    throw new Error("Unable to fetch evaluations list.");
  }
  return data;
}

export async function fetchEvaluationById(evaluationId: string) {
  const { data, error } = await getEvaluation({
    params: {
      path: { evaluation_id: evaluationId },
    },
  });

  if (error) {
    throw new Error("Unable to fetch evaluation details.");
  }
  return data;
}

export async function postRunEvaluation(body: RunEvaluationBody) {
  const { data, error } = await runEvaluation({
    body,
  });

  if (error) {
    throw new Error("Failed to start evaluation run.");
  }
  return data;
}

export async function fetchOverviewMetrics(windowHours = 24) {
  const { data, error } = await getOverviewMetrics({
    params: {
      query: { window_hours: windowHours },
    },
  });

  if (error) {
    throw new Error("Unable to fetch overview metrics.");
  }
  return data;
}

export async function fetchAgentPerformance(agentId: string) {
  const { data, error } = await getAgentPerformance({
    params: {
      query: { agent_id: agentId },
    },
  });

  if (error) {
    throw new Error("Unable to fetch agent performance.");
  }
  return data;
}
