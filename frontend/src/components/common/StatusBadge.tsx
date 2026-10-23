type StatusType =
  | "OK"
  | "ERROR"
  | "UNSET"
  | "PASS"
  | "FAIL"
  | "REVIEW"
  | "ALLOW"
  | "BLOCK"
  | "HUMAN_REVIEW"
  | "ACTIVE"
  | "INACTIVE"
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "HEALTHY"
  | "DEGRADED"
  | "UNHEALTHY"
  | string;

type StatusBadgeProps = {
  status: StatusType;
  label?: string;
  size?: "sm" | "md";
};

export default function StatusBadge({
  status,
  label,
  size = "md",
}: StatusBadgeProps) {
  const norm = String(status || "").toUpperCase();
  const display = label || norm;

  let bg = "bg-[#111111]/10 text-[#111111]";

  switch (norm) {
    case "OK":
    case "PASS":
    case "ALLOW":
    case "APPROVED":
    case "ACTIVE":
    case "HEALTHY":
      bg = "bg-[#B8F5CE] text-[#0A4D27]";
      break;
    case "ERROR":
    case "FAIL":
    case "BLOCK":
    case "REJECTED":
    case "UNHEALTHY":
      bg = "bg-[#FFB5A7] text-[#601407]";
      break;
    case "REVIEW":
    case "HUMAN_REVIEW":
    case "PENDING":
    case "DEGRADED":
      bg = "bg-[#F5F87A] text-[#111111]";
      break;
    case "INACTIVE":
    case "UNSET":
      bg = "bg-[#E5E5E5] text-[#555555]";
      break;
    default:
      bg = "bg-[#FFE3CE] text-[#111111]";
  }

  const sizeClasses =
    size === "sm"
      ? "px-2.5 py-0.5 text-[10px]"
      : "px-3.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center rounded-full font-black tracking-wider uppercase ${sizeClasses} ${bg}`}
    >
      {display}
    </span>
  );
}
