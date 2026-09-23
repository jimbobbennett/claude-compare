"""The LLM judge half of the evaluator, run on OpenAI.

The judge is deliberately **not** a Claude model. What is being measured is
Claude's own stylistic register, and a Claude judge carries a self-preference
risk on exactly that axis -- the MT-Bench work put Claude-v1's self-enhancement
at roughly 25% higher win rate, the largest of the models tested, and
Anthropic's own guidance is to grade with a different model than the one that
generated the output.

Because the judge is cross-family, the constructions are defined
*structurally*, with examples, rather than asking it to "find the claudisms" --
an outside model has to be told the patterns, not asked to recognise a house
style.

Two properties make the output trustworthy:

- **Every instance carries a verbatim quote**, and ``verify_instances`` string-
  matches each one back into the source. An instance that cannot be found is
  discarded, so a judge inventing examples to be helpful cannot inflate a
  count.
- **The judge never counts or computes rates.** It returns instances; the
  harness derives density from its own word count.

Note that these models reject ``temperature=0`` (only the default is accepted),
so the judge is irreducibly stochastic. That is why verified instance counts
are the primary signal and the 1-5 rating is secondary -- and why
``--judge-passes`` exists.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

JUDGE_PROMPT_VERSION = "v2"
DEFAULT_JUDGE_MODEL = "gpt-5.6-luna"

# Format features -- bold lead-in bullets and em-dash asides -- are
# deliberately NOT judged. They are counted exactly by claudisms.py, and asking
# the judge for them swamped everything else: a first run returned 30
# bold_leadin_bullet instances on a telegraphic research brief, which pushed the
# contamination baseline as high as the posts and destroyed the metric's
# discriminative power. The judge covers voice; regex covers format.
CATEGORIES: dict[str, str] = {
    "antithesis_pivot": '"It\'s not X, it\'s Y" / "X isn\'t just Y - it\'s Z". A '
    "negation of one framing immediately replaced by a sharper one.",
    "concessive_pivot": "A concession followed by reversal: \"Sure, X. But Y.\" / "
    '"That\'s true, as far as it goes. What it misses is..."',
    "reveal_setup": "A short sentence announcing that an insight is coming rather "
    'than delivering it: "Here\'s the thing." / "And that\'s the part that '
    'matters." / "Here\'s what\'s actually happening."',
    "rule_of_three": "Three parallel items escalating in weight, especially as a "
    "sentence's closing rhythm.",
    "meta_writing": "The text commenting on itself or steering the reader: \"take a "
    'moment to read that again" / "we\'ll come back to this" / "the short '
    'version:".',
    "load_bearing_idiom": "Engineering metaphors used for abstract claims: "
    '"load-bearing", "the sharp edges", "where it falls over", "doing the heavy '
    'lifting".',
    "punchy_closer": "A final paragraph of one or two very short declarative "
    "sentences landing the argument.",
    "hedge_then_assert": "A hedge immediately overridden: \"This is probably "
    'overstated, but the direction is right."',
}

JUDGE_SYSTEM = (
    "You are a forensic style analyst. You identify specific rhetorical "
    "constructions in text and report them as structured data. You do not "
    "rewrite, improve, or critique the writing, and you do not comment on "
    "whether it is good."
)

RATING_RUBRIC = """\
5 - Saturated. Signature constructions drive the prose; the argument advances
    through them.
4 - Strong. Recurring and noticeable across multiple sections.
3 - Moderate. Present in several places but not the dominant mode.
2 - Faint. One or two instances, otherwise plain exposition.
1 - Absent. Reads as unmarked technical prose."""


def build_judge_prompt(document: str) -> str:
    category_block = "\n".join(
        f"{i}. {name} - {desc}" for i, (name, desc) in enumerate(CATEGORIES.items(), 1)
    )
    return f"""\
Below is a document. Identify every instance of the rhetorical constructions
listed below. These are structural patterns, not topics - judge form, never
subject matter or quality.

Report only what is present in the text. If a category has no instances, omit
it. Do not stretch a match to fill a category.

Judge the prose. Do not report an instance whose only basis is list formatting,
bold text, or punctuation choice - those are counted separately.

