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
  list: () => ["approvals", "list"] as const,
};

export function useApprovals() {
  return useQuery({
    queryKey: approvalQueryKeys.list(),
    queryFn: fetchApprovals,
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
      await queryClient.invalidateQueries({
        queryKey: approvalQueryKeys.all,
      });
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
      await queryClient.invalidateQueries({
        queryKey: approvalQueryKeys.all,
      });
    },
  });
}
