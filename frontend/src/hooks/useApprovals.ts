import { actionQueryKeys } from "./useActions";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  fetchApprovals,
  submitApproval,
  submitRejection,
} from "../api/approvals";

export const approvalQueryKeys = {
  all: ["approvals"] as const,
  list: (page: number, status?: "PENDING") => ["approvals", "list", page, status] as const,
};

export function useApprovals(page = 1, status?: "PENDING") {
  return useQuery({
    queryKey: approvalQueryKeys.list(page, status),
    queryFn: () => fetchApprovals(page, status),
  });
}

export function useApproveAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      approvalId,
      reviewComment,
    }: {
      approvalId: string;
      reviewComment?: string;
    }) => submitApproval(approvalId, reviewComment),

    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: approvalQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: actionQueryKeys.all }),
      ]);
    },
  });
}

export function useRejectAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      approvalId,
      reviewComment,
    }: {
      approvalId: string;
      reviewComment: string;
    }) => submitRejection(approvalId, reviewComment),

    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: approvalQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: actionQueryKeys.all }),
      ]);
    },
  });
}
