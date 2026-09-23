## Key facts
- OpenTelemetry's GenAI semantic conventions specify that an LLM client span name SHOULD be `{gen_ai.operation.name} {gen_ai.request.model}` (https://github.com/open-telemetry/semantic-conventions/blob/v1.41.0/docs/gen-ai/gen-ai-spans.md)
- `gen_ai.operation.name` and provider name are the required attributes; model, token usage and finish reasons are the other core fields (https://github.com/open-telemetry/semantic-conventions/blob/v1.41.0/docs/gen-ai/gen-ai-spans.md)
- Capture of full prompt/completion content in GenAI spans is opt-in, not default (https://opentelemetry.io/blog/2026/genai-observability/)
- The `gen_ai.*` namespace is still marked experimental / in development in the semantic-conventions repo (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)
- Baseline OTel Python trace setup is: `Resource` with `SERVICE_NAME` → `TracerProvider` → `BatchSpanProcessor(OTLPSpanExporter(endpoint="<endpoint>/v1/traces"))` → `trace.set_tracer_provider()` (https://opentelemetry.io/docs/languages/python/exporters/)
- OpenLLMetry is an open-source OpenTelemetry extension for LLM apps, Apache 2.0, Python-first, exportable to Datadog, New Relic, Sentry, Honeycomb (https://www.traceloop.com/blog/openllmetry)
- Traceloop SDK instrumentation is two calls: `pip install traceloop-sdk`, then `Traceloop.init(app_name=...)`, with optional `@workflow` decorators (https://github.com/traceloop/openllmetry/blob/main/packages/traceloop-sdk/README.md)
- Traceloop SDK init options take precedence over environment variables; individual instrumentations can be allow-listed or blocked via `instruments=` / `block_instruments=` (https://www.traceloop.com/docs/openllmetry/configuration)
- Langfuse Python SDK v4 is built on OpenTelemetry; entry points are `get_client()`, `start_as_current_observation()` and the `@observe` decorator (https://github.com/langfuse/langfuse-python)
- The legacy Langfuse v2 client API (`trace()`, `span()`, `generation()`) is deprecated for new instrumentation (https://github.com/langfuse/langfuse-python)
- Langfuse's `@observe` decorator uses Python `contextvars` for async-safe state; the outermost decorated function creates the trace, inner ones become nested spans (https://langfuse.com/blog/2024-04-python-decorator)
- LangSmith tracing for LangChain/LangGraph apps can be enabled with a single environment variable; `LANGSMITH_PROJECT` routes traces to a named project (https://docs.langchain.com/langsmith/observability-quickstart)
- Arize Phoenix tracing starts with `from phoenix.otel import register` and `register(project_name=..., auto_instrument=True)`, which auto-instruments based on installed dependencies (https://arize.com/docs/phoenix/tracing/llm-traces-1/quickstart-tracing-python)
- Phoenix auto-instrumentation is delivered as per-library OpenInference packages, e.g. `openinference-instrumentation-openai`, `openinference-instrumentation-crewai` (https://arize.com/docs/phoenix/get-started/get-started-tracing)
- Phoenix is open-source and self-hosted, vendor- and language-agnostic, with out-of-the-box support for OpenAI Agents SDK, LangGraph, CrewAI, LlamaIndex, DSPy (https://github.com/arize-ai/phoenix)

## Figures
- Local Phoenix collector endpoint default: `http://localhost:6006` via `PHOENIX_COLLECTOR_ENDPOINT` (https://arize.com/docs/phoenix/get-started/get-started-tracing)
- Semantic-conventions release referenced for current GenAI span spec: v1.41.0 (https://github.com/open-telemetry/semantic-conventions/blob/v1.41.0/docs/gen-ai/gen-ai-spans.md)
- semantic-conventions v1.40.0 cut February 2026; core GenAI attributes stable in shape since v1.37.0 (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)
- Two standardized GenAI metric instruments: `gen_ai.client.token.usage` and `gen_ai.client.operation.duration` (https://openobserve.ai/blog/opentelemetry-genai-semantic-conventions/)
- Traceloop default OTLP destination: `https://api.traceloop.com`; http/https prefix selects OTLP/HTTP, otherwise gRPC (https://www.traceloop.com/docs/openllmetry/configuration)
- Langfuse OTLP ingestion path: `/api/public/otel` (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)
- Langfuse LangChain CallbackHandler requires `langchain ^0.1.10`; older callback interface versions unsupported (https://langfuse.com/integrations/frameworks/langchain)
- OpenLLMetry Qdrant instrumentation requires `qdrant-client` 1.7.3 or above (https://qdrant.tech/documentation/observability/openllmetry/)
- Example OTLP gRPC exporter batching config: `max_queue_size=1000`, `max_export_batch_size=100`, `schedule_delay_millis=1000` (https://launchdarkly.com/docs/tutorials/the-complete-guide-to-python-and-opentelemetry)
- Datadog LLM Observability consumes `gen_ai.*` spans natively from v1.37+ (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)

## Quotes
- "Tracing is done in a non-intrusive way, built on top of OpenTelemetry." — Traceloop SDK README, Traceloop (https://github.com/traceloop/openllmetry/blob/main/packages/traceloop-sdk/README.md)
- "we created the @observe() decorator for Langfuse to make tracing your Python code as simple as possible" — Langfuse engineering blog (https://langfuse.com/blog/2024-04-python-decorator)
- "The legacy v2 client API ... is deprecated. Do not use it for new instrumentation." — Langfuse Python SDK README, Langfuse (https://github.com/langfuse/langfuse-python)
- "They standardize how GenAI operations are recorded" — OpenTelemetry project blog, on the GenAI semantic conventions (https://opentelemetry.io/blog/2026/genai-observability/)
- "a complete record of every step that ran during a request" — LangSmith observability quickstart, LangChain, defining a trace (https://docs.langchain.com/langsmith/observability-quickstart)
- "the exact problem OpenTelemetry's GenAI semantic conventions exist to solve" — OpenObserve, on inconsistent attribute naming (https://openobserve.ai/blog/opentelemetry-genai-semantic-conventions/)

## Suggested sections
- Trace anatomy — trace vs span vs nested generation; what one LLM request looks like as a span tree
- Minimum viable setup — pip installs, env vars, tracer provider registration, one decorated function
- Auto vs manual instrumentation — library auto-instrumentors vs hand-rolled spans; when each applies
- Semantic conventions — `gen_ai.*` attribute names, span naming rule, experimental status, version pinning
- Backend choice — self-hosted Phoenix, Langfuse, LangSmith, generic OTLP collector; portability trade-offs
- Content capture and PII — opt-in prompt/completion recording, redaction, opt-out flags
- Production concerns — batching, flush on short-lived processes/serverless, sampling, async and thread context propagation

## Terms to define
- Span — single timed unit of work with attributes; the node in a trace
- Trace — tree of causally linked spans for one end-to-end request
- OTLP — OpenTelemetry Protocol; wire format for shipping telemetry over gRPC or HTTP
- TracerProvider — SDK object that creates tracers and holds exporter/processor config
- BatchSpanProcessor — buffers finished spans and exports them in batches rather than one by one
- Semantic conventions — agreed attribute names so spans from different libraries are queryable together
- Auto-instrumentation — patching of library call sites so spans are emitted without app code changes
- OpenInference — Arize's span convention/instrumentation suite for LLM calls, layered on OpenTelemetry
- Generation (observation type) — vendor-specific span subtype representing a model call with prompt, completion, token counts
- contextvars — Python stdlib mechanism for per-task state; how async-safe parent-span tracking works
- Flush — forcing buffered spans out before process exit, needed in scripts and serverless
- Sampling — dropping a share of traces to control volume and cost
- Collector — standalone OTel process that receives, transforms and fans out telemetry to backends
