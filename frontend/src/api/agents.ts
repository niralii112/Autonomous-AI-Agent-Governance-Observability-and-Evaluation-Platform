import {
  listAgents,
  getAgent,
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
