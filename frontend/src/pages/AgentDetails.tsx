import { useParams, Link } from "react-router-dom";
import { useAgent } from "../hooks/useAgents";
import { useAgentPerformance } from "../hooks/useEvaluations";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";

export default function AgentDetails() {
  const { agentId } = useParams<{ agentId: string }>();

  const { data: agent, isLoading, isError, refetch } = useAgent(agentId || "");
  const { data: performance, isLoading: perfLoading } = useAgentPerformance(agentId || "");

  const metrics = performance?.metrics;

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl p-8">
        <LoadingState message="Loading agent profile & governance parameters..." />
      </div>
    );
  }

  if (isError || !agent) {
    return (
      <div className="mx-auto max-w-7xl p-8 space-y-6">
        <Link to="/agents" className="text-xs font-bold uppercase tracking-wider text-[#111111] hover:underline">
          ← Back to Agents
        </Link>
        <ErrorState
          title="Agent Not Found"
          message={`Unable to find agent ${agentId || "specified"}.`}
          errorCode="RESOURCE_NOT_FOUND"
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-6 md:p-12 text-[#111111] space-y-8">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between border-b border-[#111111]/10 pb-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
          <Link to="/agents" className="text-[#555555] hover:text-[#111111]">
            Agents
          </Link>
          <span className="text-[#999999]">/</span>
          <span className="font-mono text-[#111111]">{agent.agent_name}</span>
        </div>

        <Link
          to="/agents"
          className="rounded-full bg-[#111111]/5 px-4 py-1.5 text-xs font-bold text-[#111111] hover:bg-[#FFE3CE] transition"
        >
          ← All Agents
        </Link>
      </div>

      {/* Hero Profile Card */}
      <div className="rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#111111]/10 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black uppercase tracking-[0.25em] text-[#555555]">
                Governed Agent Spec
              </span>
              <StatusBadge status={agent.agent_status} size="sm" />
              <span className="rounded-full bg-[#F5F87A] px-3 py-0.5 text-[10px] font-bold uppercase">
                Tier {agent.trust_tier} Trust
              </span>
            </div>
            <h2 className="mt-2 text-3xl font-black tracking-tight">{agent.agent_name}</h2>
            <p className="mt-1 text-sm text-[#555555] max-w-2xl">{agent.description}</p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              to={`/actions?agent_id=${agent.agent_id}`}
              className="rounded-full bg-[#111111] px-5 py-2.5 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A] transition"
            >
              View Agent Actions →
            </Link>
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Category</span>
            <p className="mt-1 font-bold text-sm text-[#111111]">{agent.agent_category}</p>
          </div>
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Agent ID</span>
            <p className="mt-1 font-mono text-[11px] text-[#111111] truncate">{agent.agent_id}</p>
          </div>
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Registered</span>
            <p className="mt-1 font-mono text-xs text-[#111111]">{new Date(agent.created_at).toLocaleDateString()}</p>
          </div>
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Last Update</span>
            <p className="mt-1 font-mono text-xs text-[#111111]">{new Date(agent.updated_at).toLocaleDateString()}</p>
          </div>
        </div>
      </div>

      {/* Performance & Evaluation Statistics */}
      <div className="rounded-3xl border border-[#111111]/15 bg-white/80 p-8 shadow-xs space-y-6">
        <h3 className="text-xl font-black tracking-tight text-[#111111]">
          Agent Evaluation & Governance Performance
        </h3>

        {perfLoading ? (
          <LoadingState message="Deriving evaluation metrics..." lines={2} />
        ) : metrics ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="rounded-2xl bg-[#FFF8F2] p-5 border border-[#111111]/10">
              <span className="text-xs font-bold text-[#777777]">Reliability Score</span>
              <p className="mt-2 text-3xl font-black text-[#111111]">
                {((metrics.agent_reliability_score ?? 0) * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-2xl bg-[#FFF8F2] p-5 border border-[#111111]/10">
              <span className="text-xs font-bold text-[#777777]">Allowed Actions</span>
              <p className="mt-2 text-3xl font-black text-emerald-600">
                {metrics.allow_count ?? 0}
              </p>
            </div>
            <div className="rounded-2xl bg-[#FFF8F2] p-5 border border-[#111111]/10">
              <span className="text-xs font-bold text-[#777777]">Total Actions</span>
              <p className="mt-2 text-3xl font-black text-[#111111]">
                {metrics.total_actions ?? 0}
              </p>
            </div>
            <div className="rounded-2xl bg-[#FFF8F2] p-5 border border-[#111111]/10">
              <span className="text-xs font-bold text-[#777777]">Blocked Actions</span>
              <p className="mt-2 text-3xl font-black text-red-600">
                {metrics.block_count ?? 0}
              </p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-[#777777]">No historical evaluation metrics recorded for this agent yet.</p>
        )}
      </div>
    </div>
  );
}
