import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { actionLabel, readableLabel } from "../actionLabels";
import {
  useApprovals,
  useApproveAction,
  useRejectAction,
} from "../hooks/useApprovals";

export default function Approvals() {
  const [params] = useSearchParams();
  const pendingOnly = params.get("status") === "pending";
  const requestedPage = Number(params.get("page") ?? 1);
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const { hasRole } = useAuth();
  const canReview = hasRole(["ADMIN", "REVIEWER"]);
  const approvalsQuery = useApprovals(page, pendingOnly ? "PENDING" : undefined);
  const [notice, setNotice] = useState("");
  const pageLink = (number: number) =>
    `/approvals?${pendingOnly ? "status=pending&" : ""}page=${number}`;
  const approveMutation = useApproveAction();
  const rejectMutation = useRejectAction();

  const [activeApprovalId, setActiveApprovalId] = useState<string | null>(null);
  const [rejectionId, setRejectionId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const approvals = approvalsQuery.data?.items ?? [];

  const isMutating =
    approveMutation.isPending || rejectMutation.isPending;

  async function handleApprove(approvalId: string) {
    setActionError(null);
    setNotice("");
    setActiveApprovalId(approvalId);

    try {
      await approveMutation.mutateAsync({ approvalId });
      setNotice("Approval recorded.");
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Approval failed."
      );
    } finally {
      setActiveApprovalId(null);
    }
  }

  async function handleReject(approvalId: string) {
    const comment = rejectionReason.trim();

    if (!comment) {
      setActionError("Please provide a reason for rejection.");
      return;
    }

    setActionError(null);
    setActiveApprovalId(approvalId);

    try {
      await rejectMutation.mutateAsync({
        approvalId,
        reviewComment: comment,
      });

      setNotice("Rejection recorded.");
      setRejectionId(null);
      setRejectionReason("");
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Rejection failed."
      );
    } finally {
      setActiveApprovalId(null);
    }
  }

  return (
    <div className="min-h-screen bg-[#FFE3CE] px-6 py-10 text-[#111111] md:px-12 lg:px-20">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-4xl font-black tracking-tight">Approvals</h1>
        <p className="mt-2">Review requests from your AI assistants.</p>
        {!canReview && <p className="mt-2 text-sm">Your account can view requests. A reviewer or administrator can make decisions.</p>}
        <nav aria-label="Filter approvals" className="mt-6 flex flex-wrap gap-4">
          <Link to="/approvals?status=pending" aria-current={pendingOnly ? "page" : undefined} className={pendingOnly ? "font-bold underline" : "underline"}>Pending requests</Link>
          <Link to="/approvals" aria-current={!pendingOnly ? "page" : undefined} className={!pendingOnly ? "font-bold underline" : "underline"}>All requests</Link>
        </nav>
        {notice && <p role="status" className="mt-4 font-semibold">{notice}</p>}

        {approvalsQuery.isLoading && (
          <p role="status" className="mt-8 text-sm">Loading approval requests…</p>
        )}

        {approvalsQuery.isError && (
          <div className="mt-8 rounded-[24px] bg-[#FFF8F2] p-6">
            <p className="text-sm font-bold">
              {approvalsQuery.error.message}
            </p>
            <button
              type="button"
              onClick={() => void approvalsQuery.refetch()}
              className="mt-4 rounded-full bg-[#111111] px-5 py-3 text-sm font-bold text-white"
            >
              Try again
            </button>
          </div>
        )}

        {actionError && (
          <p
            role="alert"
            className="mt-6 rounded-[16px] bg-red-100 px-5 py-4 text-sm font-semibold text-red-900"
          >
            {actionError}
          </p>
        )}

        {!approvalsQuery.isLoading &&
          !approvalsQuery.isError &&
          approvals.length === 0 && (
            <p className="mt-8 rounded-[24px] bg-[#FFF8F2] p-8 text-sm">
              {page > 1 ? "There are no requests on this page." : pendingOnly ? "No requests are waiting for a decision." : "No approval requests yet."}
            </p>
          )}

        <div className="mt-8 space-y-4">
          {!approvalsQuery.isError && approvals.map((approval) => {
            const action = approval.action_summary;
            const status = approval.approval_status;
            const isPending = status === "PENDING";
            const isBusy =
              isMutating && activeApprovalId === approval.approval_id;

            return (
              <article
                key={approval.approval_id}
                className="rounded-[24px] border border-black/10 bg-[#FFF8F2] p-6 md:p-8"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-[10px] font-bold uppercase tracking-[0.25em]">
                    {action?.agent_name ?? "Assistant name unavailable"}
                  </span>

                  <span
                    className={`rounded-full px-4 py-2 text-xs font-bold ${
                      status === "PENDING"
                        ? "bg-[#F5F87A]"
                        : status === "APPROVED"
                          ? "bg-green-200"
                          : status === "REJECTED"
                            ? "bg-red-200"
                            : "bg-gray-200"
                    }`}
                  >
                    {readableLabel(status)}
                  </span>
                </div>

                <h2 className="mt-4 text-2xl font-black tracking-tight md:text-3xl">
                  {action ? actionLabel(action.action_type) : "Approval request"}
                </h2>

                <p className="mt-3 text-sm">
                  {isPending ? "Review by " : "Review deadline was "}{new Date(approval.expires_at).toLocaleString()}
                </p>
                <Link to={`/actions/${approval.action_id}`} className="mt-3 inline-block font-semibold underline">
                  View action details
                </Link>

                {approval.review_comment && (
                  <p className="mt-3 text-sm text-[#555555]">
                    Review comment: {approval.review_comment}
                  </p>
                )}

                {canReview && isPending && <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!isPending || isMutating}
                    onClick={() => void handleApprove(approval.approval_id)}
                    className="rounded-full bg-[#111111] px-6 py-3 text-sm font-bold text-white transition hover:bg-[#333333] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {isBusy && approveMutation.isPending
                      ? "Approving..."
                      : "Approve"}
                  </button>

                  <button
                    type="button"
                    disabled={!isPending || isMutating}
                    onClick={() => {
                      setActionError(null);
                      setRejectionReason("");
                      setRejectionId(
                        rejectionId === approval.approval_id
                          ? null
                          : approval.approval_id
                      );
                    }}
                    className="rounded-full border border-[#111111] px-6 py-3 text-sm font-bold transition hover:bg-[#111111] hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Reject
                  </button>
                </div>}

                {canReview && rejectionId === approval.approval_id && isPending && (
                  <div className="mt-6 rounded-[20px] border border-black/10 p-5">
                    <label
                      htmlFor={`reason-${approval.approval_id}`}
                      className="text-xs font-bold uppercase tracking-wider"
                    >
                      Reason for rejection
                    </label>

                    <textarea
                      id={`reason-${approval.approval_id}`}
                      value={rejectionReason}
                      onChange={(event) =>
                        setRejectionReason(event.target.value)
                      }
                      rows={3}
                      className="mt-3 w-full rounded-xl border border-black/20 bg-white p-3 text-sm outline-none focus:border-black"
                      placeholder="Explain why this action should be rejected..."
                    />

                    <button
                      type="button"
                      disabled={isMutating || !rejectionReason.trim()}
                      onClick={() => void handleReject(approval.approval_id)}
                      className="mt-3 rounded-full bg-[#111111] px-6 py-3 text-sm font-bold text-white disabled:opacity-40"
                    >
                      {isBusy && rejectMutation.isPending
                        ? "Rejecting..."
                        : "Confirm rejection"}
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>

        {(page > 1 || (approvalsQuery.data?.total_pages ?? 0) > page) && (
          <nav aria-label="Approval pages" className="mt-6 flex gap-4">
            {page > 1 && <Link to={pageLink(page - 1)} className="underline">Previous page</Link>}
            {(approvalsQuery.data?.total_pages ?? 0) > page && <Link to={pageLink(page + 1)} className="underline">Next page</Link>}
          </nav>
        )}
      </div>
    </div>
  );
}
