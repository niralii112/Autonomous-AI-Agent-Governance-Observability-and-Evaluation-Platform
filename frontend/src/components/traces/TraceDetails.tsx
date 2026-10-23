import { useState } from "react";
import { Link } from "react-router-dom";
import type { components } from "../../types/generated/api";
import StatusBadge from "../common/StatusBadge";
import SpanTree from "./SpanTree";

type TraceDetail = components["schemas"]["TraceDetailResponse"];

type TraceDetailsProps = {
  trace: TraceDetail;
  actionId?: string | null;
  agentName?: string | null;
};

export default function TraceDetails({
  trace,
  actionId,
  agentName,
}: TraceDetailsProps) {
  const [showJson, setShowJson] = useState(false);

  const durationFormatted =
    trace.duration_ms >= 1000
      ? `${(trace.duration_ms / 1000).toFixed(2)}s`
      : `${trace.duration_ms.toFixed(1)}ms`;

  return (
    <div className="space-y-8">
      {/* Overview Metadata Card */}
      <div className="rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#111111]/10 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-black uppercase tracking-[0.25em] text-[#555555]">
                Trace Telemetry Record
              </span>
              <StatusBadge
                status={trace.error_count > 0 ? "ERROR" : "OK"}
                size="sm"
              />
            </div>
            <h2 className="mt-2 text-2xl md:text-3xl font-black font-mono tracking-tight break-all">
              {trace.trace_id}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowJson(!showJson)}
              className="cursor-pointer rounded-full bg-[#111111]/5 px-4 py-2 text-xs font-bold text-[#111111] hover:bg-[#FFE3CE] transition"
            >
              {showJson ? "View Waterfall" : "View Raw JSON"}
            </button>

            {actionId && (
              <Link
                to={`/actions/${actionId}`}
                className="cursor-pointer rounded-full bg-[#F5F87A] px-5 py-2 text-xs font-black uppercase tracking-wider text-[#111111] hover:bg-[#111111] hover:text-[#F5F87A] transition"
              >
                Inspect Linked Action →
              </Link>
            )}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
              Start Time
            </span>
            <p className="mt-1 font-mono text-sm font-semibold text-[#111111]">
              {new Date(trace.start_time).toLocaleString()}
            </p>
          </div>

          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
              Total Latency
            </span>
            <p className="mt-1 font-mono text-sm font-bold text-[#111111]">
              {durationFormatted}
            </p>
          </div>

          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
              Total Spans
            </span>
            <p className="mt-1 font-mono text-sm font-bold text-[#111111]">
              {trace.span_count} spans
            </p>
          </div>

          <div className="rounded-2xl bg-white/60 p-4 border border-[#111111]/5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
              Execution Agent
            </span>
            <p className="mt-1 text-sm font-bold text-[#111111] truncate">
              {agentName || "System / Unspecified"}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content Area: Waterfall vs JSON */}
      {showJson ? (
        <div className="rounded-3xl border border-[#111111]/15 bg-[#111111] p-6 text-[#F5F87A] shadow-inner overflow-x-auto">
          <div className="flex justify-between items-center pb-3 border-b border-white/10 mb-4 text-xs font-mono">
            <span className="text-white">TraceDetailResponse JSON</span>
            <button
              type="button"
              onClick={() => void navigator.clipboard.writeText(JSON.stringify(trace, null, 2))}
              className="text-[#F5F87A] hover:underline cursor-pointer"
            >
              Copy JSON
            </button>
          </div>
          <pre className="font-mono text-xs leading-relaxed">
            {JSON.stringify(trace, null, 2)}
          </pre>
        </div>
      ) : (
        <div className="rounded-3xl border border-[#111111]/15 bg-white/80 p-8 shadow-xs">
          <div className="mb-6 flex items-center justify-between">
            <h3 className="text-xl font-black tracking-tight text-[#111111]">
              Span Execution Waterfall
            </h3>
            <span className="text-xs text-[#555555]">
              Click on any span to expand sanitized attributes
            </span>
          </div>

          <SpanTree
            spans={trace.spans}
            totalDurationMs={trace.duration_ms}
            rootStartTime={trace.start_time}
          />
        </div>
      )}
    </div>
  );
}
