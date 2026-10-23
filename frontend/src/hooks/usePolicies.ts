import { useQuery } from "@tanstack/react-query";

import {
  fetchPolicies,
  fetchGovernanceDecisions,
} from "../api/policies";

export const governanceQueryKeys = {
  policies: ["governance", "policies"] as const,
  decisions: ["governance", "decisions"] as const,
};

export function usePolicies() {
  return useQuery({
    queryKey: governanceQueryKeys.policies,
    queryFn: fetchPolicies,
  });
}

export function useGovernanceDecisions() {
  return useQuery({
    queryKey: governanceQueryKeys.decisions,
    queryFn: fetchGovernanceDecisions,
  });
}
