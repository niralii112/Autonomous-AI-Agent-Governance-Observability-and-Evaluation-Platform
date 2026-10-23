import { useQuery } from "@tanstack/react-query";
import { getSystemHealth, getSystemInfo } from "../api/generated-services";

export function useSystemHealth() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: async () => {
      const { data, error } = await getSystemHealth();
      if (error) throw new Error("Failed to load system health.");
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
      if (error) throw new Error("Failed to load system info.");
      return data;
    },
  });
}
