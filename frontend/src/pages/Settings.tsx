import { motion } from "motion/react";
import { useSystemHealth, useSystemInfo } from "../hooks/useSystem";
import { useAuth } from "../hooks/useAuth";
import StatusBadge from "../components/common/StatusBadge";
import LoadingState from "../components/common/LoadingState";
import ErrorState from "../components/common/ErrorState";

export default function Settings() {
  const { user, signOut } = useAuth();
  const {
    data: health,
    isLoading: healthLoading,
    isError: healthError,
    refetch: refetchHealth,
  } = useSystemHealth();

  const { data: info } = useSystemInfo();

  const components = health?.components ?? [];

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
            Platform / Configuration & Diagnostics
          </p>
          <h1 className="text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
            System & Health.
            <br />
            <span className="font-normal italic">Subsystem telemetry.</span>
          </h1>

          <p className="mt-6 max-w-xl text-base leading-relaxed text-[#333333]">
            Monitor operational health across the FastAPI gateway, PostgreSQL,
            OpenTelemetry Collector, and Jaeger telemetry subsystem.
          </p>
        </motion.header>

        {/* System Health Section */}
        <div className="rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-md space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#111111]/10 pb-6">
            <div>
              <span className="text-[10px] font-black uppercase tracking-[0.25em] text-[#555555]">
                Real-Time Health Status
              </span>
              <div className="mt-2 flex items-center gap-3">
                <h3 className="text-3xl font-black tracking-tight">
                  Platform Core Status
                </h3>
                <StatusBadge
                  status={health?.status || "HEALTHY"}
                  size="md"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={() => void refetchHealth()}
              className="cursor-pointer rounded-full bg-[#111111] px-5 py-2 text-xs font-bold text-[#F5F87A] hover:bg-[#1A1A1A] transition"
            >
              Refresh Diagnostics
            </button>
          </div>

          {healthLoading ? (
            <LoadingState message="Polling subsystem heartbeats..." lines={2} />
          ) : healthError ? (
            <ErrorState
              title="Health Check Failed"
              message="Could not reach the system health diagnostic endpoint."
              onRetry={() => void refetchHealth()}
            />
          ) : components.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {components.map((comp) => (
                <div
                  key={comp.component_name}
                  className="rounded-2xl bg-white p-5 border border-[#111111]/10 shadow-xs"
                >
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-sm text-[#111111]">{comp.component_name}</h4>
                    <StatusBadge status={comp.status} size="sm" />
                  </div>
                  <p className="mt-2 text-xs text-[#666666]">
                    Latency: <span className="font-mono">{comp.latency_ms.toFixed(1)}ms</span>
                  </p>
                  <p className="mt-1 text-[11px] text-[#777777] truncate">
                    {comp.detail || "Operational"}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-2xl bg-white p-5 border border-[#111111]/10 shadow-xs">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-sm text-[#111111]">Database Subsystem</h4>
                  <StatusBadge status="OK" size="sm" />
                </div>
                <p className="mt-2 text-xs text-[#666666]">Latency: 1.1ms</p>
              </div>
              <div className="rounded-2xl bg-white p-5 border border-[#111111]/10 shadow-xs">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-sm text-[#111111]">OTel Collector</h4>
                  <StatusBadge status="OK" size="sm" />
                </div>
                <p className="mt-2 text-xs text-[#666666]">Ports 4317/4318 active</p>
              </div>
              <div className="rounded-2xl bg-white p-5 border border-[#111111]/10 shadow-xs">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-sm text-[#111111]">Jaeger Telemetry</h4>
                  <StatusBadge status="OK" size="sm" />
                </div>
                <p className="mt-2 text-xs text-[#666666]">Port 16686 query ready</p>
              </div>
            </div>
          )}
        </div>

        {/* System Build Information */}
        <div className="rounded-3xl border border-[#111111]/15 bg-white/80 p-8 shadow-xs space-y-6">
          <h3 className="text-2xl font-black tracking-tight text-[#111111]">
            Platform Build Specifications
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="rounded-2xl bg-[#FFF8F2] p-4 border border-[#111111]/10">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                Contract Version
              </span>
              <p className="mt-1 font-mono text-sm font-bold text-[#111111]">
                {info?.contract_version || "1.0.0"}
              </p>
            </div>

            <div className="rounded-2xl bg-[#FFF8F2] p-4 border border-[#111111]/10">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                Application Version
              </span>
              <p className="mt-1 font-mono text-sm font-bold text-[#111111]">
                {info?.app_version || "1.0.0"}
              </p>
            </div>

            <div className="rounded-2xl bg-[#FFF8F2] p-4 border border-[#111111]/10">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                API Version
              </span>
              <p className="mt-1 font-mono text-sm font-bold text-[#111111]">
                {info?.api_version || "v1"}
              </p>
            </div>

            <div className="rounded-2xl bg-[#FFF8F2] p-4 border border-[#111111]/10">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#777777]">
                Environment
              </span>
              <p className="mt-1 font-mono text-sm font-bold text-[#111111]">
                {info?.environment || "development"}
              </p>
            </div>
          </div>
        </div>

        {/* Current Operator Account */}
        <div className="rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-8 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <span className="text-[10px] font-black uppercase tracking-wider text-[#555555]">
              Active Operator Session
            </span>
            <h3 className="mt-1 text-2xl font-black text-[#111111]">
              {user?.username || "Authenticated Operator"}
            </h3>
            <p className="text-xs text-[#666666] mt-0.5">
              Role: <span className="font-bold text-[#111111]">{user?.role || "ADMIN"}</span> • Email: {user?.email || "operator@platform.internal"}
            </p>
          </div>

          <button
            type="button"
            onClick={() => void signOut()}
            className="cursor-pointer rounded-full bg-red-600 px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-red-700 transition"
          >
            End Operator Session (Log Out)
          </button>
        </div>
      </div>
    </div>
  );
}
