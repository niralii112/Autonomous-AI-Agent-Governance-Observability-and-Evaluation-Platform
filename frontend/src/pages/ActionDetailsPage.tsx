import { useParams, Link } from "react-router-dom";
import { useAction, useRetryAction } from "../hooks/useActions";
import { useTracesByAction } from "../hooks/useTraces";
import { useAgents } from "../hooks/useAgents";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";

export default function ActionDetailsPage() {
  const { actionId } = useParams<{ actionId: string }>();

  const { data: detail, isLoading, isError, refetch } = useAction(actionId || "");
  const { data: tracesData, isLoading: tracesLoading } = useTracesByAction(actionId || "");
  const { data: agentData } = useAgents();
  const retryMutation = useRetryAction();

  const action = detail?.action;
  const executions = detail?.executions ?? [];
  const decisions = detail?.governance_decisions ?? [];
  const latestExecution = executions[executions.length - 1];

  const agent = agentData?.items?.find((a) => a.agent_id === action?.agent_id);
  const linkedTraces = tracesData?.traces ?? [];

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl p-8">
        <LoadingState message="Fetching action details..." />
      </div>
    );
  }

  if (isError || !action) {
    return (
      <div className="mx-auto max-w-7xl p-8 space-y-6">
        <Link to="/actions" className="text-xs font-bold uppercase tracking-wider text-[#111111] hover:underline">
          ← Back to Actions
        </Link>
        <ErrorState
          title="Action Not Found"
          message={`Unable to find action ${actionId || "specified"}.`}
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
          <Link to="/actions" className="text-[#555555] hover:text-[#111111]">
            Actions
          </Link>
          <span className="text-[#999999]">/</span>
          <span className="font-mono text-[#111111]">{actionId}</span>
        </div>

        <Link
          to="/actions"
          className="rounded-full bg-[#111111]/5 px-4 py-1.5 text-xs font-bold text-[#111111] hover:bg-[#FFE3CE] transition"
        >
          ← All Actions
        </Link>
      </div>

      {/* Header Info Card */}
      <div className="rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#111111]/10 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black uppercase tracking-[0.25em] text-[#555555]">
                Governed Action
              </span>
              <StatusBadge
                status={latestExecution?.execution_status || decisions[0]?.final_decision || "PENDING"}
                size="sm"
              />
            </div>
            <h2 className="mt-2 text-3xl font-black tracking-tight">{action.action_type}</h2>
            <p className="mt-1 font-mono text-xs text-[#666666]">Action ID: {action.action_id}</p>
          </div>

          <div className="flex items-center gap-3">
            {latestExecution?.execution_status === "FAILED" && (
              <button
                type="button"
                onClick={() => retryMutation.mutate(action.action_id)}
                disabled={retryMutation.isPending}
                className="rounded-full bg-[#FFB5A7] px-6 py-2.5 text-xs font-bold text-[#601407] hover:bg-red-300 transition cursor-pointer"
              >
                {retryMutation.isPending ? "Retrying..." : "Retry Action"}
              </button>
            )}
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Agent</span>
            <p className="mt-1 font-bold text-sm text-[#111111]">{agent?.agent_name || action.agent_id}</p>
          </div>
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Tool Invocation</span>
            <p className="mt-1 font-bold text-sm text-[#111111]">{action.requested_tool_name || "Direct execution"}</p>
          </div>
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Created At</span>
            <p className="mt-1 font-mono text-xs text-[#111111]">{new Date(action.created_at).toLocaleString()}</p>
          </div>
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">Latest Execution</span>
            <p className="mt-1 font-bold text-sm text-[#111111]">{latestExecution?.execution_status || "None"}</p>
          </div>
        </div>
      </div>

      {/* Action Payload Details */}
      <div className="rounded-3xl border border-[#111111]/15 bg-white/80 p-8 shadow-xs">
        <h3 className="text-xl font-black tracking-tight text-[#111111] mb-4">
          Action Payload & Parameters
        </h3>
        <pre className="overflow-x-auto rounded-2xl bg-[#111111] p-6 font-mono text-xs text-[#F5F87A]">
          {JSON.stringify(action.action_payload, null, 2)}
        </pre>
      </div>

      {/* Linked Telemetry Traces (TRC-02) */}
      <div className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-8 shadow-xs space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#555555]">
              Observability Correlation
            </span>
            <h3 className="text-2xl font-black tracking-tight text-[#111111]">
              Linked Execution Traces
            </h3>
          </div>
          <span className="rounded-full bg-[#F5F87A] px-4 py-1 text-xs font-bold">
            {linkedTraces.length} Traces Linked
          </span>
        </div>

        {tracesLoading ? (
          <LoadingState message="Looking up correlated OpenTelemetry traces..." lines={2} />
        ) : linkedTraces.length === 0 ? (
          <div className="py-8 text-center text-sm text-[#666666]">
            No traces recorded for this action yet. Telemetry will correlate when the agent executes.
          </div>
        ) : (
          <div className="space-y-3">
            {linkedTraces.map((trace) => (
              <div
                key={trace.trace_id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-[#111111]/10 bg-white p-5 shadow-xs"
              >
                <div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold text-[#111111]">{trace.trace_id}</span>
                    <StatusBadge status={trace.error_count > 0 ? "ERROR" : "OK"} size="sm" />
                  </div>
                  <h4 className="mt-1 font-bold text-sm text-[#111111]">{trace.root_span_name}</h4>
                  <p className="text-xs text-[#666666] mt-0.5">
                    {trace.service_name} • {trace.duration_ms.toFixed(1)}ms • {trace.span_count} spans
                  </p>
                </div>

                <Link
                  to={`/traces/${trace.trace_id}`}
                  className="rounded-full bg-[#111111] px-5 py-2 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A] transition text-center"
                >
                  Inspect Span Waterfall →
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
