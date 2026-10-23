import { useQuery } from "@tanstack/react-query";
import {
  listRiskAssessments,
  getRiskSummary,
  listRiskModels,
} from "../api/generated-services";

export function useRiskSummary(windowHours = 24) {
  return useQuery({
    queryKey: ["risk", "summary", windowHours],
    queryFn: async () => {
      const { data, error } = await getRiskSummary({
        params: {
          query: { window_hours: windowHours },
        },
      });
      if (error) throw new Error("Failed to load risk summary.");
      return data;
    },
  });
}

export function useRiskAssessments(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: ["risk", "assessments", page, pageSize],
    queryFn: async () => {
      const { data, error } = await listRiskAssessments({
        params: {
          query: { page, page_size: pageSize },
        },
      });
      if (error) throw new Error("Failed to load risk assessments.");
      return data;
    },
  });
}

export function useRiskModels() {
  return useQuery({
    queryKey: ["risk", "models"],
    queryFn: async () => {
      const { data, error } = await listRiskModels();
      if (error) throw new Error("Failed to load risk models.");
      return data;
    },
  });
}
