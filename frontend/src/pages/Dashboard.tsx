import { motion, useReducedMotion } from "motion/react";
import { useAgents } from "../hooks/useAgents";
import { useOverviewMetrics } from "../hooks/useDashboard";

export default function Dashboard() {
    const reduceMotion = useReducedMotion();

    const agentsQuery = useAgents();
    const overviewQuery = useOverviewMetrics();

    const agents = agentsQuery.data?.items ?? [];
    const overview = overviewQuery.data;

    const fadeUp = (delay: number) => ({
        initial: reduceMotion ? false : { opacity: 0, y: 35 },
        animate: { opacity: 1, y: 0 },
        transition: {
            duration: reduceMotion ? 0 : 0.8,
            delay: reduceMotion ? 0 : delay,
            ease: [0.22, 1, 0.36, 1] as [number, number, number, number],
        },
    });

    const metrics = overview
        ? [
              { label: "Total Actions", value: overview.total_actions },
              { label: "Allowed", value: overview.allow_count },
              { label: "Human Review", value: overview.human_review_count },
              { label: "Blocked", value: overview.block_count },
          ]
        : [];

    return (
        <div className="mx-auto max-w-7xl text-ink">
            <div className="mb-16 flex flex-wrap items-center justify-between gap-4">
                <span className="text-xs font-bold uppercase tracking-[0.25em]">
                    Platform Overview / 01
                </span>

                <span className="rounded-full bg-neon px-4 py-2 text-xs font-bold uppercase">
                    Governance Workspace
                </span>
            </div>

            <section className="mb-20">
                <motion.p
                    {...fadeUp(0)}
                    className="mb-6 text-sm font-semibold uppercase tracking-[0.3em]"
                >
                    Autonomous AI / Governance & Observability
                </motion.p>

                <motion.h1
                    {...fadeUp(0.15)}
                    className="mb-8 text-6xl font-black leading-[0.95] tracking-[-0.07em] md:text-7xl xl:text-8xl"
                >
                    Intelligence.
                    <br />
                    With{" "}
                    <span className="font-medium italic">
                        oversight.
                    </span>
                </motion.h1>

                <motion.p
                    {...fadeUp(0.3)}
                    className="max-w-xl text-lg leading-relaxed text-charcoal md:text-xl"
                >
                    A unified workspace to monitor autonomous AI agents,
                    enforce governance policies, and evaluate every decision.
                </motion.p>
            </section>

            <section>
                <motion.div
                    {...fadeUp(0.4)}
                    className="mb-8 flex flex-wrap items-end justify-between gap-4"
                >
                    <div>
                        <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em]">
                            Your Ecosystem
                        </p>

                        <h2 className="text-4xl font-black tracking-tight md:text-5xl">
                            Meet the agents.
                        </h2>
                    </div>

                    <span className="text-sm font-semibold">
                        {String(agentsQuery.data?.total_items ?? 0).padStart(2, "0")} / Agents
                    </span>
                </motion.div>

                {agentsQuery.isLoading && (
                    <p className="mb-6 text-sm text-charcoal/70" role="status">
                        Loading agents...
                    </p>
                )}

                {agentsQuery.isError && (
                    <div className="mb-6 rounded-[24px] bg-cream p-6">
                        <p className="mb-4 text-sm font-semibold">
                            Unable to load agents.
                        </p>
                        <button
                            type="button"
                            onClick={() => void agentsQuery.refetch()}
                            className="rounded-full bg-ink px-5 py-2 text-sm font-semibold text-cream"
                        >
                            Try again
                        </button>
                    </div>
                )}

                {!agentsQuery.isLoading &&
                    !agentsQuery.isError &&
                    agents.length === 0 && (
                        <p className="mb-6 text-sm text-charcoal/70">
                            No registered agents found.
                        </p>
                    )}

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                    {agents.map((agent, index) => {
                        const dark = index % 2 === 0;

                        return (
                            <motion.article
                                key={agent.agent_id}
                                {...fadeUp(0.5 + index * 0.15)}
                                whileHover={
                                    reduceMotion ? undefined : { y: -8 }
                                }
                                className={
                                    dark
                                        ? "flex min-h-72 flex-col justify-between rounded-[28px] bg-ink p-8 text-cream md:p-10"
                                        : "flex min-h-72 flex-col justify-between rounded-[28px] border border-ink/10 bg-cream p-8 text-ink md:p-10"
                                }
                            >
                                <div className="flex items-center justify-between">
                                    <span className="text-xs uppercase tracking-widest">
                                        Agent / {String(index + 1).padStart(3, "0")}
                                    </span>

                                    <span
                                        className={
                                            dark
                                                ? "text-3xl text-neon"
                                                : "text-3xl"
                                        }
                                        aria-hidden="true"
                                    >
                                        ↗
                                    </span>
                                </div>

                                <div>
                                    <h3 className="mb-3 text-4xl font-bold tracking-tight">
                                        {agent.agent_name}
                                    </h3>

                                    <p
                                        className={
                                            dark
                                                ? "text-sm text-cream/70"
                                                : "text-sm text-charcoal/70"
                                        }
                                    >
                                        {agent.description ??
                                            "No description provided."}
                                    </p>
                                </div>
                            </motion.article>
                        );
                    })}
                </div>
            </section>

            <section className="mt-20">
                <motion.div {...fadeUp(0.7)}>
                    <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em]">
                        Governance Activity
                    </p>

                    <h2 className="mb-8 text-4xl font-black tracking-tight md:text-5xl">
                        At a glance.
                    </h2>
                </motion.div>

                {overviewQuery.isLoading && (
                    <p className="text-sm text-charcoal/70" role="status">
                        Loading governance metrics...
                    </p>
                )}

                {overviewQuery.isError && (
                    <div className="rounded-[24px] bg-cream p-6">
                        <p className="mb-4 text-sm font-semibold">
                            Unable to load governance metrics.
                        </p>
                        <button
                            type="button"
                            onClick={() => void overviewQuery.refetch()}
                            className="rounded-full bg-ink px-5 py-2 text-sm font-semibold text-cream"
                        >
                            Try again
                        </button>
                    </div>
                )}

                {overview && (
                    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                        {metrics.map((metric, index) => (
                            <motion.article
                                key={metric.label}
                                {...fadeUp(0.8 + index * 0.1)}
                                className="rounded-[24px] border border-ink/10 bg-cream p-6 md:p-8"
                            >
                                <p className="mb-5 text-xs font-bold uppercase tracking-[0.2em]">
                                    {metric.label}
                                </p>

                                <p className="text-5xl font-black tracking-tight">
                                    {metric.value}
                                </p>
                            </motion.article>
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
}
