import {
  listPolicies,
  listGovernanceDecisions,
} from "./generated-services";

export async function fetchPolicies() {
  const { data, error } = await listPolicies();

  if (error) {
    throw new Error("Unable to load governance policies.");
  }

  return data;
}

export async function fetchGovernanceDecisions() {
  const { data, error } = await listGovernanceDecisions();

  if (error) {
    throw new Error("Unable to load governance decisions.");
  }

  return data;
}
