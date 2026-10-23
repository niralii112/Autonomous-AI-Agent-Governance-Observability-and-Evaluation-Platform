import { useState } from "react";
import { motion } from "motion/react";
import { usePolicies } from "../hooks/usePolicies";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";

export default function Policies() {
  const { data: policiesData, isLoading, isError, refetch } = usePolicies();
  const [selectedEffect, setSelectedEffect] = useState("ALL");
  const [expandedPolicyId, setExpandedPolicyId] = useState<string | null>(null);

  const policies = policiesData?.items ?? [];

  const filtered = policies.filter((p) => {
    if (selectedEffect === "ALL") return true;
    return p.effect === selectedEffect;
  });

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
                Platform / Governance Engine
              </p>
              <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
                Policy Rules.
                <br />
                <span className="font-normal italic">Enforced boundaries.</span>
              </h1>
            </div>

            <span className="rounded-full bg-[#F5F87A] px-5 py-2.5 text-xs font-black uppercase text-[#111111]">
              {policies.length} Active Rules
            </span>
          </div>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Deterministic governance policies that evaluate every proposed agent action.
            Configure ALLOW, BLOCK, and HUMAN_REVIEW effects with mandatory thresholds.
          </p>
        </motion.header>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-[#111111]/10 bg-[#FFF8F2] p-5 shadow-xs">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-[#555555]">
              Filter by Enforcement Effect:
            </span>
            <select
              value={selectedEffect}
              onChange={(e) => setSelectedEffect(e.target.value)}
              className="rounded-xl border border-[#111111]/20 bg-white px-3 py-2 text-xs font-semibold text-[#111111] focus:border-[#111111] focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Effects</option>
              <option value="ALLOW">ALLOW</option>
              <option value="HUMAN_REVIEW">HUMAN_REVIEW</option>
              <option value="BLOCK">BLOCK</option>
            </select>
          </div>
        </div>

        {/* Policy Cards */}
        {isLoading ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <LoadingState message="Fetching active governance policies..." />
          </div>
        ) : isError ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-10 shadow-xs">
            <ErrorState
              title="Failed to Load Policies"
              message="Could not retrieve governance policies from the backend."
              onRetry={() => void refetch()}
            />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No Matching Policies"
            description="No policies match the selected filter effect."
          />
        ) : (
          <div className="space-y-4">
            {filtered.map((policy) => {
              const isExpanded = expandedPolicyId === policy.policy_id;

              return (
                <div
                  key={policy.policy_id}
                  className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-6 shadow-xs transition hover:border-[#111111]/30"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs font-bold text-[#555555]">
                          v{policy.version}
                        </span>
                        <span className="text-[#888888]">•</span>
                        <span className="font-mono text-xs text-[#777777]">
                          Priority: {policy.priority}
                        </span>
                        {policy.is_mandatory && (
                          <>
                            <span className="text-[#888888]">•</span>
                            <span className="rounded-full bg-red-100 text-red-800 px-2.5 py-0.5 text-[10px] font-black uppercase">
                              Mandatory
                            </span>
                          </>
                        )}
                      </div>

                      <h3 className="mt-2 text-2xl font-black text-[#111111]">
                        {policy.name}
                      </h3>

                      <p className="mt-1 text-xs text-[#555555] max-w-2xl">
                        {policy.description || "No rule description provided."}
                      </p>

                      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[#666666]">
                        <span>Key: <code className="font-mono text-[#111111]">{policy.policy_key}</code></span>
                        {policy.scope_action_type && (
                          <>
                            <span>•</span>
                            <span>Scope: <code className="font-mono text-[#111111]">{policy.scope_action_type}</code></span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusBadge status={policy.effect} size="md" />

                      <button
                        type="button"
                        onClick={() =>
                          setExpandedPolicyId(isExpanded ? null : policy.policy_id)
                        }
                        className="cursor-pointer rounded-full bg-[#111111]/5 px-4 py-2 text-xs font-bold text-[#111111] hover:bg-[#FFE3CE] transition"
                      >
                        {isExpanded ? "Hide Logic" : "Inspect Conditions"}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-4 border-t border-[#111111]/10 pt-4">
                      <span className="text-[10px] font-black uppercase tracking-wider text-[#555555] block mb-2">
                        Condition Tree Logic
                      </span>
                      <pre className="overflow-x-auto rounded-2xl bg-[#111111] p-4 font-mono text-xs text-[#F5F87A]">
                        {JSON.stringify(policy.conditions || {}, null, 2)}
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
