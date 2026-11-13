import {
  listApprovals,
  approveAction,
  rejectAction,
} from "./generated-services";

export async function fetchApprovals(page = 1, status?: "PENDING") {
  const { data, error, response } = await listApprovals({
    params: {
      query: {
        page,
        approval_status: status,
        page_size: 25,
        sort_by: "created_at",
        sort_order: "desc",
      },
    },
  });

  if (response.status === 403) {
    throw new Error("Your account does not have access to approval requests.");
  }
  if (error || !data) {
    throw new Error("Approval requests are unavailable.");
  }

  return data;
}

export async function submitApproval(
  approvalId: string,
  reviewComment?: string
) {
  const { data, error } = await approveAction({
    params: {
      path: {
        approval_id: approvalId,
      },
    },
    body: {
      review_comment: reviewComment ?? null,
    },
  });

  if (error) {
    throw new Error("Unable to approve the requested action.");
  }

  return data;
}

export async function submitRejection(
  approvalId: string,
  reviewComment: string
) {
  const comment = reviewComment.trim();

  if (!comment) {
    throw new Error("A rejection reason is required.");
  }

  const { data, error } = await rejectAction({
    params: {
      path: {
        approval_id: approvalId,
      },
    },
    body: {
      review_comment: comment,
    },
  });

  if (error) {
    throw new Error("Unable to reject the requested action.");
  }

  return data;
}
