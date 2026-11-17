import {
  listAgents,
  getAgent,
  listAgentScenarios,
  runAgentScenario,
} from "./generated-services";

export async function fetchAgents() {
  const { data, error } = await listAgents();

  if (error) {
    throw new Error(
      "Unable to load registered agents."
    );
  }

  return data;
}

export async function fetchAgentById(agentId: string) {
  const { data, error } = await getAgent({
    params: {
      path: {
        agent_id: agentId,
      },
    },
  });

  if (error) {
    throw new Error(
      "Unable to load agent details."
    );
  }

  return data;
}


export async function fetchAgentScenarios(agentId: string, signal: AbortSignal) {
  const { data, response } = await listAgentScenarios({
    params: { path: { agent_id: agentId } },
    signal,
  });

  if (response.status === 403) {
    throw new Error("Your account does not have access to scenarios.");
  }
  if (!data) {
    throw new Error("Unable to load scenarios for this agent.");
  }

  return data.scenarios;
}

export async function submitAgentScenario(agentId: string, scenarioKey: string) {
  const { data, response } = await runAgentScenario({
    params: { path: { agent_id: agentId } },
    body: { scenario_key: scenarioKey },
  });

  if (response.status === 403) {
    throw new Error("Your account does not have permission to run scenarios.");
  }
  if (!data) {
    throw new Error("Couldn’t confirm the run. Check Agent Actions before trying again.");
  }

  return data.submission;
}
