import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: string;
};

export default function EmptyState({
  title,
  description,
  action,
  icon = "∅",
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-[#111111]/15 bg-[#FFF8F2] p-12 text-center text-[#111111]">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[#FFE3CE] text-2xl font-bold">
        {icon}
      </div>

      <h3 className="mb-2 text-xl font-bold tracking-tight">{title}</h3>
      <p className="max-w-md text-sm leading-relaxed text-[#555555]">
        {description}
      </p>

      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
