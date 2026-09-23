"""The model call, and Stage B -- the measured step.

Writing a post from a frozen brief is one LLM call: no tools, no loop, no
filesystem. So this talks to the Messages API directly rather than wrapping an
agent harness around a single request. That removes confounds rather than
adding them -- there is no subprocess to inherit config or environment from,
and effort is set explicitly on the request. Spans are emitted explicitly (see
tracing.py for why the auto-instrumentor is not used).

See ``request_kwargs`` for the reasoning behind each parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
from openinference.instrumentation import using_metadata
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace as otel_trace

from .determinism import (
    capture_versions,
    load_verified_brief,
    sha256_text,
)
from .models import estimate_cost
from .prompts import (
    WRITER_PROMPT_VERSION,
    WRITER_SYSTEM,
    build_writer_prompt,
)
from .tracing import get_tracer

# Generous, because thinking tokens count toward max_tokens and adaptive
# thinking is always on for Opus 5.5. A ~1200-word post is ~2k output tokens;
# the rest is headroom so a long think can never truncate the post.
MAX_TOKENS = 32000

_client: anthropic.Anthropic | None = None


class ModelCallError(RuntimeError):
    pass


class RefusalError(RuntimeError):
    """The model declined the request (``stop_reason == "refusal"``).

    Deliberately fatal. Anthropic's general guidance is to enable server-side
    fallbacks so a refusal retries on another model -- but that is exactly the
    wrong behaviour here: a post silently written by a fallback model would be
    mislabelled, which is the one outcome this harness must never produce.
    """


class ModelSubstitutionError(RuntimeError):
    """The response came back from a model other than the one requested."""


def get_client() -> anthropic.Anthropic:
    """The client is created lazily so tracing is instrumented first."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


@dataclass
class ModelCall:
    """One model call's output plus everything worth recording."""

    text: str
    model_id: str
    effort: str
    # The model named in the response. Checked against model_id, never assumed.
    served_model: str | None = None
    stop_reason: str | None = None
    # Full prompt count: uncached + cache-read + cache-write. usage's
    # input_tokens counts only the uncached part.
    input_tokens: int | None = None
    uncached_input_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    output_tokens: int | None = None
    # Opus 5.5 thinks more per turn at a given effort, so this is a comparison
    # metric in its own right.
    thinking_tokens: int | None = None
    total_tokens: int | None = None
    web_search_requests: int | None = None
    # Computed from token counts; the Messages API returns no cost.
    cost_usd: float | None = None
    turns: int = 1
    tools_used: list[str] = field(default_factory=list)


