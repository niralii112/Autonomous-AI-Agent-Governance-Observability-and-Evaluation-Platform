import { motion, useReducedMotion } from "motion/react";
import { useAgents } from "../hooks/useAgents";

export default function Agents() {
    const reduceMotion = useReducedMotion();
    const { data, isLoading, isError, error, refetch } = useAgents();

    const agents = data?.items ?? [];

    return (
        <div className="mx-auto max-w-7xl text-ink">
            <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7 }}
            >
                <p className="mb-6 text-xs font-bold uppercase tracking-[0.3em]">
                    Platform / Agent Registry
                </p>

                <h1 className="mb-6 text-6xl font-black leading-[0.95] tracking-[-0.06em] md:text-7xl">
                    Meet your
                    <br />
                    <span className="font-medium italic">AI agents.</span>
                </h1>

                <p className="mb-16 max-w-2xl text-lg leading-relaxed">
                    Explore the autonomous agents operating within your
                    governance and observability platform.
                </p>
            </motion.div>

            {isLoading && (
                <p className="mb-8 text-sm text-charcoal/70" role="status">
                    Loading registered agents...
                </p>
            )}

            {isError && (
                <div className="mb-8 rounded-[24px] border border-ink/10 bg-cream p-8">
                    <p className="mb-4 text-sm font-semibold">
                        Unable to load registered agents.
                    </p>

                    <p className="mb-6 text-sm text-charcoal/70">
                        {error instanceof Error
                            ? error.message
                            : "An unexpected error occurred."}
                    </p>

                    <button
                        type="button"
                        onClick={() => void refetch()}
                        className="rounded-full bg-ink px-6 py-3 text-sm font-semibold text-cream"
                    >
                        Try again
                    </button>
                </div>
            )}

            {!isLoading && !isError && agents.length === 0 && (
                <p className="mb-8 text-sm text-charcoal/70">
                    No registered agents found.
                </p>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {agents.map((agent, index) => {
                    const isDark = index % 2 === 0;

                    const background = isDark ? "bg-ink" : "bg-cream";
                    const text = isDark ? "text-cream" : "text-ink";
                    const accent = isDark ? "text-neon" : "text-ink";

                    const category = agent.agent_category
                        .replaceAll("_", " ");

                    return (
                        <motion.article
                            key={agent.agent_id}
                            initial={
                                reduceMotion
                                    ? false
                                    : { opacity: 0, y: 40 }
                            }
                            animate={{ opacity: 1, y: 0 }}
                            transition={{
                                duration: 0.7,
                                delay: reduceMotion ? 0 : index * 0.15,
                            }}
                            whileHover={
                                reduceMotion ? undefined : { y: -8 }
                            }
                            className={`flex min-h-96 flex-col justify-between rounded-[30px] p-8 md:p-10 ${background} ${text}`}
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold tracking-[0.2em]">
                                    AGENT / {String(index + 1).padStart(3, "0")}
                                </span>

                                <span
                                    className={`text-3xl ${accent}`}
                                    aria-hidden="true"
                                >
                                    ↗
                                </span>
                            </div>

                            <div>
                                <p className="mb-4 text-xs font-semibold tracking-[0.2em]">
                                    {category}
                                </p>

                                <h2 className="mb-5 text-4xl font-black tracking-tight md:text-5xl">
                                    {agent.agent_name}
                                </h2>

                                <p className="max-w-sm text-sm leading-relaxed opacity-75">
                                    {agent.description ??
                                        "No description provided."}
                                </p>

                                <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] opacity-75">
                                    {agent.agent_status} / Trust Tier {agent.trust_tier}
                                </p>
                            </div>
                        </motion.article>
                    );
                })}
            </div>
        </div>
    );
}
