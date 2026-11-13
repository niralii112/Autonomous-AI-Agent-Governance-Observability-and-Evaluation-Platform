import { Link } from "react-router-dom";

const guides = {
  activity: {
    title: "How to find an action",
    steps: ["Choose an assistant to narrow the list.", "Check the outcome beside the action.", "Open action details to see what was requested."],
    link: ["/approvals?status=pending", "See requests waiting for review"],
  },
  action: {
    title: "How to read this record",
    steps: ["Check the assistant, request and outcome.", "If review is still needed, open pending approvals.", "Expand Technical details when investigating an issue."],
  },
  rules: {
    title: "How safety rules work",
    steps: ["An assistant proposes an action.", "AgentGuard checks the rules that apply to that action.", "A matching rule can allow, block or require approval."],
    link: ["/governance", "See recorded decisions"],
  },
  decisions: {
    title: "How to investigate a decision",
    steps: ["Read whether the action was allowed, blocked or sent for review.", "Check the recorded reason when available.", "Open the linked action to see what the assistant requested."],
    link: ["/policies", "See safety rules"],
  },
  performance: {
    title: "How to read a test result",
    steps: ["Choose an assistant to narrow the results.", "Check how many actions the test examined.", "Open results for measures such as accuracy or how often a rule was broken."],
  },
  assistants: {
    title: "How to find an assistant",
    steps: ["Read the description to find the assistant for your task.", "Check whether the assistant is active.", "Open Activity History and select the assistant to see its requests."],
  },
  approvals: {
    title: "How to use the approval queue",
    steps: ["Choose Pending requests to focus on items awaiting a decision.", "Open action details and check the request and its deadline.", "If you have review access, approve it or reject it with a reason."],
  },
  risk: {
    title: "How to read risk results",
    steps: ["Start with the risk level to see which requests may need closer attention.", "Open the assessment details to check the factors behind the score when available.", "Use Approvals to see requests waiting for a decision."],
  },
  audit: {
    title: "How to check who did what",
    steps: ["Find the event you want to investigate.", "Read who or what recorded the event and when it happened.", "Open event details for the underlying record when available."],
  },
  tools: {
    title: "How to read the tool directory",
    steps: ["Find the tool by the action it supports.", "Check its status and sensitivity before investigating how an assistant uses it.", "Open its details to inspect the technical configuration."],
  },
  traces: {
    title: "How to investigate an action with a trace",
    steps: ["Choose a time window or filter for errors.", "Open a trace to see the steps the system recorded.", "Check the duration and errors to find a step that needs investigation."],
  },
  health: {
    title: "How to read system health",
    steps: ["Check the overall status and the time of the last check.", "If the status is unavailable, refresh to try the request again.", "If a service reports a problem, share its name and status with your administrator."],
  },
} satisfies Record<string, { title: string; steps: string[]; link?: [string, string] }>;

export default function PageGuide({ page }: { page: keyof typeof guides }) {
  const guide = guides[page];

  return (
    <details className="rounded-2xl border border-ink/15 bg-cream p-5 open:pb-6">
      <summary className="cursor-pointer font-bold">{guide.title}</summary>
      <ol role="list" className="mt-4 grid gap-3 md:grid-cols-3">
        {guide.steps.map((step, index) => (
          <li key={step} className="flex items-start gap-3 rounded-xl bg-peach/60 p-3 text-sm">
            <span aria-hidden="true" className="grid size-7 shrink-0 place-items-center rounded-full bg-ink font-bold text-cream">
              {index + 1}
            </span>
            <p>{step}</p>
          </li>
        ))}
      </ol>
      {"link" in guide && (
        <Link className="mt-4 inline-block font-semibold underline" to={guide.link[0]}>{guide.link[1]}</Link>
      )}
    </details>
  );
}
