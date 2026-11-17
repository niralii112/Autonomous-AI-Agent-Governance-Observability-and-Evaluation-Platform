import { useId, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { actionLabel, outcomeLabel } from "../../actionLabels";
import { fetchAgentScenarios, submitAgentScenario } from "../../api/agents";
import { actionQueryKeys } from "../../hooks/useActions";
import { evaluationQueryKeys } from "../../hooks/useEvaluations";
import StatusBadge from "../common/StatusBadge";
import { isDemoMode } from "../../demoMode";

const buttonClass =
  "rounded-full bg-[#111111] px-5 py-2.5 text-sm font-bold text-[#F5F87A] hover:bg-[#1A1A1A] disabled:opacity-50";

export default function AgentScenarios({ agentId }: { agentId: string }) {
  const headingId = useId();
  const selectId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [scenarioKey, setScenarioKey] = useState("");
  const submitting = useRef(false);
  const queryClient = useQueryClient();
  const scenarios = useQuery({
    queryKey: ["agents", "scenarios", agentId],
    queryFn: ({ signal }) => fetchAgentScenarios(agentId, signal),
    enabled: isOpen,
  });
  const run = useMutation({
    mutationFn: (key: string) => submitAgentScenario(agentId, key),
    retry: false,
    onSettled: () => { submitting.current = false; },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: actionQueryKeys.all });
      void queryClient.invalidateQueries({
        queryKey: evaluationQueryKeys.agentPerformance(agentId),
      });
    },
  });
  const selected = scenarios.data?.find((scenario) => scenario.scenario_key === scenarioKey);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || submitting.current || run.isPending) return;

    submitting.current = true;
    run.mutate(selected.scenario_key);
  }

  return (
    <section
      aria-labelledby={headingId}
      className="space-y-4 rounded-3xl border border-[#111111]/15 bg-white/80 p-6 shadow-xs md:p-8"
    >
      <h3 id={headingId} className="text-xl font-black tracking-tight">Test this agent</h3>
      <p className="text-sm text-[#555555]">
        {isDemoMode
          ? "Demo mode uses mock decisions. Each run creates a sample action in this session."
          : "Choose a scenario to see whether your rules allow it, block it, or require approval. Running a scenario creates an action record."}
      </p>

      {!isOpen && (
        <button type="button" className={buttonClass} onClick={() => setIsOpen(true)}>
          Run scenario
        </button>
      )}

      {isOpen && scenarios.isPending && <p role="status">Loading scenarios…</p>}
      {isOpen && scenarios.isError && (
        <div className="space-y-2">
          <p role="alert" className="text-sm text-red-800">
            {scenarios.error instanceof TypeError
              ? "Couldn’t connect to the server. Try loading scenarios again."
              : scenarios.error.message}
          </p>
          <button
            type="button"
            className={buttonClass}
            disabled={scenarios.isFetching}
            onClick={() => void scenarios.refetch()}
          >
            Try again
          </button>
        </div>
      )}
      {isOpen && scenarios.isSuccess && scenarios.data.length === 0 && (
        <p role="status" className="text-sm text-[#555555]">This agent has no scenarios available.</p>
      )}
      {isOpen && scenarios.isSuccess && scenarios.data.length > 0 && (
        <form onSubmit={handleSubmit} className="space-y-3">
          <label htmlFor={selectId} className="block text-sm font-bold">Scenario</label>
          <select
            id={selectId}
            value={scenarioKey}
            disabled={run.isPending}
            onChange={(event) => {
              setScenarioKey(event.target.value);
              run.reset();
            }}
            className="w-full rounded-xl border border-[#111111]/25 bg-white px-3 py-2 text-sm md:max-w-lg"
          >
            <option value="">Choose a scenario</option>
            {scenarios.data.map((scenario) => (
              <option key={scenario.scenario_key} value={scenario.scenario_key}>
                {actionLabel(scenario.action_type)} — {scenario.description}
              </option>
            ))}
          </select>
          <button type="submit" className={buttonClass} disabled={!selected || run.isPending}>
            Run scenario
          </button>
          {run.isPending && <p role="status" className="text-sm">Running scenario…</p>}
        </form>
      )}
      {run.isError && (
        <p role="alert" className="text-sm text-red-800">
          {run.error instanceof TypeError
            ? "Couldn’t confirm the run. Check Agent Actions before trying again."
            : run.error.message}
        </p>
      )}
      {run.data && (
        <div role="status" className="flex flex-wrap items-center gap-3 text-sm">
          <span className="font-bold">{isDemoMode ? "Simulated decision" : "Decision"}</span>
          <StatusBadge
            status={run.data.governance_decision.final_decision}
            label={outcomeLabel(run.data.governance_decision.final_decision)}
          />
          <Link className="font-bold underline" to={`/actions/${run.data.action.action_id}`}>
            View action details
          </Link>
        </div>
      )}
    </section>
  );
}
