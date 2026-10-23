from opentelemetry import trace


def current_trace_id() -> str | None:
    """32 lowercase hex characters from the active OpenTelemetry span, or None."""
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None