def request_kwargs(
    *,
    model_id: str,
    effort: str,
    system_prompt: str,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the request with every drift source pinned.

    - ``output_config.effort`` is explicit because the defaults differ by
      model: Opus 5 defaults to "high", Opus 5.5 to "medium". Unpinned, this
      compares two different effort levels rather than two models.
    - ``thinking`` is adaptive. Opus 5.5 rejects both ``disabled`` and an
      explicit ``budget_tokens`` with a 400, and effort is the depth control.
    - No ``fallbacks``: a refusal must fail loudly, not be answered by a
      different model (see RefusalError).
    - No assistant prefill: removed on both models.
    """
    kwargs: dict[str, Any] = {
        "model": model_id,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort},
    }
    if tools:
        kwargs["tools"] = tools
    return kwargs


def _accumulate_usage(usage: Any, call: ModelCall) -> None:
    """Add one response's usage onto the running totals.

    Read defensively: a missing or renamed field should degrade the recorded
    metrics, not kill the run.
    """

    def _get(name: str) -> int | None:
        value = getattr(usage, name, None)
        return value if isinstance(value, int) else None

    def _add(current: int | None, extra: int | None) -> int | None:
        if extra is None:
            return current
        return extra if current is None else current + extra

    call.uncached_input_tokens = _add(call.uncached_input_tokens, _get("input_tokens"))
    call.cache_read_tokens = _add(
        call.cache_read_tokens, _get("cache_read_input_tokens")
    )
    call.cache_creation_tokens = _add(
        call.cache_creation_tokens, _get("cache_creation_input_tokens")
    )
    call.output_tokens = _add(call.output_tokens, _get("output_tokens"))

    details = getattr(usage, "output_tokens_details", None)
    if details is not None:
        thinking = getattr(details, "thinking_tokens", None)
        if isinstance(thinking, int):
            call.thinking_tokens = _add(call.thinking_tokens, thinking)

    server_tools = getattr(usage, "server_tool_use", None)
    if server_tools is not None:
        searches = getattr(server_tools, "web_search_requests", None)
        if isinstance(searches, int):
            call.web_search_requests = _add(call.web_search_requests, searches)

    prompt_parts = [
        call.uncached_input_tokens,
        call.cache_read_tokens,
        call.cache_creation_tokens,
    ]
    if any(part is not None for part in prompt_parts):
        call.input_tokens = sum(part or 0 for part in prompt_parts)
    if call.input_tokens is not None and call.output_tokens is not None:
        call.total_tokens = call.input_tokens + call.output_tokens

    call.cost_usd = estimate_cost(
        call.model_id,
        uncached_input_tokens=call.uncached_input_tokens,
        cache_read_tokens=call.cache_read_tokens,
        cache_creation_tokens=call.cache_creation_tokens,
        output_tokens=call.output_tokens,
        web_search_requests=call.web_search_requests,
    )


def _set_token_attributes(span: Any, call: ModelCall) -> None:
    """Put the token counts on a span, skipping anything we didn't get."""
    for attr, value in (
        (SpanAttributes.LLM_TOKEN_COUNT_PROMPT, call.input_tokens),
        (SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, call.output_tokens),
        (SpanAttributes.LLM_TOKEN_COUNT_TOTAL, call.total_tokens),
        (
            SpanAttributes.LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHE_READ,
            call.cache_read_tokens,
        ),
        (
            SpanAttributes.LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHE_WRITE,
            call.cache_creation_tokens,
        ),
        (
            SpanAttributes.LLM_TOKEN_COUNT_COMPLETION_DETAILS_REASONING,
            call.thinking_tokens,
        ),
    ):
        if value is not None:
            span.set_attribute(attr, value)
    if call.cost_usd is not None:
        span.set_attribute(SpanAttributes.LLM_COST_TOTAL, call.cost_usd)


def verify_served_model(call: ModelCall) -> None:
    """Abort unless the response came from the model we asked for.

    Cheap, and it guards the one failure this harness must never produce: a
    post labelled with a model that did not write it.
    """
    if call.served_model is None:
        return
    if call.served_model == call.model_id:
        return
    raise ModelSubstitutionError(
        f"requested {call.model_id!r} but the response came from "
        f"{call.served_model!r}. Refusing to label this output with a model "
        "that did not produce it."
    )


def _check_refusal(response: Any) -> None:
    if getattr(response, "stop_reason", None) != "refusal":
        return
    details = getattr(response, "stop_details", None)
    category = getattr(details, "category", None)
    explanation = getattr(details, "explanation", None)
    raise RefusalError(
        f"model declined the request (category={category!r}): {explanation!r}"
    )


def run_model(
    *,
    prompt: str,
    system_prompt: str,
    model_id: str,
    effort: str,
    metadata: dict[str, Any],
    span_name: str,
    tools: list[dict[str, Any]] | None = None,
    max_turns: int = 8,
) -> ModelCall:
    """Make the model call, traced, and return its text.

    Two tracing layers:

    - ``using_metadata`` puts the run's identity on the OTel context, so the
      instrumentor's LLM span picks it up too. That is what makes the
      comparison filterable by model in Arize.
    - a CHAIN span via ``tracer.chain``, which sets kind, input/output and
      terminal status automatically. The LLM span nests underneath it.

    ``max_turns`` only matters when server-side tools are in play: the API
    returns ``stop_reason == "pause_turn"`` for a long-running server tool
    turn, which we continue by resending the accumulated content.
    """
    tracer = get_tracer()
    client = get_client()
    call = ModelCall(text="", model_id=model_id, effort=effort)

    @tracer.chain(name=span_name)
    def _invoke(topic_prompt: str, model: str, effort_level: str) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": topic_prompt}
        ]
        text_chunks: list[str] = []
        base = request_kwargs(
            model_id=model,
            effort=effort_level,
            system_prompt=system_prompt,
            tools=tools,
        )

        for turn in range(1, max_turns + 1):
            call.turns = turn
            # The Anthropic instrumentor emits the LLM span for this call;
            # hand-rolling one alongside it would duplicate spans and drift
            # from the semantic conventions.
            #
            # Streaming: max_tokens is large enough that a non-streaming
            # request risks an HTTP timeout.
            with client.messages.stream(**base, messages=messages) as stream:
                response = stream.get_final_message()

            _check_refusal(response)
            call.served_model = getattr(response, "model", None)
            call.stop_reason = getattr(response, "stop_reason", None)
            _accumulate_usage(getattr(response, "usage", None), call)

            for block in response.content:
                kind = getattr(block, "type", None)
                if kind == "text":
                    text_chunks.append(block.text)
                elif kind == "server_tool_use":
                    name = getattr(block, "name", None)
                    if name and name not in call.tools_used:
                        call.tools_used.append(name)

            # A paused turn is the server still working; continue it.
            if call.stop_reason == "pause_turn":
                messages = [
                    *messages,
                    {"role": "assistant", "content": response.content},
                ]
                continue
            break
        else:
            raise ModelCallError(
                f"turn limit ({max_turns}) reached while the server tool was "
                "still paused"
            )

        verify_served_model(call)
        call.text = "".join(text_chunks).strip()
        if not call.text:
            raise ModelCallError(
                f"model returned no text (stop_reason={call.stop_reason!r})"
            )

        # The CHAIN span carries the same facts so it is filterable and costed
        # on its own, without joining to the instrumentor's child LLM span --
        # and the computed cost lives only here, since the API returns none.
        span = otel_trace.get_current_span()
        span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model)
        span.set_attribute(SpanAttributes.LLM_PROVIDER, "anthropic")
        _set_token_attributes(span, call)

        return call.text

    with using_metadata(metadata):
        _invoke(prompt, model_id, effort)

    return call


