"""Arize AX tracing setup.

Call ``init_tracing()`` before the first Anthropic client is constructed, so
instrumentation is in place for every model call.

The Anthropic instrumentor produces the LLM span -- model, messages and token
counts are captured natively, so none of that is hand-rolled. Each post also
gets a CHAIN span carrying the run's identity and the computed cost (the
Messages API returns no cost, so the instrumentor cannot supply one).

Note the pinned ``anthropic==1.7.0``: instrumentor 2.1.5 imports
``anthropic._utils._transform``, which exists in 1.7.0 but was renamed by
1.8.0, where ``.instrument()`` raises ModuleNotFoundError. Raising the
Anthropic pin means re-checking that import first.
"""

from __future__ import annotations

import os

from openinference.instrumentation import OITracer, TraceConfig

# This experiment gets its own project. ARIZE_PROJECT_NAME is commonly set in
# the shell for something else entirely (e.g. Claude Code's own tracing), and
# load_dotenv() does not override an existing shell var -- so inheriting it
# would silently mix blog-writer spans into an unrelated project. Override with
# BLOGWRITER_PROJECT_NAME when you want a different one.
DEFAULT_PROJECT_NAME = "claude-compare-blogwriter"

_tracer_provider = None
_tracer: OITracer | None = None


def project_name() -> str:
    return os.environ.get("BLOGWRITER_PROJECT_NAME") or DEFAULT_PROJECT_NAME


class TracingConfigError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise TracingConfigError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


def init_tracing():
    """Register the Arize exporter and instrument the Agent SDK.

    Idempotent: the batch runner calls this once, but a double call must not
    double-instrument and duplicate every span.
    """
    global _tracer_provider, _tracer
    if _tracer_provider is not None:
        return _tracer_provider

    from arize.otel import register
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    kwargs = {
        "space_id": _require_env("ARIZE_SPACE_ID"),
        "api_key": _require_env("ARIZE_API_KEY"),
        # Required. Without a project name the collector returns HTTP 500;
        # service.name alone is not enough.
        "project_name": project_name(),
    }
    # Only non-US Arize accounts need an explicit endpoint; don't assume US.
    endpoint = os.environ.get("ARIZE_COLLECTOR_ENDPOINT")
    if endpoint:
        kwargs["endpoint"] = endpoint

    _tracer_provider = register(**kwargs)
    AnthropicInstrumentor().instrument(tracer_provider=_tracer_provider)
    # The evaluator's judge runs on OpenAI, so its calls are traced too.
    OpenAIInstrumentor().instrument(tracer_provider=_tracer_provider)
    _tracer = OITracer(
        _tracer_provider.get_tracer(__name__), config=TraceConfig()
    )
    return _tracer_provider


def get_tracer() -> OITracer:
    if _tracer is None:
        raise TracingConfigError("init_tracing() must be called first")
    return _tracer


def shutdown_tracing() -> None:
    """Flush and shut down. Without this a short-lived CLI drops its spans."""
    global _tracer_provider, _tracer
    if _tracer_provider is None:
        return
    try:
        _tracer_provider.force_flush()
    finally:
        _tracer_provider.shutdown()
        _tracer_provider = None
        _tracer = None
