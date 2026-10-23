import { useState } from "react";
import type { components } from "../../types/generated/api";
import StatusBadge from "../common/StatusBadge";

type Span = components["schemas"]["SpanDetail"];

type SpanTreeProps = {
  spans: Span[];
  totalDurationMs: number;
  rootStartTime: string;
};

export default function SpanTree({
  spans,
  totalDurationMs,
  rootStartTime,
}: SpanTreeProps) {
  const [expandedSpanId, setExpandedSpanId] = useState<string | null>(null);

  const rootTimeMs = new Date(rootStartTime).getTime();

  // Build parent-to-children index
  const childrenMap = new Map<string | null, Span[]>();
  for (const span of spans) {
    const parentId = span.parent_span_id ?? null;
    if (!childrenMap.has(parentId)) {
      childrenMap.set(parentId, []);
    }
    childrenMap.get(parentId)!.push(span);
  }

  // Flatten spans with hierarchy depth
  const orderedList: { span: Span; depth: number }[] = [];
  function traverse(parentId: string | null, depth: number) {
    const children = childrenMap.get(parentId) || [];
    for (const child of children) {
      orderedList.push({ span: child, depth });
      traverse(child.span_id, depth + 1);
    }
  }
  traverse(null, 0);

  // If spans lack null parent, fall back to sequential
  const renderList = orderedList.length > 0 ? orderedList : spans.map((s) => ({ span: s, depth: 0 }));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs font-black uppercase tracking-wider text-[#777777] border-b border-[#111111]/10 pb-3">
        <span>Operation & Hierarchy</span>
        <span>Timeline & Duration</span>
      </div>

      <div className="space-y-3">
        {renderList.map(({ span, depth }) => {
          const spanStartMs = new Date(span.start_time).getTime();
          const startOffsetMs = Math.max(0, spanStartMs - rootTimeMs);
          const offsetPercent = totalDurationMs > 0 ? (startOffsetMs / totalDurationMs) * 100 : 0;
          const widthPercent = totalDurationMs > 0 ? Math.max((span.duration_ms / totalDurationMs) * 100, 2) : 100;
          const isExpanded = expandedSpanId === span.span_id;

          const attrEntries = Object.entries(span.attributes || {});

          return (
            <div
              key={span.span_id}
              className="rounded-2xl border border-[#111111]/10 bg-[#FFF8F2] p-4 transition hover:border-[#111111]/30 shadow-xs"
            >
              <div
                className="cursor-pointer flex flex-wrap items-center justify-between gap-4"
                onClick={() =>
                  setExpandedSpanId(isExpanded ? null : span.span_id)
                }
              >
                <div
                  className="flex items-center gap-3 min-w-[260px] flex-1"
                  style={{ paddingLeft: `${depth * 20}px` }}
                >
                  <span className="text-xs font-mono text-[#777777]">
                    {depth > 0 ? "↳" : "•"}
                  </span>

                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-[#111111]">
                        {span.span_name}
                      </h4>
                      <StatusBadge status={span.status} size="sm" />
                    </div>

                    <p className="mt-0.5 text-xs text-[#555555]">
                      <span className="font-semibold text-[#111111]">
                        {span.service_name}
                      </span>{" "}
                      • Span: <span className="font-mono text-[10px]">{span.span_id}</span>
                      {span.parent_span_id && (
                        <span>
                          {" "}• Parent:{" "}
                          <span className="font-mono text-[10px]">{span.parent_span_id}</span>
                        </span>
                      )}
                    </p>
                  </div>
                </div>

                {/* Duration bar relative to trace */}
                <div className="w-full sm:w-64 flex flex-col justify-center">
                  <div className="flex justify-between text-[11px] font-mono text-[#555555] mb-1">
                    <span>+{startOffsetMs.toFixed(0)}ms</span>
                    <span className="font-bold text-[#111111]">
                      {span.duration_ms >= 1000
                        ? `${(span.duration_ms / 1000).toFixed(2)}s`
                        : `${span.duration_ms.toFixed(1)}ms`}
                    </span>
                  </div>

                  <div className="relative h-2 w-full rounded-full bg-[#111111]/10 overflow-hidden">
                    <div
                      className={`absolute h-full rounded-full ${
                        span.status === "ERROR"
                          ? "bg-red-500"
                          : "bg-[#111111]"
                      }`}
                      style={{
                        left: `${Math.min(offsetPercent, 95)}%`,
                        width: `${Math.min(widthPercent, 100 - offsetPercent)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Attributes accordion */}
              {isExpanded && (
                <div className="mt-4 border-t border-[#111111]/10 pt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#555555]">
                      Sanitized Telemetry Attributes ({attrEntries.length})
                    </span>
                    <span className="text-[10px] font-mono text-[#777777]">
                      Start: {new Date(span.start_time).toISOString()}
                    </span>
                  </div>

                  {attrEntries.length === 0 ? (
                    <p className="text-xs italic text-[#777777]">
                      No custom governance or HTTP attributes on this span.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {attrEntries.map(([key, val]) => (
                        <div
                          key={key}
                          className="flex items-start justify-between rounded-xl bg-white/70 p-2 text-xs border border-[#111111]/5"
                        >
                          <span
                            className={`font-mono text-[11px] font-bold ${
                              key.startsWith("gov.")
                                ? "text-indigo-700"
                                : key.startsWith("http.")
                                  ? "text-emerald-700"
                                  : "text-[#555555]"
                            }`}
                          >
                            {key}
                          </span>
                          <span className="font-mono text-[11px] text-[#111111] break-all max-w-[55%] text-right">
                            {typeof val === "object" ? JSON.stringify(val) : String(val)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