# --- the measured step ------------------------------------------------------


@dataclass
class BlogPost:
    slug: str
    topic: str
    model_alias: str
    model_id: str
    effort: str
    markdown: str
    word_count: int
    prompt_version: str
    prompt_sha256: str
    brief_sha256: str
    run_id: str
    repeat: int
    versions: dict[str, str]
    call: ModelCall


def write_post(
    *,
    slug: str,
    topic: str,
    model_alias: str,
    model_id: str,
    effort: str,
    word_target: int,
    run_id: str,
    repeat: int = 1,
    genre: str = "unspecified",
    domain: str = "unspecified",
) -> BlogPost:
    """Write one post. The brief is verified before a single token is spent."""
    brief, brief_sha = load_verified_brief(slug)
    prompt = build_writer_prompt(topic=topic, brief=brief, word_target=word_target)
    prompt_sha = sha256_text(prompt)

    metadata = {
        "stage": "write",
        "model_alias": model_alias,
        "model_id": model_id,
        "effort": effort,
        "topic_slug": slug,
        "genre": genre,
        "domain": domain,
        "run_id": run_id,
        "repeat": repeat,
        "word_target": word_target,
        "prompt_version": WRITER_PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "brief_sha256": brief_sha,
    }

    call = run_model(
        prompt=prompt,
        system_prompt=WRITER_SYSTEM,
        model_id=model_id,
        effort=effort,
        metadata=metadata,
        span_name=f"write_post[{model_alias}]",
        # No tools: neither model can bring different material to the page.
        tools=None,
        max_turns=1,
    )

    return BlogPost(
        slug=slug,
        topic=topic,
        model_alias=model_alias,
        model_id=model_id,
        effort=effort,
        markdown=call.text,
        word_count=len(call.text.split()),
        prompt_version=WRITER_PROMPT_VERSION,
        prompt_sha256=prompt_sha,
        brief_sha256=brief_sha,
        run_id=run_id,
        repeat=repeat,
        versions=capture_versions(),
        call=call,
    )


def front_matter(post: BlogPost) -> str:
    """YAML front-matter recording the full pinned surface for this run."""
    c = post.call
    lines = [
        "---",
        f"topic: {post.topic!r}",
        f"slug: {post.slug}",
        f"model_alias: {post.model_alias}",
        f"model_id: {post.model_id}",
        f"served_model: {c.served_model}",
        f"effort: {post.effort}",
        f"prompt_version: {post.prompt_version}",
        f"prompt_sha256: {post.prompt_sha256}",
        f"brief_sha256: {post.brief_sha256}",
        f"run_id: {post.run_id}",
        f"repeat: {post.repeat}",
        f"word_count: {post.word_count}",
        f"input_tokens: {c.input_tokens}",
        f"input_tokens_uncached: {c.uncached_input_tokens}",
        f"cache_read_tokens: {c.cache_read_tokens}",
        f"cache_creation_tokens: {c.cache_creation_tokens}",
        f"output_tokens: {c.output_tokens}",
        f"thinking_tokens: {c.thinking_tokens}",
        f"total_tokens: {c.total_tokens}",
        f"cost_usd_estimated: {c.cost_usd}",
        f"stop_reason: {c.stop_reason}",
    ]
    for key, value in sorted(post.versions.items()):
        lines.append(f"harness_{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def write_output(post: BlogPost, out_root: Path) -> Path:
    """Write the post verbatim under the front-matter. The markdown itself is
    never reformatted -- it is the specimen.

    The repeat index is part of the filename: without it, repeated samples of
    the same cell overwrite each other and all but the last are lost, which
    would quietly defeat the point of --repeats.
    """
    path = (
        out_root
        / post.run_id
        / post.model_alias
        / f"{post.slug}.r{post.repeat}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(front_matter(post) + "\n\n" + post.markdown + "\n")
    return path
