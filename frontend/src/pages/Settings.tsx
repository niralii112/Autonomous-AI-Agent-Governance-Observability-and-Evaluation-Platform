import { useSystemHealth, useSystemInfo } from "../hooks/useSystem";
import StatusBadge from "../components/common/StatusBadge";
import PageGuide from "../components/common/PageGuide";
import { isDemoMode } from "../demoMode";

const labels = { OK: "Operational", DEGRADED: "Limited service", DOWN: "Service down" };

export default function Settings() {
  const health = useSystemHealth();
  const info = useSystemInfo();
  const current = health.isError ? undefined : health.data;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-5 md:p-10">
      <header>
        <h1 className="text-4xl font-black tracking-tight">System Health</h1>
        <p className="mt-2">
          {isDemoMode ? "This workspace shows sample service status." : "Check the latest reported status of AgentGuard services."}
        </p>
      </header>

      <section className="rounded-3xl bg-cream p-6" aria-labelledby="service-status">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="service-status" className="text-2xl font-bold">Service status</h2>
          <button type="button" disabled={health.isFetching} onClick={() => void health.refetch()}
            className="rounded-full bg-ink px-5 py-2 font-semibold text-cream disabled:opacity-60">
            {health.isFetching ? "Checking…" : "Refresh status"}
          </button>
        </div>
        {health.isPending ? (
          <p role="status" className="mt-4">Checking service status…</p>
        ) : health.isError ? (
          <div role="alert" className="mt-4 rounded-xl bg-peach p-4">
            <p className="font-bold">Status unavailable</p>
            <p className="mt-1 text-sm">
              {isDemoMode
                ? "The sample health response could not be loaded. Refresh this page and try again."
                : "AgentGuard could not load the health check. Try refreshing the status."}
            </p>
            <p className="mt-2 text-sm">{health.error.message}</p>
          </div>
        ) : current && (
          <>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <StatusBadge status={current.status} label={labels[current.status]} />
              <p className="text-sm">Last checked {new Date(current.checked_at).toLocaleString()}</p>
            </div>
            {current.components.length ? (
              <ul className="mt-4 grid gap-3 sm:grid-cols-2">
                {current.components.map((service) => (
                  <li key={service.component_name} className="rounded-xl border border-ink/15 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-bold">{service.component_name}</h3>
                      <StatusBadge status={service.status} label={labels[service.status]} size="sm" />
                    </div>
                    {service.detail && <p className="mt-2 text-sm">{service.detail}</p>}
                    {typeof service.latency_ms === "number" && <p className="mt-1 text-sm">Response time {service.latency_ms.toFixed(1)} ms</p>}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-4">The health check returned no individual service results.</p>}
          </>
        )}
      </section>

      <img src={import.meta.env.BASE_URL + "system-health.jpg"}
        alt="Network equipment with service indicator lights" width={720} height={480}
        className="h-48 w-full rounded-2xl object-cover md:h-64" />
      <PageGuide page="health" />

      <details className="rounded-2xl bg-cream p-5">
        <summary className="cursor-pointer font-bold">Version information</summary>
        {info.isPending ? <p className="mt-3">Loading version information…</p> : info.isError || !info.data ? (
          <p className="mt-3">Version information is unavailable.</p>
        ) : (
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div><dt>Application</dt><dd>{info.data.app_version}</dd></div>
            <div><dt>API</dt><dd>{info.data.api_version}</dd></div>
            <div><dt>Contract</dt><dd>{info.data.contract_version}</dd></div>
            <div><dt>Environment</dt><dd>{info.data.environment}</dd></div>
          </dl>
        )}
      </details>
    </div>
  );
}
