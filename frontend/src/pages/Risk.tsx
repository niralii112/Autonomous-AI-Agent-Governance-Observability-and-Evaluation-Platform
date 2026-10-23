import { motion } from "motion/react";
import { useRiskSummary, useRiskAssessments, useRiskModels } from "../hooks/useRisk";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";
import EmptyState from "../components/common/EmptyState";

export default function Risk() {
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    refetch: refetchSummary,
  } = useRiskSummary(24);

  const {
    data: assessmentsData,
    isLoading: assessmentsLoading,
  } = useRiskAssessments(1, 20);

  const { data: modelsData } = useRiskModels();

  const assessments = assessmentsData?.items ?? [];
  const models = modelsData?.items ?? [];

  // Parse counts per level
  const levelCounts = new Map(
    (summary?.by_risk_level ?? []).map((l) => [l.risk_level, l.count])
  );

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
            Platform / Heuristic & ML Analytics
          </p>
          <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
            Risk Analytics.
            <br />
            <span className="font-normal italic">Predictive safety.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Evaluate automated risk scores, anomaly detections, and model boundaries
            before and during action execution.
          </p>
        </motion.header>

        {/* Risk Metrics Cards */}
        {summaryLoading ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-8 shadow-xs">
            <LoadingState message="Deriving 24h risk distribution..." lines={2} />
          </div>
        ) : summaryError ? (
          <div className="rounded-3xl bg-[#FFF8F2] p-8 shadow-xs">
            <ErrorState
              title="Risk Summary Unavailable"
              message="Could not load risk analytics metrics."
              onRetry={() => void refetchSummary()}
            />
          </div>
        ) : summary ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div className="rounded-3xl bg-[#111111] p-6 text-white shadow-md">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#A0A0A0]">
                Total Assessments
              </span>
              <p className="mt-2 text-4xl font-black text-[#F5F87A]">
                {summary.total_assessments ?? 0}
              </p>
              <p className="mt-1 text-xs text-[#888888]">In 24-hour window</p>
            </div>

            <div className="rounded-3xl bg-[#FFF8F2] p-6 border border-[#111111]/10 shadow-xs">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                Critical / High Risk
              </span>
              <p className="mt-2 text-4xl font-black text-red-600">
                {(levelCounts.get("CRITICAL") ?? 0) + (levelCounts.get("HIGH") ?? 0)}
              </p>
              <p className="mt-1 text-xs text-[#555555]">Required human review</p>
            </div>

            <div className="rounded-3xl bg-[#FFF8F2] p-6 border border-[#111111]/10 shadow-xs">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                Moderate Risk
              </span>
              <p className="mt-2 text-4xl font-black text-amber-600">
                {levelCounts.get("MEDIUM") ?? 0}
              </p>
              <p className="mt-1 text-xs text-[#555555]">Monitored execution</p>
            </div>

            <div className="rounded-3xl bg-[#FFF8F2] p-6 border border-[#111111]/10 shadow-xs">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                Low Risk (Safe)
              </span>
              <p className="mt-2 text-4xl font-black text-emerald-600">
                {levelCounts.get("LOW") ?? 0}
              </p>
              <p className="mt-1 text-xs text-[#555555]">Directly allowed</p>
            </div>
          </div>
        ) : null}

        {/* Risk Models Section */}
        <div className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-8 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-2xl font-black tracking-tight text-[#111111]">
              Active Risk Assessment Models
            </h3>
            <span className="rounded-full bg-[#111111]/5 px-3 py-1 text-xs font-bold">
              {models.length} Models Registered
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {models.map((model) => (
              <div
                key={model.model_version_id}
                className="rounded-2xl border border-[#111111]/10 bg-white p-5 shadow-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-[#555555]">
                    {model.model_version}
                  </span>
                  <StatusBadge
                    status={model.is_active ? "ACTIVE" : "INACTIVE"}
                    size="sm"
                  />
                </div>
                <h4 className="mt-2 text-base font-black text-[#111111]">
                  {model.model_kind}
                </h4>
                <p className="mt-1 text-xs text-[#666666] line-clamp-2">
                  Algorithm: {model.algorithm}
                </p>
              </div>
            ))}

            {models.length === 0 && (
              <p className="text-xs text-[#777777] col-span-3">
                No external ML models registered. Platform using deterministic heuristic rules.
              </p>
            )}
          </div>
        </div>

        {/* Recent Risk Assessments Feed */}
        <div className="space-y-4">
          <h3 className="text-2xl font-black tracking-tight text-[#111111]">
            Recent Risk Assessments
          </h3>

          {assessmentsLoading ? (
            <div className="rounded-3xl bg-[#FFF8F2] p-8 shadow-xs">
              <LoadingState message="Loading risk assessments..." lines={2} />
            </div>
          ) : assessments.length === 0 ? (
            <EmptyState
              title="No Risk Assessments"
              description="No recent action assessments recorded."
            />
          ) : (
            <div className="space-y-3">
              {assessments.map((a) => (
                <div
                  key={a.risk_assessment_id}
                  className="rounded-2xl border border-[#111111]/10 bg-[#FFF8F2] p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs font-bold text-[#555555]">
                        {a.risk_assessment_id.slice(0, 8)}...
                      </span>
                      <span className="text-[#888888]">•</span>
                      <span className="text-xs font-semibold text-[#111111]">
                        Model: {a.model_version || "Heuristic"}
                      </span>
                      <span className="text-[#888888]">•</span>
                      <span className="font-mono text-xs text-[#777777]">
                        {new Date(a.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="mt-1 font-mono text-xs text-[#666666]">
                      Action ID: {a.action_id}
                    </p>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <span className="text-[10px] font-bold uppercase text-[#777777]">
                        Risk Score
                      </span>
                      <p className="font-mono text-xl font-black text-[#111111]">
                        {(a.risk_score ?? 0).toFixed(2)}
                      </p>
                    </div>

                    <StatusBadge status={a.risk_level} size="md" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
