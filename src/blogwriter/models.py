"""Model registry and the run knobs that must be pinned explicitly.

The whole experiment rests on the model ID being the *only* thing that differs
between two runs, so anything that could vary per model is nailed down here
rather than left to a default.
"""

from __future__ import annotations

# Short alias -> full model ID. Aliases are for the CLI; the full ID is what
# reaches the SDK and gets recorded in the trace and front-matter.
MODELS: dict[str, str] = {
    "opus-5": "claude-opus-5",
    "opus-5.5": "claude-opus-5-5",
}

# Research runs once and its output is committed as a fixture, so this model
# never varies between comparison runs.
RESEARCH_MODEL = "claude-opus-5"

# Pinned deliberately. Opus 5 defaults to "high" and Opus 5.5 defaults to
# "medium": leaving effort unset would compare Opus 5 at high against Opus 5.5
# at medium, which is a confound rather than a model comparison.
DEFAULT_EFFORT = "medium"
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")

DEFAULT_WORD_TARGET = 1200


class ModelError(ValueError):
    """Raised for an unusable --model value, before any API call is made."""


def resolve_model(value: str) -> tuple[str, str]:
    """Map a CLI --model value to ``(alias, model_id)``.

    Accepts a registry alias ("opus-5.5") or a raw model ID ("claude-opus-5-5"),
    so comparing a third model needs no code change.
    """
    value = value.strip()
    if not value:
        raise ModelError("--model must not be empty")
    if value in MODELS:
        return value, MODELS[value]
    if value.startswith("claude-"):
        # Raw ID: reuse the alias if we know it, so output paths stay tidy.
        for alias, model_id in MODELS.items():
            if model_id == value:
                return alias, model_id
        return value, value
    raise ModelError(
        f"unknown model {value!r}. Use an alias ({', '.join(MODELS)}) "
        "or a full model ID starting with 'claude-'."
    )


def resolve_effort(value: str) -> str:
    value = value.strip().lower()
    if value not in VALID_EFFORTS:
        raise ModelError(
            f"invalid effort {value!r}. Choose one of: {', '.join(VALID_EFFORTS)}."
        )
    return value


# Per-million-token list prices, from
# https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-09-22).
# The Messages API does not return a cost, so it is computed from exact token
# counts. Unknown models return None rather than a fabricated number.
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-5": {
        "input": 5.00,
        "cache_write_5m": 6.25,
        "cache_read": 0.50,
        "output": 25.00,
    },
    "claude-opus-5-5": {
        "input": 4.00,
        "cache_write_5m": 5.00,
        "cache_read": 0.20,
        "output": 20.00,
    },
}

# Web search: $10 per 1,000 searches. Failed searches are not billed.
WEB_SEARCH_COST_PER_REQUEST = 0.01


def estimate_cost(
    model_id: str,
    *,
    uncached_input_tokens: int | None,
    cache_read_tokens: int | None,
    cache_creation_tokens: int | None,
    output_tokens: int | None,
    web_search_requests: int | None = None,
) -> float | None:
    """Estimate USD cost from exact token counts, or None if rates are unknown.

    Cache writes are priced at the 5-minute rate: we never request the 1-hour
    duration, so automatic caching only ever writes 5-minute entries.
    """
    rates = PRICING.get(model_id)
    if rates is None:
        return None
    cost = (
        (uncached_input_tokens or 0) * rates["input"]
        + (cache_read_tokens or 0) * rates["cache_read"]
        + (cache_creation_tokens or 0) * rates["cache_write_5m"]
        + (output_tokens or 0) * rates["output"]
    ) / 1_000_000
    cost += (web_search_requests or 0) * WEB_SEARCH_COST_PER_REQUEST
    return round(cost, 6)
