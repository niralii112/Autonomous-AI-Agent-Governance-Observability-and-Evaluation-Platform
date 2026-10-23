import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchActions,
  fetchActionById,
  postActionRetry,
  postSubmitAction,
  type ActionFilterParams,
  type ActionSubmission,
} from "../api/actions";

export const actionQueryKeys = {
  all: ["actions"] as const,
  list: (params: ActionFilterParams) => ["actions", "list", params] as const,
  detail: (id: string) => ["actions", "detail", id] as const,
};

export function useActions(params: ActionFilterParams = {}) {
  return useQuery({
    queryKey: actionQueryKeys.list(params),
    queryFn: () => fetchActions(params),
  });
}

export function useAction(actionId: string) {
  return useQuery({
    queryKey: actionQueryKeys.detail(actionId),
    queryFn: () => fetchActionById(actionId),
    enabled: Boolean(actionId && actionId.trim().length > 0),
  });
}

export function useRetryAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (actionId: string) => postActionRetry(actionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: actionQueryKeys.all });
    },
  });
}

export function useSubmitAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (submission: ActionSubmission) => postSubmitAction(submission),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: actionQueryKeys.all });
    },
  });
}
