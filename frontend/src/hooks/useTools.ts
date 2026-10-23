import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchTools,
  fetchToolById,
  postCreateTool,
  patchUpdateTool,
  type ToolCreateParams,
  type ToolUpdateParams,
} from "../api/tools";

export const toolQueryKeys = {
  all: ["tools"] as const,
  list: (page: number, pageSize: number) => ["tools", "list", page, pageSize] as const,
  detail: (id: string) => ["tools", "detail", id] as const,
};

export function useTools(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: toolQueryKeys.list(page, pageSize),
    queryFn: () => fetchTools(page, pageSize),
  });
}

export function useTool(toolId: string) {
  return useQuery({
    queryKey: toolQueryKeys.detail(toolId),
    queryFn: () => fetchToolById(toolId),
    enabled: Boolean(toolId && toolId.trim().length > 0),
  });
}

export function useCreateTool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ToolCreateParams) => postCreateTool(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: toolQueryKeys.all });
    },
  });
}

export function useUpdateTool() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ toolId, body }: { toolId: string; body: ToolUpdateParams }) =>
      patchUpdateTool(toolId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: toolQueryKeys.all });
    },
  });
}
