type ErrorStateProps = {
  title?: string;
  message?: string;
  errorCode?: string;
  onRetry?: () => void;
};

export default function ErrorState({
  title = "Telemetry & API Request Failed",
  message = "An unexpected error occurred while communicating with the governance service.",
  errorCode,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="rounded-3xl border-2 border-[#111111] bg-[#FFB5A7]/30 p-8 text-[#111111] shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="inline-block rounded-full bg-red-600 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-white">
            {errorCode || "ERROR"}
          </span>
          <h3 className="mt-3 text-2xl font-black tracking-tight">{title}</h3>
        </div>

        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="cursor-pointer rounded-full bg-[#111111] px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-[#F5F87A] transition hover:bg-[#1A1A1A] hover:scale-105 active:scale-95"
          >
            Retry Request
          </button>
        )}
      </div>

      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#1A1A1A]">
        {message}
      </p>
    </div>
  );
}
