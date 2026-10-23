import { useState } from "react";
import { motion } from "motion/react";
import {
  useApprovals,
  useApproveAction,
  useRejectAction,
} from "../hooks/useApprovals";

export default function Approvals() {
  const approvalsQuery = useApprovals();
  const approveMutation = useApproveAction();
  const rejectMutation = useRejectAction();

  const [activeApprovalId, setActiveApprovalId] = useState<string | null>(null);
  const [rejectionId, setRejectionId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const approvals = approvalsQuery.data?.items ?? [];

  const pendingCount = approvals.filter(
    (approval) => approval.approval_status === "PENDING"
  ).length;

  const isMutating =
    approveMutation.isPending || rejectMutation.isPending;

  async function handleApprove(approvalId: string) {
    setActionError(null);
    setActiveApprovalId(approvalId);

    try {
      await approveMutation.mutateAsync({ approvalId });
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
      <motion.div
        initial={{ opacity: 0, y: 25 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mx-auto max-w-6xl"
      >
        <p className="mb-8 text-[10px] font-bold uppercase tracking-[0.35em]">
          Platform / Human Oversight
        </p>

        <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
          Human decisions.
          <br />
          <span className="font-normal italic">Real control.</span>
        </h1>

        <p className="mt-6 max-w-xl text-base leading-relaxed">
          Review sensitive AI agent actions before they are allowed to
          proceed. Keep human oversight at the center of automation.
        </p>

        <div className="mt-16 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.3em]">
              Approval Queue
            </p>
            <h2 className="text-3xl font-black tracking-tight md:text-4xl">
              Awaiting your review.
            </h2>
          </div>

          <span className="rounded-full bg-[#F5F87A] px-5 py-3 text-xs font-bold">
            {pendingCount} Pending
          </span>
        </div>

        {approvalsQuery.isLoading && (
          <p className="mt-8 text-sm">Loading approval requests...</p>
        )}

        {approvalsQuery.isError && (
          <div className="mt-8 rounded-[24px] bg-[#FFF8F2] p-6">
            <p className="text-sm font-bold">
              Unable to load approval requests.
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
              No approval requests are available.
            </p>
          )}

        <div className="mt-8 space-y-4">
          {approvals.map((approval, index) => {
            const action = approval.action_summary;
            const status = approval.approval_status;
            const isPending = status === "PENDING";
            const isBusy =
              isMutating && activeApprovalId === approval.approval_id;

            return (
              <motion.article
                key={approval.approval_id}
                initial={{ opacity: 0, y: 25 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.12, duration: 0.5 }}
                whileHover={{ y: -3 }}
                className="rounded-[24px] border border-black/10 bg-[#FFF8F2] p-6 md:p-8"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-[10px] font-bold uppercase tracking-[0.25em]">
                    {approval.approval_id.slice(0, 8)} /{" "}
                    {action?.agent_name ?? "Unknown Agent"}
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
                    {status}
                  </span>
                </div>

                <h3 className="mt-8 text-2xl font-black tracking-tight md:text-3xl">
                  {action?.action_type.replaceAll("_", " ") ??
                    "Approval request"}
                </h3>

                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#555555]">
                  Requested tool:{" "}
                  {action?.requested_tool_name ?? "Not available"}
                </p>

                {approval.review_comment && (
                  <p className="mt-3 text-sm text-[#555555]">
                    Review comment: {approval.review_comment}
                  </p>
                )}

                <div className="mt-8 flex flex-wrap gap-3">
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
                </div>

                {rejectionId === approval.approval_id && isPending && (
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
              </motion.article>
            );
          })}
        </div>

        <p className="mt-8 text-xs text-[#555555]">
          Approval decisions are submitted through the platform API.
          Development mock mode simulates these operations without changing
          real backend records.
        </p>
      </motion.div>
    </div>
  );
}
