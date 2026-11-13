import { Link } from "react-router-dom";
import OverviewWalkthrough from "../components/common/OverviewWalkthrough";
import { isDemoMode } from "../demoMode";
import { useAgents } from "../hooks/useAgents";
import { useApprovals } from "../hooks/useApprovals";

export default function Dashboard() {
  const assistants = useAgents();
  const pending = useApprovals(1, "PENDING");

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-5 md:p-10">
      <header>
        <h1 className="text-4xl font-black tracking-tight">Overview</h1>
        <p className="mt-2 text-charcoal">See what needs review and check what your AI assistants have done.</p>
        {isDemoMode && <p className="mt-2 text-sm font-semibold">Sample data</p>}
      </header>

      <section className="rounded-3xl bg-ink p-6 text-cream md:p-8" aria-labelledby="attention">
        <h2 id="attention" className="text-2xl font-bold">Needs your attention</h2>
        {pending.isPending ? (
          <p className="mt-3" role="status">Checking for pending approvals…</p>
        ) : pending.isError ? (
          <p className="mt-3">Pending approvals are unavailable. <button type="button" className="underline" onClick={() => void pending.refetch()}>Try again</button></p>
        ) : pending.data?.total_items === 0 ? (
          <p className="mt-3">No requests are waiting for a decision.</p>
        ) : pending.data?.total_items !== undefined ? (
          <p className="mt-3">{pending.data.total_items} {pending.data.total_items === 1 ? "request is" : "requests are"} waiting for a decision.</p>
        ) : null}
        <Link to="/approvals?status=pending" className="mt-5 inline-block rounded-full bg-neon px-5 py-3 font-bold text-ink">View pending approvals</Link>
      </section>

      <OverviewWalkthrough />

      <section aria-labelledby="assistants" className="rounded-3xl bg-cream p-6 md:p-8">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="assistants" className="text-2xl font-bold">AI Assistants</h2>
          <Link to="/agents" className="font-semibold underline">View all assistants</Link>
        </div>
        {assistants.isPending ? (
          <p className="mt-4" role="status">Loading assistants…</p>
        ) : assistants.isError ? (
          <p className="mt-4">Assistants are unavailable. <button type="button" className="underline" onClick={() => void assistants.refetch()}>Try again</button></p>
        ) : !assistants.data?.items.length ? (
          <p className="mt-4">No assistants are registered yet.</p>
        ) : (
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {assistants.data.items.slice(0, 4).map((assistant) => (
              <li key={assistant.agent_id}>
                <Link to={`/agents/${assistant.agent_id}`} className="block h-full rounded-xl border border-ink/15 p-4 hover:bg-peach/50">
                  <span className="font-bold">{assistant.agent_name}</span>
                  {assistant.description && <p className="mt-1 text-sm">{assistant.description}</p>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <Link to="/actions" className="inline-block font-bold underline">View activity history</Link>
    </div>
  );
}
