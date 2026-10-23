import { useState } from "react";
import { motion } from "motion/react";
import { useAuditEvents } from "../hooks/useAudit";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";

export default function Audit() {
  const [page, setPage] = useState(1);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const { data: auditData, isLoading, isError, refetch } = useAuditEvents(page, 25);

  const events = auditData?.items ?? [];
  const totalPages = auditData?.total_pages ?? 1;

  return (
    <div className="min-h-screen bg-[#FFE3CE] px-6 py-10 text-[#111111] md:px-12 lg:px-20 space-y-12">
      <div className="mx-auto max-w-6xl space-y-10">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: 25 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <p className="mb-4 text-[10px] font-bold uppercase tracking-[0.35em] text-[#555555]">
            Platform / Compliance & Security
          </p>
          <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
            Audit Trail.
            <br />
            <span className="font-normal italic">Immutable activity.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Comprehensive, tamper-resistant record of operator logins, policy updates,
            human approvals, and automated decisions.
          </p>
        </motion.header>

        {/* Audit Log Feed */}
        {isLoading ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <LoadingState message="Fetching immutable audit events..." />
          </div>
        ) : isError ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <ErrorState
              title="Failed to Load Audit Log"
              message="Could not load audit trail from the compliance service."
              onRetry={() => void refetch()}
            />
          </div>
        ) : events.length === 0 ? (
          <EmptyState
            title="No Audit Events Recorded"
            description="The audit log has no entries recorded for this time window."
          />
        ) : (
          <div className="space-y-3">
            {events.map((event) => {
              const isSelected = selectedEventId === event.audit_event_id;

              return (
                <div
                  key={event.audit_event_id}
                  className="rounded-2xl border border-[#111111]/15 bg-[#FFF8F2] p-5 shadow-xs transition hover:border-[#111111]/30 cursor-pointer"
                  onClick={() => setSelectedEventId(isSelected ? null : event.audit_event_id)}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="rounded-full bg-[#111111] px-3 py-0.5 text-[10px] font-black uppercase text-[#F5F87A]">
                          {event.event_name}
                        </span>
                        <span className="text-[#888888]">•</span>
                        <span className="text-xs font-bold text-[#111111]">
                          Actor: {event.actor_user_id ? event.actor_user_id.slice(0, 8) : event.actor_type}
                        </span>
                        <span className="text-[#888888]">•</span>
                        <span className="font-mono text-xs text-[#666666]">
                          {new Date(event.created_at).toLocaleString()}
                        </span>
                      </div>

                      <h4 className="mt-2 text-base font-bold text-[#111111]">
                        {event.event_name} ({event.outcome})
                      </h4>

                      <p className="mt-1 text-xs text-[#555555]">
                        Entity: <span className="font-mono text-[#111111]">{event.entity_type || "N/A"}</span>
                        {event.entity_id && ` (${event.entity_id.slice(0, 8)}...)`}
                      </p>
                    </div>

                    <span className="text-xs font-bold text-indigo-700 hover:underline">
                      {isSelected ? "Hide Metadata ▲" : "View Metadata ▼"}
                    </span>
                  </div>

                  {isSelected && (
                    <div className="mt-4 border-t border-[#111111]/10 pt-4">
                      <span className="text-[10px] font-black uppercase tracking-wider text-[#555555] block mb-2">
                        Event Payload & Metadata
                      </span>
                      <pre className="overflow-x-auto rounded-2xl bg-[#111111] p-4 font-mono text-xs text-[#F5F87A]">
                        {JSON.stringify(event.event_data || {}, null, 2)}
                      </pre>
                    </div>
                  )}
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