CATEGORIES

{category_block}

For each instance, quote the text VERBATIM - 4 to 25 words, copied exactly from
the document. An instance you cannot quote exactly does not count.

Then rate the whole document:

{RATING_RUBRIC}

Do not count words or compute rates. Report instances and the rating only.

DOCUMENT
---
{document}
---
"""


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "instances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": list(CATEGORIES)},
                    "quote": {"type": "string"},
                },
                "required": ["category", "quote"],
                "additionalProperties": False,
            },
        },
        "rating": {"type": "integer"},
        "rationale": {"type": "string"},
    },
    "required": ["instances", "rating", "rationale"],
    "additionalProperties": False,
}


class JudgeError(RuntimeError):
    pass


@dataclass
class JudgeResult:
    model: str
    prompt_version: str
    rating: int | None
    rationale: str
    # Instances whose quote was found verbatim in the source.
    verified: list[dict[str, str]] = field(default_factory=list)
    # Instances the judge reported that are NOT in the source. Kept, not
    # silently dropped: a rising count here means the judge is confabulating.
    unverified: list[dict[str, str]] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    passes: int = 1

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for inst in self.verified:
            out[inst["category"]] = out.get(inst["category"], 0) + 1
        return out

    @property
    def verified_total(self) -> int:
        return len(self.verified)


def _normalise(text: str) -> str:
    """Collapse whitespace and unify dash/quote variants for quote matching.

    A judge quoting across a line break, or normalising an en-dash to a hyphen,
    is quoting faithfully; only a quote that is not in the text at all should
    fail verification.
    """
    text = text.replace("—", "-").replace("–", "-")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def verify_instances(
    instances: list[dict[str, str]], document: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split reported instances into (found verbatim, not found)."""
    haystack = _normalise(document)
    verified: list[dict[str, str]] = []
    unverified: list[dict[str, str]] = []
    for inst in instances:
        quote = (inst.get("quote") or "").strip()
        if quote and _normalise(quote) in haystack:
            verified.append(inst)
        else:
            unverified.append(inst)
    return verified, unverified


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def judge_document(
    document: str,
    *,
    model: str = DEFAULT_JUDGE_MODEL,
    passes: int = 1,
) -> JudgeResult:
    """Run the judge over one document, optionally averaging several passes.

    With more than one pass, instances are unioned by (category, quote) so a
    construction spotted in any pass counts once, and the rating is the mean
    rounded to the nearest integer. These models reject temperature=0, so
    repeated passes are the only way to damp judge variance.
    """
    client = get_client()
    prompt = build_judge_prompt(document)

    seen: dict[tuple[str, str], dict[str, str]] = {}
    unverified: list[dict[str, str]] = []
    ratings: list[int] = []
    rationales: list[str] = []
    in_tokens = 0
    out_tokens = 0

    for _ in range(max(1, passes)):
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "claudism_instances",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise JudgeError("judge returned empty content")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"judge returned unparseable JSON: {exc}") from exc

        ver, unver = verify_instances(payload.get("instances") or [], document)
        for inst in ver:
            seen[(inst["category"], _normalise(inst["quote"]))] = inst
        unverified.extend(unver)

        # strict mode does not enforce numeric bounds, so validate here rather
        # than trust the rubric to have been followed.
        rating = payload.get("rating")
        if isinstance(rating, int) and 1 <= rating <= 5:
            ratings.append(rating)
        rationales.append(str(payload.get("rationale") or "")[:400])

        usage = getattr(response, "usage", None)
        if usage is not None:
            in_tokens += getattr(usage, "prompt_tokens", 0) or 0
            out_tokens += getattr(usage, "completion_tokens", 0) or 0

    return JudgeResult(
        model=model,
        prompt_version=JUDGE_PROMPT_VERSION,
        rating=round(sum(ratings) / len(ratings)) if ratings else None,
        rationale=rationales[0] if rationales else "",
        verified=list(seen.values()),
        unverified=unverified,
        input_tokens=in_tokens or None,
        output_tokens=out_tokens or None,
        passes=max(1, passes),
    )
