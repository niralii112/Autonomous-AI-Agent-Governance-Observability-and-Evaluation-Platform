import { motion } from "motion/react";

type LoadingStateProps = {
  message?: string;
  lines?: number;
};

export default function LoadingState({
  message = "Loading platform data...",
  lines = 3,
}: LoadingStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <motion.div
        animate={{
          scale: [1, 1.15, 1],
          opacity: [0.6, 1, 0.6],
        }}
        transition={{
          duration: 1.6,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F5F87A] text-[#111111] shadow-md"
      >
        <span className="text-xl font-black">AI</span>
      </motion.div>

      <p className="mb-4 text-xs font-bold uppercase tracking-[0.25em] text-[#111111]">
        {message}
      </p>

      <div className="w-full max-w-md space-y-3">
        {Array.from({ length: lines }).map((_, index) => (
          <div
            key={index}
            className="h-4 animate-pulse rounded-full bg-[#111111]/10"
            style={{
              width: `${100 - index * 15}%`,
              margin: "0 auto",
            }}
          />
        ))}
      </div>
    </div>
  );
}
