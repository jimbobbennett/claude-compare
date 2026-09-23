## Key facts
- GenAI semantic conventions define a dedicated agent span set: `create_agent`, `invoke_agent`, and (newer) `invoke_workflow` for orchestrated multi-agent processes (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- Agent span name format: `invoke_agent {gen_ai.agent.name}` when the agent name is readily available; plain `invoke_agent` when it is not (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- `invoke_agent` span kind SHOULD be INTERNAL; `create_agent` span kind SHOULD be CLIENT, as it usually applies to remote agent services (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- Tool execution span name SHOULD be `execute_tool {gen_ai.tool.name}`, span kind INTERNAL (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
- Inference span name SHOULD be `{gen_ai.operation.name} {gen_ai.request.model}`, kind CLIENT, or INTERNAL for in-process models (https://github.com/open-telemetry/semantic-conventions/blob/v1.41.0/docs/gen-ai/gen-ai-spans.md)
- Typical agent trace shape: top-level `invoke_agent` span, child `chat` spans per LLM call, child `execute_tool` spans per tool invocation (https://opentelemetry.io/blog/2026/genai-observability/)
- Prompt/completion content is not captured by default; content capture is opt-in via attributes `gen_ai.system_instructions`, `gen_ai.input.messages`, `gen_ai.output.messages` (https://opentelemetry.io/blog/2026/genai-observability/)
- Tool spans carry `gen_ai.tool.name`, `gen_ai.tool.type`, and `gen_ai.tool.call.id`, linking back to the tool_call_id the model emitted in the preceding chat turn (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)
- `gen_ai.tool.type` enum: function (client-side execution), extension (agent-side call to external API), datastore (retrieval over external data) (https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
- `gen_ai.conversation.id` is conditionally required when the instrumented library has one available or the app supplies one through OTel context (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- `error.type` is conditionally required on agent spans when the operation ends in error; SHOULD be a low-cardinality identifier matching provider error code or exception name (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- All `gen_ai.*` attributes, metrics, events and spans were deprecated in the main semantic-conventions repo and moved to a dedicated GenAI semantic conventions repository (https://github.com/open-telemetry/semantic-conventions/releases)
- MCP `tools/call` spans emit GenAI attributes — `gen_ai.operation.name` = "execute_tool" and `gen_ai.tool.name`; every MCP span carries `mcp.method.name` and `mcp.protocol.version` (https://py.sdk.modelcontextprotocol.io/run/opentelemetry/)
- Open gap: no standard way to express that a specific `execute_tool` span was triggered by a specific LLM inference span; tool spans appear as siblings of the chat span, not children (https://github.com/open-telemetry/semantic-conventions-genai/issues/309)
- `gen_ai.workflow.name` MUST NOT be captured by default when no meaningful low-cardinality name exists; instrumentation-time constants like "StateGraph" are NOT RECOMMENDED (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- Ambiguity flagged in the spec repo: `gen_ai.provider.name` is Required on `invoke_agent` but undefined for framework-emitted spans (LangChain, LangGraph, CrewAI) (https://github.com/open-telemetry/semantic-conventions-genai/issues/178)

## Figures
- `gen_ai.*` namespace status: experimental / in development, not stable (https://raw.githubusercontent.com/open-telemetry/semantic-conventions/main/docs/gen-ai/gen-ai-spans.md)
- v1.36.0 — the cutoff version; instrumentations emitting it or prior SHOULD NOT change emitted convention version by default (https://github.com/open-telemetry/semantic-conventions/blob/v1.41.0/docs/gen-ai/gen-ai-spans.md)
- v1.37 — version from which Datadog Agent Observability natively ingests OTel GenAI spans (https://www.datadoghq.com/blog/llm-otel-semantic-convention/)
- v1.40.0 — cut February 2026 (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)
- Time-to-first-token metric bucket boundaries: [0.001, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0] seconds (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-metrics.md)
- MCP protocol version 2026-07-28 removes the protocol-level handshake and session, breaking assumptions in current MCP conventions built around 2025-06-18 (https://github.com/open-telemetry/semantic-conventions-genai/issues/437)
- Three backends ingesting `gen_ai.*` spans without a translation layer: Datadog LLM Observability, Langfuse, Arize AX/Phoenix (https://dev.to/gabrielanhaia/opentelemetry-genai-semantic-conventions-your-llm-traces-should-look-like-this-in-2026-3ff6)

## Quotes
- "By default, no prompt content or tool arguments are captured with GenAI telemetry, as these can contain sensitive data." — OpenTelemetry project blog (https://opentelemetry.io/blog/2026/genai-observability/)
- "Span name SHOULD be execute_tool {gen_ai.tool.name}. Span kind SHOULD be INTERNAL." — OpenTelemetry GenAI semantic conventions (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
- "The workflow span SHOULD be reported for operations that trigger the execution of composable processes" — OpenTelemetry GenAI agent spans spec (https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)
- "GenAI semantic conventions have no standard way to express that a specific execute_tool span was triggered by a specific LLM inference span." — issue #309, semantic-conventions-genai (https://github.com/open-telemetry/semantic-conventions-genai/issues/309)
- "these attributes can be large, and many observability platforms render them as raw JSON, making them difficult to read" — OpenTelemetry project blog, on message content attributes (https://opentelemetry.io/blog/2026/genai-observability/)

## Suggested sections
- Span taxonomy — `create_agent`, `invoke_agent`, `invoke_workflow`, `chat`/inference, `execute_tool`, MCP spans
- Anatomy of one agent trace — parent/child tree, span kinds, naming templates, cardinality rules
- Required vs recommended attributes — operation name, provider, agent name/id, conversation id, error.type, tool call id
- Content capture and privacy — opt-in message attributes, redaction, payload size, external storage option
- Metrics alongside spans — token usage, operation duration, TTFT buckets, streaming chunk metrics
- Stability and migration — experimental status, repo split, `OTEL_SEMCONV_STABILITY_OPT_IN`, `-v2` packages
- Known gaps — tool-call causality links, provider name on framework spans, MCP protocol drift, backend translation layers

## Terms to define
- Span — single timed operation in a trace, with name, kind, status, attributes
- Span kind — CLIENT / SERVER / INTERNAL / PRODUCER / CONSUMER; signals caller-callee relationship
- Semantic conventions — standardized attribute names and values so telemetry is portable across vendors
- `gen_ai.operation.name` — enum-ish attribute identifying the operation (chat, embeddings, execute_tool, invoke_agent, create_agent)
- Cardinality — number of distinct values an attribute or span name can take; high cardinality breaks aggregation
- OTLP — OpenTelemetry Protocol, wire format for exporting traces/metrics/logs
- OTel Collector — proxy process that receives, processes (redacts, enriches, routes) and exports telemetry
- MCP — Model Context Protocol, standard for exposing tools/resources/prompts to models
- Development/experimental status — spec maturity tier where attribute names may still change
- `OTEL_SEMCONV_STABILITY_OPT_IN` — env var selecting which convention version an instrumentation emits
- Explicit bucket boundaries — fixed histogram bucket edges specified by the convention
- Tool call id — provider-generated identifier correlating a model's requested tool call with its execution
- W3C Trace Context — standard for propagating trace/span ids across process boundaries
- OpenInference — competing/parallel LLM tracing schema used by Arize Phoenix
