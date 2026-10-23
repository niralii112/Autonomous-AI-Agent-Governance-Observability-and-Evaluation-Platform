import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#FFE3CE] p-6 text-center text-[#111111]">
      <div className="rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-12 shadow-2xl max-w-md w-full">
        <span className="rounded-full bg-red-600 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-white">
          404 ERROR
        </span>
        <h1 className="mt-4 text-6xl font-black tracking-tight">404</h1>
        <h2 className="mt-2 text-2xl font-black tracking-tight">Page Not Found</h2>
        <p className="mt-3 text-xs text-[#555555] leading-relaxed">
          The requested governance view or telemetry resource does not exist or has been relocated.
        </p>

        <div className="mt-8">
          <Link
            to="/"
            className="inline-block rounded-full bg-[#111111] px-6 py-3 text-xs font-black uppercase tracking-wider text-[#F5F87A] hover:bg-[#1A1A1A] transition"
          >
            Return to Dashboard →
          </Link>
        </div>
      </div>
    </div>
  );
}
