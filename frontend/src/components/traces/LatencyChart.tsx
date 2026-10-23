import { useState } from "react";
import { useTraceMetrics } from "../../hooks/useTraces";
import LoadingState from "../common/LoadingState";
import ErrorState from "../common/ErrorState";

type LatencyChartProps = {
  initialWindowMinutes?: number;
};

export default function LatencyChart({
  initialWindowMinutes = 60,
}: LatencyChartProps) {
  const [windowMinutes, setWindowMinutes] = useState(initialWindowMinutes);
  const { data, isLoading, isError, refetch } = useTraceMetrics(windowMinutes, 60);

  const buckets = data?.buckets ?? [];

  const maxDuration = Math.max(
    ...buckets.map((b) => Math.max(b.p95_ms ?? 0, b.p50_ms ?? 0)),
    50
  );

  return (
    <div className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-8 text-[#111111] shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#111111]/10 pb-6">
        <div>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#555555]">
            Telemetry Series / Observability
          </span>
          <h3 className="mt-1 text-2xl font-black tracking-tight">
            Latency Distribution (p50 / p95)
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {[15, 60, 360, 1440].map((mins) => (
            <button
              key={mins}
              type="button"
              onClick={() => setWindowMinutes(mins)}
              className={`cursor-pointer rounded-full px-4 py-1.5 text-xs font-bold transition ${
                windowMinutes === mins
                  ? "bg-[#111111] text-[#F5F87A]"
                  : "bg-[#111111]/5 text-[#111111] hover:bg-[#FFE3CE]"
              }`}
            >
              {mins >= 60 ? `${mins / 60}h` : `${mins}m`}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Deriving latency metrics..." lines={2} />
      ) : isError ? (
        <div className="mt-6">
          <ErrorState
            title="Telemetry Series Unavailable"
            message="Could not load latency series from the trace backend."
            onRetry={() => void refetch()}
          />
        </div>
      ) : buckets.length === 0 ? (
        <div className="py-12 text-center text-sm font-semibold text-[#666666]">
          No trace latency data available in this time window.
        </div>
      ) : (
        <div className="mt-8">
          <div className="flex items-end gap-3 h-48 pt-4">
            {buckets.map((bucket, idx) => {
              const p50 = bucket.p50_ms ?? 0;
              const p95 = bucket.p95_ms ?? 0;
              const p50Height = maxDuration > 0 ? (p50 / maxDuration) * 100 : 0;
              const p95Height = maxDuration > 0 ? (p95 / maxDuration) * 100 : 0;

              return (
                <div
                  key={bucket.bucket_start || idx}
                  className="group relative flex-1 flex flex-col items-center justify-end h-full"
                >
                  {/* Tooltip on hover */}
                  <div className="pointer-events-none absolute -top-12 z-20 hidden -translate-x-1/2 flex-col items-center whitespace-nowrap rounded-xl bg-[#111111] px-3 py-1.5 text-[10px] font-bold text-white shadow-lg group-hover:flex">
                    <span>p50: {p50.toFixed(0)}ms | p95: {p95.toFixed(0)}ms</span>
                    <span className="text-[#F5F87A]">{bucket.request_count} req ({bucket.error_count} err)</span>
                  </div>

                  <div className="w-full max-w-[28px] relative flex items-end justify-center h-full">
                    {/* p95 background bar */}
                    <div
                      className="w-full rounded-t-lg bg-[#FFE3CE] transition-all group-hover:bg-[#FFD1AF]"
                      style={{ height: `${Math.max(p95Height, 6)}%` }}
                    />
                    {/* p50 foreground bar */}
                    <div
                      className="absolute w-full rounded-t-lg bg-[#111111] transition-all group-hover:bg-[#F5F87A]"
                      style={{ height: `${Math.max(p50Height, 4)}%` }}
                    />
                  </div>

                  <span className="mt-2 text-[9px] font-mono text-[#777777] truncate max-w-full">
                    {new Date(bucket.bucket_start).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between border-t border-[#111111]/10 pt-4 text-xs font-semibold text-[#555555]">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-[#111111]" />
                <span>p50 Median</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-[#FFE3CE] border border-[#111111]/20" />
                <span>p95 Tail Latency</span>
              </div>
            </div>
            <span className="font-mono text-[11px]">
              Peak Window Latency: {maxDuration.toFixed(1)}ms
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
