import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { useActions, useRetryAction } from "../hooks/useActions";
import { useAgents } from "../hooks/useAgents";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";

export default function Actions() {
  const [agentFilter, setAgentFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const { data: actionsData, isLoading, isError, refetch } = useActions({
    agent_id: agentFilter !== "ALL" ? agentFilter : undefined,
    page,
    page_size: 20,
  });

  const { data: agentData } = useAgents();
  const retryMutation = useRetryAction();

  const agents = agentData?.items ?? [];
  const actions = actionsData?.items ?? [];
  const totalPages = actionsData?.total_pages ?? 1;

  const handleRetry = (actionId: string) => {
    retryMutation.mutate(actionId);
  };

  return (
    <div className="min-h-screen bg-[#FFE3CE] px-6 py-10 text-[#111111] md:px-12 lg:px-20 space-y-12">
      <div className="mx-auto max-w-6xl space-y-10">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <p className="mb-6 text-[10px] font-bold uppercase tracking-[0.35em] text-[#555555]">
            Platform / Action Execution
          </p>

          <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
            Action History.
            <br />
            <span className="font-normal italic">Audited & Governed.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Track proposed and executed actions across all autonomous agents. Inspect
            risk scores, policy outcomes, and follow directly to telemetry traces.
          </p>
        </motion.header>

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-[#111111]/10 bg-[#FFF8F2] p-5 shadow-xs">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-[#555555]">
              Filter by Agent:
            </span>
            <select
              value={agentFilter}
              onChange={(e) => {
                setAgentFilter(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-semibold text-[#111111] focus:border-[#111111] focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Agents</option>
              {agents.map((agent) => (
                <option key={agent.agent_id} value={agent.agent_id}>
                  {agent.agent_name}
                </option>
              ))}
            </select>
          </div>

          <span className="rounded-full bg-[#F5F87A] px-4 py-1.5 text-xs font-black uppercase text-[#111111]">
            {actionsData?.total_items ?? 0} Actions Total
          </span>
        </div>

        {/* Action List */}
        {isLoading ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <LoadingState message="Fetching action history..." />
          </div>
        ) : isError ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <ErrorState
              title="Failed to Load Actions"
              message="Could not retrieve the action execution log."
              onRetry={() => void refetch()}
            />
          </div>
        ) : actions.length === 0 ? (
          <EmptyState
            title="No Actions Found"
            description="No actions match the selected filter, or no agent actions have been submitted yet."
          />
        ) : (
          <div className="space-y-4">
            {actions.map((act) => {
              const statusDisplay = act.execution_status || act.final_decision || act.approval_status || "PENDING";

              return (
                <div
                  key={act.action_id}
                  className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-6 shadow-xs transition hover:border-[#111111]/30 flex flex-col md:flex-row md:items-center justify-between gap-6"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[11px] font-bold text-[#555555]">
                        {act.action_id.slice(0, 8)}...
                      </span>
                      <span className="text-[#888888]">•</span>
                      <span className="text-xs font-bold text-[#111111]">
                        {act.agent_name}
                      </span>
                      <span className="text-[#888888]">•</span>
                      <span className="font-mono text-xs text-[#777777]">
                        {new Date(act.created_at).toLocaleString()}
                      </span>
                    </div>

                    <h3 className="mt-2 text-xl font-black text-[#111111]">
                      {act.action_type}
                    </h3>

                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[#555555]">
                      <span>
                        Tool: <span className="font-bold text-[#111111]">{act.requested_tool_name || "Direct execution"}</span>
                      </span>
                      {act.risk_score !== null && (
                        <>
                          <span>•</span>
                          <span>Risk: <span className="font-mono font-bold">{act.risk_score.toFixed(2)}</span> ({act.risk_level})</span>
                        </>
                      )}
                      {act.trace_id && (
                        <>
                          <span>•</span>
                          <Link
                            to={`/traces/${act.trace_id}`}
                            className="font-mono text-indigo-700 hover:underline"
                          >
                            Trace: {act.trace_id.slice(0, 8)}...
                          </Link>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-wrap">
                    <StatusBadge status={statusDisplay} size="md" />

                    <Link
                      to={`/actions/${act.action_id}`}
                      className="rounded-full bg-[#111111] px-4 py-2 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A] transition"
                    >
                      Action Details →
                    </Link>

                    {act.execution_status === "FAILED" && (
                      <button
                        type="button"
                        onClick={() => handleRetry(act.action_id)}
                        disabled={retryMutation.isPending}
                        className="rounded-full bg-[#FFB5A7] px-4 py-2 text-xs font-bold text-[#601407] hover:bg-red-300 transition cursor-pointer"
                      >
                        {retryMutation.isPending ? "Retrying..." : "Retry"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 pt-6">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-full bg-[#111111] px-5 py-2 text-xs font-bold text-[#F5F87A] disabled:opacity-30 cursor-pointer"
                >
                  ← Previous
                </button>
                <span className="text-xs font-bold text-[#111111]">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-full bg-[#111111] px-5 py-2 text-xs font-bold text-[#F5F87A] disabled:opacity-30 cursor-pointer"
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
