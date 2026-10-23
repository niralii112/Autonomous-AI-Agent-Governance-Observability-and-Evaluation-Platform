import { useTrace } from "../../hooks/useTraces";
import LoadingState from "../common/LoadingState";
import ErrorState from "../common/ErrorState";
import StatusBadge from "../common/StatusBadge";

type TraceTimelineProps = {
  traceId: string;
};

export default function TraceTimeline({ traceId }: TraceTimelineProps) {
  const { data, isLoading, isError, refetch } = useTrace(traceId);

  if (isLoading) {
    return <LoadingState message="Loading execution timeline..." lines={2} />;
  }

  if (isError) {
    return (
      <ErrorState
        title="Trace Timeline Unavailable"
        message="Could not load span breakdown for this trace."
        onRetry={() => void refetch()}
      />
    );
  }

  if (!data || data.spans.length === 0) {
    return <p className="text-sm text-[#555555]">No spans available in this trace.</p>;
  }

  return (
    <ol className="relative border-l-2 border-[#111111] pl-6 space-y-6 my-4">
      {data.spans.map((span) => (
        <li key={span.span_id} className="relative group">
          {/* Timeline node marker */}
          <span className="absolute -left-[31px] top-1 h-3.5 w-3.5 rounded-full border-2 border-[#111111] bg-[#F5F87A]" />

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <h4 className="font-bold text-sm text-[#111111]">{span.span_name}</h4>
              <StatusBadge status={span.status} size="sm" />
            </div>

            <span className="font-mono text-xs text-[#555555]">
              {span.duration_ms >= 1000
                ? `${(span.duration_ms / 1000).toFixed(2)}s`
                : `${span.duration_ms.toFixed(1)}ms`}
            </span>
          </div>

          <p className="mt-1 text-xs text-[#555555]">
            Service: <span className="font-semibold text-[#111111]">{span.service_name}</span> • Span ID:{" "}
            <span className="font-mono text-[10px] text-[#777777]">{span.span_id}</span>
            {span.parent_span_id ? ` (parent: ${span.parent_span_id})` : " (root span)"}
          </p>
        </li>
      ))}
    </ol>
  );
}
