import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
  fallback?: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  error: Error | null;
};

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="m-8 rounded-3xl border-2 border-[#111111] bg-[#FFF8F2] p-8 text-[#111111] shadow-lg">
          <span className="rounded-full bg-red-600 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-white">
            RUNTIME EXCEPTION
          </span>
          <h2 className="mt-4 text-3xl font-black tracking-tight">
            Something went wrong
          </h2>
          <p className="mt-2 text-sm text-[#555555]">
            An unexpected error occurred in this view.
          </p>
          {this.state.error && (
            <pre className="mt-4 overflow-x-auto rounded-xl bg-[#111111] p-4 text-xs font-mono text-[#F5F87A]">
              {this.state.error.message}
            </pre>
          )}
          <button
            type="button"
            onClick={this.handleReset}
            className="mt-6 cursor-pointer rounded-full bg-[#F5F87A] px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-[#111111] hover:bg-[#FFE3CE] transition"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
