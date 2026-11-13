import { useState } from "react";
import { Link } from "react-router-dom";

const slides = [
  {
    title: "Find a request to review",
    example: "Anushka, a finance reviewer, opens Pending approvals and selects a proposed payment.",
    instruction: "Start here when an assistant needs someone to decide whether a request can proceed.",
    photo: "request-review.jpg",
    alt: "A person reviewing a printed request at a desk",
    to: "/approvals?status=pending",
    link: "Open pending approvals",
  },
  {
    title: "Check what the assistant requested",
    example: "Anushka opens View action details and checks the recipient, amount, and recorded reason when available.",
    instruction: "For example, compare a proposed payment with the invoice before making a decision.",
    to: "/actions",
    link: "Open activity history",
  },
  {
    title: "Record a decision",
    example: "Anushka returns to Approvals. She can approve the request or reject it with a reason.",
    instruction: "Reviewers and administrators can make decisions. Anyone with read access can check the recorded status.",
    to: "/approvals",
    link: "Open approvals",
  },
  {
    title: "Understand why review was needed",
    example: "Anushka opens AI Decisions to read the recorded reason and follow the link back to the action.",
    instruction: "Use Safety Rules to see which actions can proceed, are blocked, or need approval.",
    to: "/governance",
    link: "Open AI Decisions",
  },
  {
    title: "Check the workspace",
    example: "If a page cannot load its results, Anushka checks System Health for the latest reported service status.",
    instruction: "Share the affected service and the time of the check with your administrator if the issue continues.",
    photo: "system-health.jpg",
    alt: "Network equipment with service indicator lights",
    to: "/settings",
    link: "Open System Health",
  },
];

export default function OverviewWalkthrough() {
  const [index, setIndex] = useState(0);
  const slide = slides[index];

  return (
    <section aria-labelledby="walkthrough-title" className="overflow-hidden rounded-3xl border border-ink/15 bg-cream">
      <div className="px-5 pt-5 md:px-7 md:pt-7">
        <h2 id="walkthrough-title" className="text-2xl font-bold">How to use AgentGuard</h2>
        <p className="mt-1 text-sm text-charcoal">Follow an example payment request at your own pace.</p>
      </div>

      <div aria-live="polite" aria-atomic="true" className="grid gap-5 px-5 py-5 md:grid-cols-2 md:px-7">
        <div className="flex min-h-48 flex-col justify-center">
          <p className="text-sm font-semibold">Step {index + 1} of {slides.length}</p>
          <h3 className="mt-2 text-xl font-bold">{slide.title}</h3>
          <p className="mt-2">{slide.example}</p>
          <p className="mt-2 text-sm text-charcoal">{slide.instruction}</p>
          <Link to={slide.to} className="mt-4 self-start font-semibold underline">{slide.link}</Link>
        </div>
        {slide.photo ? (
          <img src={import.meta.env.BASE_URL + slide.photo} alt={slide.alt} width={720} height={480}
            className="h-48 w-full rounded-xl object-cover md:h-full md:max-h-64" />
        ) : (
          <ol role="list" aria-label="Review workflow" className="grid content-center gap-2 rounded-xl bg-peach/60 p-4">
            {["Find a request", "Check the details", "Record a decision", "Read the outcome"].map((step, position) => (
              <li key={step} aria-current={position === index ? "step" : undefined}
                className={position === index ? "rounded-lg bg-ink px-3 py-2 font-semibold text-cream" : "px-3 py-2"}>
                {step}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="flex justify-between gap-3 border-t border-ink/10 px-5 py-4 md:px-7">
        <button type="button" disabled={index === 0} onClick={() => setIndex(index - 1)}
          className="rounded-full border border-ink/25 px-4 py-2 font-semibold disabled:opacity-40">Previous</button>
        <button type="button" disabled={index === slides.length - 1} onClick={() => setIndex(index + 1)}
          className="rounded-full bg-neon px-4 py-2 font-semibold disabled:opacity-40">Next</button>
      </div>
    </section>
  );
}
