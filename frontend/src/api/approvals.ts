import {
  listApprovals,
  approveAction,
  rejectAction,
} from "./generated-services";

export async function fetchApprovals() {
  const { data, error } = await listApprovals({
    params: {
      query: {
        page: 1,
        page_size: 25,
        sort_by: "created_at",
        sort_order: "desc",
      },
    },
  });

  if (error) {
    throw new Error("Unable to load approval requests.");
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
