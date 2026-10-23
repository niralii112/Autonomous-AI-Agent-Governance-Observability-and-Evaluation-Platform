import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { useAgents } from "../hooks/useAgents";
import { useTraces } from "../hooks/useTraces";
import type { components } from "../types/generated/api";
import LatencyChart from "../components/traces/LatencyChart";
import TraceTimeline from "../components/traces/TraceTimeline";
import TraceFilters from "../components/traces/TraceFilters";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";

type TraceSummary = components["schemas"]["TraceSummary"];

function formatDuration(ms: number) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
}

function formatTimestamp(value: string) {
  return new Date(value).toLocaleString();
}

export default function Traces() {
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("ALL");
  const [hasErrorFilter, setHasErrorFilter] = useState("ALL");
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);

  const {
    data: traceData,
    isLoading,
    isError,
    refetch,
  } = useTraces({
    windowMinutes,
    hasError:
      hasErrorFilter === "ERROR"
        ? true
        : hasErrorFilter === "OK"
          ? false
          : undefined,
  });

  const { data: agentData } = useAgents();

  const agents = agentData?.items ?? [];

  const agentNames = useMemo(
    () => new Map(agents.map((agent) => [agent.agent_id, agent.agent_name])),
    [agents]
  );

  const traces: TraceSummary[] = traceData?.items ?? [];

  const filteredTraces = traces.filter((trace) => {
    const agentName = trace.agent_id
      ? agentNames.get(trace.agent_id) ?? trace.agent_id
      : "Unknown agent";

    const status = trace.error_count > 0 ? "ERROR" : "OK";

    const matchesSearch = [
      trace.trace_id,
      trace.root_span_name,
      trace.service_name,
      trace.action_id ?? "",
      agentName,
      status,
    ]
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesAgent =
      agentFilter === "ALL" || trace.agent_id === agentFilter;

    const matchesError =
      hasErrorFilter === "ALL" ||
      (hasErrorFilter === "ERROR" && trace.error_count > 0) ||
      (hasErrorFilter === "OK" && trace.error_count === 0);

    return matchesSearch && matchesAgent && matchesError;
  });

  return (
    <div className="min-h-screen bg-[#FFE3CE] px-6 py-10 text-[#111111] md:px-12 lg:px-20 space-y-12">
      <div className="mx-auto max-w-6xl space-y-12">
        {/* Editorial Header */}
        <motion.header
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <p className="mb-8 text-[10px] font-bold uppercase tracking-[0.35em] text-[#555555]">
            Platform / Observability
          </p>

          <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
            Every action.
            <br />
            <span className="font-normal italic">Fully visible.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Explore agent execution traces, investigate span failures, and
            correlate actions with live OpenTelemetry & Jaeger telemetry.
          </p>
        </motion.header>

        {/* Latency Distribution Chart */}
        <section>
          <LatencyChart initialWindowMinutes={windowMinutes} />
        </section>

        {/* Trace List & Search Section */}
        <section className="space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.3em] text-[#555555]">
                Execution Telemetry
              </p>
              <h2 className="text-3xl font-black tracking-tight md:text-4xl">
                Trace explorer.
              </h2>
            </div>

            <span className="rounded-full bg-[#F5F87A] px-5 py-2.5 text-xs font-black uppercase tracking-wider text-[#111111]">
              {filteredTraces.length} Traces Loaded
            </span>
          </div>

          {/* Modular Filters */}
          <TraceFilters
            search={search}
            onSearchChange={setSearch}
            agentFilter={agentFilter}
            onAgentFilterChange={setAgentFilter}
            agents={agents}
            hasErrorFilter={hasErrorFilter}
            onHasErrorFilterChange={setHasErrorFilter}
            windowMinutes={windowMinutes}
            onWindowMinutesChange={setWindowMinutes}
          />

          {isLoading && (
            <div className="rounded-3xl bg-[#FFF8F2] p-8 shadow-xs">
              <LoadingState message="Loading recent execution traces..." />
            </div>
          )}

          {isError && (
            <div className="rounded-3xl bg-[#FFF8F2] p-8 shadow-xs">
              <ErrorState
                title="Telemetry Backend Unavailable"
                message="Unable to communicate with the trace query service. Ensure Jaeger / OTel Collector is running."
                errorCode="TELEMETRY_UNAVAILABLE"
                onRetry={() => void refetch()}
              />
            </div>
          )}

          {!isLoading && !isError && (
            <div className="space-y-4">
              {filteredTraces.map((trace, index) => {
                const isOpen = selectedTrace === trace.trace_id;

                const agentName = trace.agent_id
                  ? agentNames.get(trace.agent_id) ?? trace.agent_id
                  : "System Agent";

                const hasError = trace.error_count > 0;

                return (
                  <motion.article
                    key={trace.trace_id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="overflow-hidden rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] shadow-xs transition hover:border-[#111111]/30"
                  >
                    <div className="flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between md:p-8">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <p className="font-mono text-[11px] font-bold uppercase tracking-wider text-[#555555] truncate">
                            {trace.trace_id}
                          </p>
                          <span className="text-[10px] font-bold text-[#888888]">•</span>
                          <span className="text-xs font-semibold text-[#111111]">
                            {agentName}
                          </span>
                        </div>

                        <h3 className="mt-2 text-xl font-black tracking-tight text-[#111111] md:text-2xl">
                          {trace.root_span_name}
                        </h3>

                        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[#666666]">
                          <span>{formatTimestamp(trace.start_time)}</span>
                          <span>•</span>
                          <span className="font-mono font-bold text-[#111111]">
                            {formatDuration(trace.duration_ms)}
                          </span>
                          <span>•</span>
                          <span>{trace.span_count} spans</span>
                          {trace.action_id && (
                            <>
                              <span>•</span>
                              <Link
                                to={`/actions/${trace.action_id}`}
                                className="font-mono text-indigo-700 hover:underline"
                                onClick={(e) => e.stopPropagation()}
                              >
                                Action: {trace.action_id.slice(0, 8)}...
                              </Link>
                            </>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <StatusBadge
                          status={hasError ? "ERROR" : "OK"}
                          size="md"
                        />

                        {/* Link to dedicated waterfall route */}
                        <Link
                          to={`/traces/${trace.trace_id}`}
                          className="rounded-full bg-[#111111] px-4 py-2 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A] transition"
                        >
                          Inspect Waterfall →
                        </Link>

                        {/* Inline Timeline Toggle */}
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          onClick={() =>
                            setSelectedTrace(isOpen ? null : trace.trace_id)
                          }
                          className="flex h-9 w-9 items-center justify-center rounded-full bg-[#111111]/5 text-lg font-bold text-[#111111] hover:bg-[#FFE3CE] transition cursor-pointer"
                        >
                          {isOpen ? "−" : "+"}
                        </button>
                      </div>
                    </div>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          key="details"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3 }}
                          className="overflow-hidden border-t border-[#111111]/10 bg-white/60 px-6 py-6 md:px-8"
                        >
                          <div className="flex items-center justify-between mb-4">
                            <span className="text-[10px] font-black uppercase tracking-[0.25em] text-[#555555]">
                              Execution Timeline
                            </span>
                            <Link
                              to={`/traces/${trace.trace_id}`}
                              className="text-xs font-bold text-indigo-700 hover:underline"
                            >
                              Open Full Waterfall View →
                            </Link>
                          </div>

                          <TraceTimeline traceId={trace.trace_id} />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.article>
                );
              })}

              {filteredTraces.length === 0 && (
                <div className="rounded-3xl bg-[#FFF8F2] p-12 text-center border border-[#111111]/10">
                  <h3 className="text-xl font-black">No matching traces.</h3>
                  <p className="mt-2 text-sm text-[#555555]">
                    Try adjusting the search query, outcome status, or time window filter.
                  </p>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
