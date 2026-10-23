import { useState, useMemo } from "react";
import { motion } from "motion/react";
import { useEvaluations, useRunEvaluation } from "../hooks/useEvaluations";
import { useAgents } from "../hooks/useAgents";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";

export default function Evaluations() {
  const [selectedAgent, setSelectedAgent] = useState("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showRunModal, setShowRunModal] = useState(false);

  // Run evaluation form state
  const [targetAgentId, setTargetAgentId] = useState("");
  const [evalType, setEvalType] = useState<"PRODUCTION_RECORDS" | "LABELLED_DATASET">("PRODUCTION_RECORDS");

  const { data: evalData, isLoading, isError, refetch } = useEvaluations({
    agent_id: selectedAgent !== "ALL" ? selectedAgent : undefined,
  });

  const { data: agentData } = useAgents();
  const runMutation = useRunEvaluation();

  const agents = agentData?.items ?? [];
  const agentNames = useMemo(
    () => new Map(agents.map((a) => [a.agent_id, a.agent_name])),
    [agents]
  );

  const evaluations = evalData?.items ?? [];

  const handleRunEvaluation = (e: React.FormEvent) => {
    e.preventDefault();
    runMutation.mutate(
      {
        evaluation_type: evalType,
        agent_id: targetAgentId || undefined,
        window_hours: 24,
        dataset_id: "risk_eval_v1",
      },
      {
        onSuccess: () => {
          setShowRunModal(false);
        },
      }
    );
  };

  // Derive dynamic metrics
  const totalCount = evaluations.length;
  const avgSampleSize =
    totalCount > 0
      ? (evaluations.reduce((acc, ev) => acc + (ev.sample_size ?? 0), 0) / totalCount).toFixed(0)
      : "0";

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
                Platform / Evaluation & Benchmarking
              </p>
              <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
                Evaluation Analytics.
                <br />
                <span className="font-normal italic">Rigorous verification.</span>
              </h1>
            </div>

            <button
              type="button"
              onClick={() => {
                if (agents.length > 0 && !targetAgentId) {
                  setTargetAgentId(agents[0].agent_id);
                }
                setShowRunModal(true);
              }}
              className="cursor-pointer rounded-full bg-[#111111] px-6 py-3 text-xs font-black uppercase tracking-wider text-[#F5F87A] hover:bg-[#1A1A1A] transition"
            >
              + Trigger Evaluation Run
            </button>
          </div>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Continuous assessment of autonomous agents against policy compliance,
            factual precision, risk boundaries, and safety test suites.
          </p>
        </motion.header>

        {/* Dynamic Metric Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-3xl bg-[#111111] p-6 text-white shadow-md">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#A0A0A0]">
              Total Evaluations
            </span>
            <p className="mt-2 text-5xl font-black text-[#F5F87A]">
              {String(totalCount).padStart(2, "0")}
            </p>
            <p className="mt-1 text-xs text-[#888888]">Stored evaluation runs</p>
          </div>

          <div className="rounded-3xl bg-[#F5F87A] p-6 text-[#111111] shadow-md">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#555555]">
              Average Sample Size
            </span>
            <p className="mt-2 text-5xl font-black text-[#111111]">
              {avgSampleSize}
            </p>
            <p className="mt-1 text-xs text-[#555555]">Actions analyzed per run</p>
          </div>

          <div className="rounded-3xl bg-[#FFF8F2] p-6 border border-[#111111]/10 text-[#111111] shadow-xs">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
              Active Tested Agents
            </span>
            <p className="mt-2 text-5xl font-black text-[#111111]">
              {String(agents.length).padStart(2, "0")}
            </p>
            <p className="mt-1 text-xs text-[#555555]">Registered in governance</p>
          </div>
        </div>

        {/* Trigger Run Modal */}
        {showRunModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-lg rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-2xl">
              <h3 className="text-2xl font-black tracking-tight">Trigger Evaluation Run</h3>
              <p className="text-xs text-[#555555] mt-1 mb-6">
                Initiate automated policy and accuracy verification.
              </p>

              <form onSubmit={handleRunEvaluation} className="space-y-4 text-xs font-semibold">
                <div>
                  <label className="block uppercase tracking-wider text-[#777777] mb-1">
                    Target Agent
                  </label>
                  <select
                    value={targetAgentId}
                    onChange={(e) => setTargetAgentId(e.target.value)}
                    className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-bold"
                  >
                    <option value="">All / Platform Wide</option>
                    {agents.map((a) => (
                      <option key={a.agent_id} value={a.agent_id}>
                        {a.agent_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block uppercase tracking-wider text-[#777777] mb-1">
                    Evaluation Benchmark Type
                  </label>
                  <select
                    value={evalType}
                    onChange={(e) => setEvalType(e.target.value as "PRODUCTION_RECORDS" | "LABELLED_DATASET")}
                    className="w-full rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-bold"
                  >
                    <option value="PRODUCTION_RECORDS">PRODUCTION_RECORDS (Live Telemetry & Actions)</option>
                    <option value="LABELLED_DATASET">LABELLED_DATASET (Ground Truth Benchmark)</option>
                  </select>
                </div>

                <div className="flex items-center justify-end gap-3 pt-6 border-t border-[#111111]/10">
                  <button
                    type="button"
                    onClick={() => setShowRunModal(false)}
                    className="cursor-pointer rounded-full bg-[#111111]/5 px-5 py-2 text-xs font-bold hover:bg-[#FFE3CE]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={runMutation.isPending}
                    className="cursor-pointer rounded-full bg-[#111111] px-6 py-2 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A]"
                  >
                    {runMutation.isPending ? "Starting Run..." : "Run Evaluation"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-[#111111]/10 bg-[#FFF8F2] p-5 shadow-xs">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-[#555555]">
              Filter by Agent:
            </span>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
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
        </div>

        {/* Evaluation Cards */}
        {isLoading ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <LoadingState message="Fetching evaluation benchmarking data..." />
          </div>
        ) : isError ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <ErrorState
              title="Failed to Load Evaluations"
              message="Could not retrieve evaluation records from the evaluation backend."
              onRetry={() => void refetch()}
            />
          </div>
        ) : evaluations.length === 0 ? (
          <EmptyState
            title="No Evaluation Records"
            description="No evaluation benchmarks have been recorded yet. Click 'Trigger Evaluation Run' to run your first evaluation."
          />
        ) : (
          <div className="space-y-4">
            {evaluations.map((ev) => {
              const isExpanded = expandedId === ev.evaluation_id;
              const agentName = ev.agent_id
                ? agentNames.get(ev.agent_id) ?? ev.agent_id
                : "Platform Wide";

              const prod = ev.production_metrics;
              const labelled = ev.labelled_metrics;

              return (
                <div
                  key={ev.evaluation_id}
                  className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-6 shadow-xs transition hover:border-[#111111]/30 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : ev.evaluation_id)}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="rounded-full bg-[#111111] px-3 py-0.5 text-[10px] font-black uppercase text-[#F5F87A]">
                          {ev.evaluation_type}
                        </span>
                        <span className="text-[#888888]">•</span>
                        <span className="text-xs font-bold text-[#111111]">{agentName}</span>
                        <span className="text-[#888888]">•</span>
                        <span className="font-mono text-xs text-[#777777]">
                          {new Date(ev.created_at).toLocaleString()}
                        </span>
                      </div>

                      <h3 className="mt-2 text-2xl font-black text-[#111111]">
                        {ev.evaluation_type === "PRODUCTION_RECORDS"
                          ? "Production Policy & Execution Compliance"
                          : "Ground-Truth Factual Accuracy Benchmark"}
                      </h3>

                      <p className="mt-1 text-xs text-[#555555]">
                        Sample Size: <span className="font-bold text-[#111111]">{ev.sample_size} actions</span>
                        {ev.model_version && ` • Model Version: ${ev.model_version}`}
                      </p>
                    </div>

                    <div className="flex items-center gap-4">
                      {labelled && (
                        <div className="text-right">
                          <span className="text-[10px] font-bold uppercase text-[#777777]">Accuracy</span>
                          <p className="font-mono text-2xl font-black text-[#111111]">
                            {((labelled.accuracy ?? 0) * 100).toFixed(1)}%
                          </p>
                        </div>
                      )}

                      {prod && (
                        <div className="text-right">
                          <span className="text-[10px] font-bold uppercase text-[#777777]">Violation Rate</span>
                          <p className="font-mono text-2xl font-black text-red-600">
                            {((prod.policy_violation_rate ?? 0) * 100).toFixed(1)}%
                          </p>
                        </div>
                      )}

                      <span className="text-xs font-bold text-indigo-700 hover:underline">
                        {isExpanded ? "Hide Details ▲" : "Inspect Metrics ▼"}
                      </span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-4 border-t border-[#111111]/10 pt-4">
                      <span className="text-[10px] font-black uppercase tracking-wider text-[#555555] block mb-2">
                        Benchmark Breakdown & Metrics
                      </span>
                      <pre className="overflow-x-auto rounded-2xl bg-[#111111] p-4 font-mono text-xs text-[#F5F87A]">
                        {JSON.stringify(
                          {
                            evaluation_id: ev.evaluation_id,
                            evaluation_type: ev.evaluation_type,
                            production_metrics: ev.production_metrics,
                            labelled_metrics: ev.labelled_metrics,
                            window_start: ev.window_start,
                            window_end: ev.window_end,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
