import { Link, useParams } from "react-router-dom";
import { actionLabel, readableLabel } from "../actionLabels";
import { useAction, useRetryAction } from "../hooks/useActions";
import { useAgents } from "../hooks/useAgents";
import { useAuth } from "../hooks/useAuth";
import { useTracesByAction } from "../hooks/useTraces";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";

const outcomes: Record<string, string> = {
  ALLOW: "Allowed to proceed",
  HUMAN_REVIEW: "Sent for human review",
  BLOCK: "Blocked by safety checks",
  SUCCEEDED: "Completed",
  FAILED: "Action failed",
};

export default function ActionDetailsPage() {
  const { actionId = "" } = useParams();
  const { hasRole } = useAuth();
  const actionQuery = useAction(actionId);
  const traces = useTracesByAction(actionId);
  const assistants = useAgents();
  const retry = useRetryAction();
  const detail = actionQuery.data;
  const action = detail?.action;
  const decision = detail?.governance_decisions.reduce<(typeof detail.governance_decisions)[number] | undefined>(
    (latest, item) => !latest || item.decision_sequence > latest.decision_sequence ? item : latest,
    undefined,
  );
  const execution = detail?.executions.reduce<(typeof detail.executions)[number] | undefined>(
    (latest, item) => !latest || item.attempt_number > latest.attempt_number ? item : latest,
    undefined,
  );
  const assistant = assistants.data?.items.find((item) => item.agent_id === action?.agent_id);
  const approval = detail?.approvals.reduce<(typeof detail.approvals)[number] | undefined>(
    (latest, item) => !latest || Date.parse(item.requested_at) > Date.parse(latest.requested_at) ? item : latest,
    undefined,
  );
  const payload = action?.payload_redacted ? undefined : action?.action_payload;
  const status = execution?.execution_status ?? approval?.approval_status ?? decision?.final_decision;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-5 md:p-10">
      <Link to="/actions" className="font-semibold underline">Back to activity history</Link>
      {actionQuery.isPending ? (
        <LoadingState message="Loading action details…" />
      ) : actionQuery.isError || !action ? (
        <ErrorState
          title="Action details unavailable"
          message="Try loading this action again or return to activity history."
          onRetry={() => void actionQuery.refetch()}
        />
      ) : (
        <>
          <section className="rounded-3xl bg-cream p-6 md:p-8">
            <h1 className="text-3xl font-black tracking-tight">{actionLabel(action.action_type)}</h1>
            <p className="mt-3 text-lg font-bold">{!execution && approval?.approval_status === "PENDING" ? "Waiting for approval" : status ? outcomes[status] ?? readableLabel(status) : "No outcome recorded"}</p>
            {decision?.decision_reason_code && (
              <p className="mt-2">Recorded reason · {readableLabel(decision.decision_reason_code)}</p>
            )}
            <dl className="mt-6 grid gap-4 sm:grid-cols-2">
              <div><dt className="font-semibold">AI assistant</dt><dd>{assistant?.agent_name ?? "Name unavailable"}</dd></div>
              <div><dt className="font-semibold">Requested on</dt><dd>{new Date(action.created_at).toLocaleString()}</dd></div>
            </dl>
            {payload && (action.action_type === "FINANCE_PROPOSE_PAYMENT" || action.action_type === "SUPPORT_PROPOSE_REFUND") && (
              <dl className="mt-5 grid gap-4 sm:grid-cols-2">
                {typeof payload.recipient === "string" && <div><dt className="font-semibold">Recipient</dt><dd>{payload.recipient}</dd></div>}
                {typeof payload.amount === "number" && <div><dt className="font-semibold">Payment amount</dt><dd>{payload.amount.toLocaleString()} {typeof payload.currency === "string" && payload.currency}</dd></div>}
                {typeof payload.refund_amount === "number" && <div><dt className="font-semibold">Refund amount</dt><dd>{payload.refund_amount.toLocaleString()} {typeof payload.currency === "string" && payload.currency}</dd></div>}
                {typeof payload.reason === "string" && <div><dt className="font-semibold">Request reason</dt><dd>{payload.reason}</dd></div>}
              </dl>
            )}
            {approval?.approval_status === "PENDING" && <Link to="/approvals?status=pending" className="mt-5 inline-block font-semibold underline">View pending approvals</Link>}
            {hasRole(["ADMIN", "OPERATOR"]) && execution?.execution_status === "FAILED" && (
              <button type="button" className="mt-5 block rounded-full bg-ink px-5 py-2 font-semibold text-cream" disabled={retry.isPending} onClick={() => retry.mutate(action.action_id)}>
                {retry.isPending ? "Requesting retry…" : "Retry action"}
              </button>
            )}
            {retry.isError && <p role="alert" className="mt-3">Unable to retry this action. Try again.</p>}
            {retry.isSuccess && <p role="status" className="mt-3">Retry requested.</p>}
          </section>
          <details className="rounded-3xl bg-cream p-6 md:p-8">
            <summary className="cursor-pointer text-lg font-bold">Technical details</summary>
            <p className="mt-4 break-all text-sm">Action ID {action.action_id}</p>
            {action.requested_tool_name && <p className="mt-1 text-sm">Requested tool · {action.requested_tool_name}</p>}
            <h2 className="mt-5 font-bold">Action data</h2>
            <pre className="mt-2 overflow-x-auto rounded-xl bg-ink p-4 text-xs text-cream">{JSON.stringify(action.action_payload, null, 2)}</pre>
            <h2 className="mt-5 font-bold">Execution traces</h2>
            {traces.isPending ? (
              <LoadingState message="Loading trace diagnostics…" lines={2} />
            ) : traces.isError ? (
              <p className="mt-2">Trace diagnostics are unavailable. <button type="button" className="underline" onClick={() => void traces.refetch()}>Try again</button></p>
            ) : !traces.data?.traces.length ? (
              <p className="mt-2">No traces were found for this action.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {traces.data.traces.map((trace) => (
                  <li key={trace.trace_id}>
                    <Link className="break-all font-semibold underline" to={`/traces/${trace.trace_id}`}>{trace.root_span_name || trace.trace_id}</Link>
                    <span className="ml-2 text-sm">{trace.duration_ms.toFixed(1)} ms · {trace.span_count} spans · {trace.error_count} errors</span>
                  </li>
                ))}
              </ul>
            )}
          </details>
        </>
      )}
    </div>
  );
}
