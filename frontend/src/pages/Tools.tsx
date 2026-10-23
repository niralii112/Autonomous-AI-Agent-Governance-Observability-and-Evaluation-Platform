import { useState } from "react";
import { motion } from "motion/react";
import { useTools, useCreateTool } from "../hooks/useTools";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";
import type { components } from "../types/generated/api";

type ToolSensitivity = components["schemas"]["ToolSensitivity"];
type ActionType = components["schemas"]["ActionType"];

export default function Tools() {
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form state
  const [toolName, setToolName] = useState("");
  const [description, setDescription] = useState("");
  const [sensitivity, setSensitivity] = useState<ToolSensitivity>("READ_ONLY");
  const [actionType, setActionType] = useState<ActionType>("FINANCE_GET_REPORT");

  const { data: toolsData, isLoading, isError, refetch } = useTools(page, 20);
  const createMutation = useCreateTool();

  const tools = toolsData?.items ?? [];
  const totalPages = toolsData?.total_pages ?? 1;

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!toolName.trim()) return;

    createMutation.mutate(
      {
        tool_name: toolName.trim(),
        description: description.trim(),
        tool_sensitivity: sensitivity,
        supported_action_type: actionType,
      },
      {
        onSuccess: () => {
          setShowCreateModal(false);
          setToolName("");
          setDescription("");
        },
      }
    );
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
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.35em] text-[#555555]">
                Platform / Capability Management
              </p>
              <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
                Tool Registry.
                <br />
                <span className="font-normal italic">Governed integrations.</span>
              </h1>
            </div>

            <button
              type="button"
              onClick={() => setShowCreateModal(true)}
              className="cursor-pointer rounded-full bg-[#111111] px-6 py-3 text-xs font-black uppercase tracking-wider text-[#F5F87A] hover:bg-[#1A1A1A] transition"
            >
              + Register New Tool
            </button>
          </div>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Manage executable capabilities and APIs exposed to autonomous agents.
            Define sensitivity tiers, supported action schemas, and activation states.
          </p>
        </motion.header>

        {/* Create Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-lg rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-2xl">
              <h3 className="text-2xl font-black tracking-tight">Register New Tool</h3>
              <p className="text-xs text-[#555555] mt-1 mb-6">
                Add an executable capability to the governance boundary.
              </p>

              <form onSubmit={handleCreate} className="space-y-4 text-xs font-semibold">
                <div>
                  <label className="block uppercase tracking-wider text-[#777777] mb-1">
                    Tool Identifier
                  </label>
                  <input
                    type="text"
                    required
                    value={toolName}
                    onChange={(e) => setToolName(e.target.value)}
                    placeholder="e.g. finance_report_generator"
                    className="w-full rounded-xl border border-[#111111]/20 bg-white px-3.5 py-2.5 text-sm font-medium focus:border-[#111111] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block uppercase tracking-wider text-[#777777] mb-1">
                    Description
                  </label>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe tool purpose and guardrails..."
                    className="w-full rounded-xl border border-[#111111]/20 bg-white px-3.5 py-2 text-sm font-medium focus:border-[#111111] focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block uppercase tracking-wider text-[#777777] mb-1">
                      Tool Sensitivity
                    </label>
                    <select
                      value={sensitivity}
                      onChange={(e) => setSensitivity(e.target.value as ToolSensitivity)}
                      className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-bold cursor-pointer"
                    >
                      <option value="READ_ONLY">READ_ONLY</option>
                      <option value="SENSITIVE_READ">SENSITIVE_READ</option>
                      <option value="WRITE">WRITE</option>
                      <option value="PRIVILEGED">PRIVILEGED</option>
                    </select>
                  </div>

                  <div>
                    <label className="block uppercase tracking-wider text-[#777777] mb-1">
                      Supported Action Type
                    </label>
                    <select
                      value={actionType}
                      onChange={(e) => setActionType(e.target.value as ActionType)}
                      className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-bold cursor-pointer"
                    >
                      <option value="FINANCE_GET_REPORT">FINANCE_GET_REPORT</option>
                      <option value="FINANCE_GENERATE_SUMMARY">FINANCE_GENERATE_SUMMARY</option>
                      <option value="FINANCE_PROPOSE_PAYMENT">FINANCE_PROPOSE_PAYMENT</option>
                      <option value="SUPPORT_LOOKUP_CUSTOMER">SUPPORT_LOOKUP_CUSTOMER</option>
                      <option value="SUPPORT_PROPOSE_REFUND">SUPPORT_PROPOSE_REFUND</option>
                      <option value="SUPPORT_SEND_EMAIL">SUPPORT_SEND_EMAIL</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-6 border-t border-[#111111]/10">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="cursor-pointer rounded-full bg-[#111111]/5 px-5 py-2 text-xs font-bold hover:bg-[#FFE3CE]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="cursor-pointer rounded-full bg-[#111111] px-6 py-2 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A]"
                  >
                    {createMutation.isPending ? "Registering..." : "Register Tool"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Tools List */}
        {isLoading ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <LoadingState message="Fetching registered tool specifications..." />
          </div>
        ) : isError ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <ErrorState
              title="Failed to Load Tools"
              message="Could not load tools from the governance platform."
              onRetry={() => void refetch()}
            />
          </div>
        ) : tools.length === 0 ? (
          <EmptyState
            title="No Tools Registered"
            description="The tool registry is currently empty. Register your first governed tool above."
          />
        ) : (
          <div className="space-y-4">
            {tools.map((tool) => {
              return (
                <div
                  key={tool.tool_id}
                  className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-6 shadow-xs transition hover:border-[#111111]/30"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[11px] font-bold uppercase text-[#555555]">
                          {tool.supported_action_type}
                        </span>
                        <span className="text-[#888888]">•</span>
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase ${
                            tool.tool_sensitivity === "PRIVILEGED"
                              ? "bg-red-600 text-white"
                              : tool.tool_sensitivity === "WRITE"
                                ? "bg-[#FFB5A7] text-[#601407]"
                                : tool.tool_sensitivity === "SENSITIVE_READ"
                                  ? "bg-[#F5F87A] text-[#111111]"
                                  : "bg-[#B8F5CE] text-[#0A4D27]"
                          }`}
                        >
                          {tool.tool_sensitivity}
                        </span>
                      </div>

                      <h3 className="mt-2 text-2xl font-black text-[#111111]">
                        {tool.tool_name}
                      </h3>

                      <p className="mt-1 text-xs text-[#555555] max-w-2xl">
                        {tool.description || "No tool description provided."}
                      </p>

                      <p className="mt-2 font-mono text-[10px] text-[#777777]">
                        Tool ID: {tool.tool_id} • Registered: {new Date(tool.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusBadge
                        status={tool.tool_status}
                        size="md"
                      />
                    </div>
                  </div>
                </div>
              );
            })}

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
                <span className="text-xs font-bold">
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
