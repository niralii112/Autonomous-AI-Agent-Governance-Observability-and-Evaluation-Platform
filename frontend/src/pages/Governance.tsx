
import { motion, useReducedMotion } from "motion/react";
import {
    usePolicies,
    useGovernanceDecisions,
} from "../hooks/usePolicies";

const decisions = [
    {
        name: "ALLOW",
        description: "Actions that satisfy governance requirements.",
        color: "bg-neon",
    },
    {
        name: "HUMAN_REVIEW",
        description: "Actions requiring approval before execution.",
        color: "bg-cream",
    },
    {
        name: "BLOCK",
        description: "Actions rejected by governance policies.",
        color: "bg-ink text-cream",
    },
];

export default function Governance() {
    const reduceMotion = useReducedMotion();

    const policiesQuery = usePolicies();
    const decisionsQuery = useGovernanceDecisions();

    const policies = policiesQuery.data?.items ?? [];
    const governanceDecisions = decisionsQuery.data?.items ?? [];

    return (
        <div className="mx-auto max-w-7xl text-ink">
            <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduceMotion ? 0 : 0.7 }}
            >
                <p className="mb-6 text-xs font-bold uppercase tracking-[0.3em]">
                    Platform / Governance
                </p>

                <h1 className="mb-6 text-6xl font-black leading-[0.95] tracking-[-0.06em] md:text-7xl">
                    Built for
                    <br />
                    <span className="font-medium italic">accountability.</span>
                </h1>

                <p className="mb-16 max-w-2xl text-lg leading-relaxed">
                    Understand how autonomous agent actions are governed,
                    reviewed, and controlled through clearly defined policies.
                </p>
            </motion.div>

            <section>
                <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em]">
                            Decision Framework
                        </p>

                        <h2 className="text-4xl font-black tracking-tight">
                            Three possible outcomes.
                        </h2>
                    </div>

                    <span className="text-sm font-semibold">
                        03 / Decisions
                    </span>
                </div>

                <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                    {decisions.map((decision, index) => (
                        <motion.article
                            key={decision.name}
                            initial={reduceMotion ? false : { opacity: 0, y: 35 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{
                                duration: reduceMotion ? 0 : 0.7,
                                delay: reduceMotion ? 0 : index * 0.15,
                            }}
                            whileHover={reduceMotion ? undefined : { y: -6 }}
                            className={`flex min-h-64 flex-col justify-between rounded-[28px] p-8 ${decision.color}`}
                        >
                            <span className="text-xs font-bold tracking-[0.2em]">
                                OUTCOME / 0{index + 1}
                            </span>

                            <div>
                                <h3 className="mb-4 break-words text-2xl font-black tracking-tight">
                                    {decision.name}
                                </h3>

                                <p className="text-sm leading-relaxed opacity-75">
                                    {decision.description}
                                </p>
                            </div>
                        </motion.article>
                    ))}
                </div>
            </section>

            {/* Registered policies */}
            <section className="mt-20">
                <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em]">
                    Policy Registry
                </p>

                <h2 className="mb-8 text-4xl font-black tracking-tight md:text-5xl">
                    Rules with purpose.
                </h2>

                {policiesQuery.isPending && (
                    <p className="text-sm text-charcoal/70">
                        Loading governance policies...
                    </p>
                )}

                {policiesQuery.isError && (
                    <div className="rounded-[24px] bg-cream p-6">
                        <p className="mb-4 text-sm font-semibold">
                            Unable to load governance policies.
                        </p>

                        <button
                            type="button"
                            onClick={() => void policiesQuery.refetch()}
                            className="rounded-full bg-ink px-5 py-2 text-sm font-semibold text-cream"
                        >
                            Try again
                        </button>
                    </div>
                )}

                {policiesQuery.isSuccess && policies.length === 0 && (
                    <p className="text-sm text-charcoal/70">
                        No governance policies registered yet.
                    </p>
                )}

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                    {policies.map((policy, index) => (
                        <motion.article
                            key={policy.policy_id}
                            initial={reduceMotion ? false : { opacity: 0, y: 30 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{
                                duration: reduceMotion ? 0 : 0.7,
                                delay: reduceMotion ? 0 : index * 0.1,
                            }}
                            className="flex min-h-64 flex-col justify-between rounded-[28px] border border-ink/10 bg-cream p-8"
                        >
                            <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
                                <span className="text-xs font-bold uppercase tracking-[0.2em]">
                                    Policy / v{policy.version}
                                </span>

                                <span className="rounded-full border border-ink/20 px-3 py-1 text-xs font-bold">
                                    {policy.is_active ? "ACTIVE" : "INACTIVE"}
                                </span>
                            </div>

                            <div>
                                <h3 className="mb-3 text-2xl font-black tracking-tight">
                                    {policy.name}
                                </h3>

                                <p className="mb-5 text-sm leading-relaxed text-charcoal/70">
                                    {policy.description ?? "No description provided."}
                                </p>

                                <div className="flex flex-wrap gap-3 text-xs font-bold uppercase tracking-wider">
                                    <span>Effect: {policy.effect.replaceAll("_", " ")}</span>
                                    <span>Priority: {policy.priority}</span>
                                </div>
                            </div>
                        </motion.article>
                    ))}
                </div>
            </section>

            {/* Recent governance decisions */}
            <section className="mt-20">
                <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em]">
                    Decision History
                </p>

                <h2 className="mb-8 text-4xl font-black tracking-tight md:text-5xl">
                    Every decision matters.
                </h2>

                {decisionsQuery.isPending && (
                    <p className="text-sm text-charcoal/70">
                        Loading governance decisions...
                    </p>
                )}

                {decisionsQuery.isError && (
                    <div className="rounded-[24px] bg-cream p-6">
                        <p className="mb-4 text-sm font-semibold">
                            Unable to load governance decisions.
                        </p>

                        <button
                            type="button"
                            onClick={() => void decisionsQuery.refetch()}
                            className="rounded-full bg-ink px-5 py-2 text-sm font-semibold text-cream"
                        >
                            Try again
                        </button>
                    </div>
                )}

                {decisionsQuery.isSuccess &&
                    governanceDecisions.length === 0 && (
                        <p className="text-sm text-charcoal/70">
                            No governance decisions recorded yet.
                        </p>
                    )}

                <div className="space-y-4">
                    {governanceDecisions.map((decision) => (
                        <article
                            key={decision.governance_decision_id}
                            className="flex flex-wrap items-center justify-between gap-5 rounded-[24px] border border-ink/10 bg-cream p-6 md:p-8"
                        >
                            <div>
                                <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-charcoal/70">
                                    Governance Decision
                                </p>

                                <h3 className="text-xl font-black tracking-tight">
                                    {decision.final_decision.replaceAll("_", " ")}
                                </h3>

                                <p className="mt-2 break-all text-xs text-charcoal/70">
                                    Action: {decision.action_id}
                                </p>
                            </div>

                            <div className="text-sm">
                                <p className="font-semibold">
                                    {decision.decision_reason_code}
                                </p>

                                <p className="mt-2 text-charcoal/70">
                                    {new Date(decision.decided_at).toLocaleString()}
                                </p>
                            </div>
                        </article>
                    ))}
                </div>
            </section>
        </div>
    );
}
