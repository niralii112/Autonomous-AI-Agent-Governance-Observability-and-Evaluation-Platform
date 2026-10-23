import { useParams, Link } from "react-router-dom";
import { useTrace, useTraces } from "../hooks/useTraces";
import { useAgents } from "../hooks/useAgents";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import TraceDetails from "../components/traces/TraceDetails";

export default function TraceDetailsPage() {
  const { traceId } = useParams<{ traceId: string }>();

  const { data: trace, isLoading, isError, refetch } = useTrace(traceId || "");
  const { data: traceListData } = useTraces({ windowMinutes: 1440 });
  const { data: agentData } = useAgents();

  // Find summary to resolve agent_id and action_id if available
  const matchingSummary = traceListData?.items?.find((t) => t.trace_id === traceId);
  const matchingAgent = agentData?.items?.find((a) => a.agent_id === matchingSummary?.agent_id);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl p-8">
        <LoadingState message="Fetching trace spans from telemetry backend..." />
      </div>
    );
  }

  if (isError || !trace) {
    return (
      <div className="mx-auto max-w-7xl p-8 space-y-6">
        <Link
          to="/traces"
          className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#111111] hover:underline"
        >
          ← Back to Trace Explorer
        </Link>
        <ErrorState
          title="Trace Not Found or Telemetry Unavailable"
          message={`Unable to retrieve trace ${traceId || "specified"}. It may have expired or telemetry services are temporarily unreachable.`}
          errorCode="TRACE_NOT_FOUND"
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-6 md:p-12 text-[#111111] space-y-8">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between border-b border-[#111111]/10 pb-4">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
          <Link to="/traces" className="text-[#555555] hover:text-[#111111]">
            Trace Explorer
          </Link>
          <span className="text-[#999999]">/</span>
          <span className="text-[#111111] font-mono truncate max-w-xs">{traceId}</span>
        </div>

        <Link
          to="/traces"
          className="rounded-full bg-[#111111]/5 px-4 py-1.5 text-xs font-bold text-[#111111] hover:bg-[#FFE3CE] transition"
        >
          ← All Traces
        </Link>
      </div>

      <TraceDetails
        trace={trace}
        actionId={matchingSummary?.action_id}
        agentName={matchingAgent?.agent_name}
      />
    </div>
  );
}
