import { useQuery } from "@tanstack/react-query";
import { getSystemHealth, getSystemInfo } from "../api/generated-services";

export function useSystemHealth() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: async () => {
      const { data, response } = await getSystemHealth();
      if (!response.ok) throw new Error(`Health check returned HTTP ${response.status}.`);
      if (!data || !["OK", "DEGRADED", "DOWN"].includes(data.status) || !Array.isArray(data.components)) {
        throw new Error("The health check returned an unexpected response.");
      }
      return data;
    },
    refetchInterval: 15000,
  });
}

export function useSystemInfo() {
  return useQuery({
    queryKey: ["system", "info"],
    queryFn: async () => {
      const { data, error } = await getSystemInfo();
      if (error || !data) throw new Error("Failed to load system info.");
      return data;
    },
  });
}
