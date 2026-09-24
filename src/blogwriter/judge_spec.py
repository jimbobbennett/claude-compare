"""The single definition of what counts as a claudism.

Two things consume this: the AX judge evaluator, and the de-styling tool in
``destyle.py``. Keeping one definition means a construction cannot be scored by
the evaluator but missed by the rewriter, or vice versa.

``ax/claudism_template.txt`` is generated from here. A test asserts the file on
disk matches ``render_template()``, so editing one without regenerating the
other fails the suite rather than silently drifting.

There are two judges:

- **v1** (``claudism_density``): one label per post on the 1-5 scale.
  Generated into ``ax/claudism_template.txt``. Kept unchanged so every existing
  score stays reproducible.
- **v2** (``claudism_spans``): returns every instance it finds as JSON quotes
  with a category, and code turns that into a density and the same 1-5 scale.
  Generated into ``ax/claudism_spans_template.txt``. The categories come from
  153 hand-flagged claudisms (``annotations/``), so the judge's output can be
  checked against a human, which v1's single label cannot. v2 runs locally
  through ``judge.py`` rather than in AX; ``render_template_v2`` says why.

To change the definitions:

    1. edit the categories or scales below
    2. run: uv run python -m blogwriter.judge_spec --write
    3. for v1, create a new evaluator version in AX from the regenerated file
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AX_DIR = Path(__file__).resolve().parents[2] / "ax"
TEMPLATE_PATH = AX_DIR / "claudism_template.txt"
TEMPLATE_V2_PATH = AX_DIR / "claudism_spans_template.txt"

CLAUDISM_CATEGORIES: dict[str, str] = {
    "antithesis pivot": (
        '"It is not X, it is Y" / "X is not just Y, it is Z": a negation of one '
        "framing immediately replaced by a sharper one."
    ),
    "concessive pivot": (
        'a concession followed by reversal: "Sure, X. But Y." / "That is true, '
        'as far as it goes. What it misses is..."'
    ),
    "reveal setup": (
        "a short sentence announcing an insight is coming rather than "
        'delivering it: "Here is the thing." / "And that is the part that '
        'matters."'
    ),
    "rule of three": (
        "three parallel items escalating in weight, especially closing a "
        "sentence."
    ),
    "meta writing": (
        'the text commenting on itself or steering the reader: "take a moment '
        'to read that again" / "we will come back to this" / "the short '
        'version:".'
    ),
    "load-bearing idiom": (
        'engineering metaphors for abstract claims: "load-bearing", "the sharp '
        'edges", "where it falls over", "doing the heavy lifting".'
    ),
    "punchy closer": (
        "a final paragraph of one or two very short declarative sentences "
        "landing the argument."
    ),
    "hedge then assert": (
        'a hedge immediately overridden: "This is probably overstated, but the '
        'direction is right."'
    ),
}

# Label -> numeric score. Ordered worst-to-best for the prompt's rating scale.
RATING_SCALE: dict[str, tuple[int, str]] = {
    "saturated": (
        5,
        "these constructions drive the prose; the argument advances through them.",
    ),
    "strong": (4, "recurring and noticeable across multiple sections."),
    "moderate": (3, "present in several places but not the dominant mode."),
    "faint": (2, "one or two instances, otherwise plain exposition."),
    "absent": (1, "reads as unmarked technical prose."),
}


def classification_choices() -> dict[str, int]:
    """The --classification-choices payload for the AX evaluator."""
    return {label: score for label, (score, _) in RATING_SCALE.items()}


def render_template() -> str:
    """Build the AX judge prompt. `{output}` is the only variable."""
    constructions = "\n".join(
        f"{i}. {name} - {desc}"
        for i, (name, desc) in enumerate(CLAUDISM_CATEGORIES.items(), 1)
    )
    scale = "\n".join(f"{label} - {desc}" for label, (_, desc) in RATING_SCALE.items())
    labels = ", ".join(RATING_SCALE)
    return f"""\
You are a forensic style analyst. You judge the FORM of prose, never its subject matter, accuracy, or quality.

Below is a blog post. Rate how heavily it uses the following rhetorical constructions.

CONSTRUCTIONS TO LOOK FOR
{constructions}

Judge the prose only. Do NOT count list formatting, bold text, headings, or punctuation choices - those are measured separately.

RATING SCALE
{scale}

BLOG POST
{{output}}

Respond with exactly one of these labels: {labels}
"""


# --- v2: span extraction --------------------------------------------------
#
# Ordered by how often each move was hand-flagged in the Opus 5 posts. Rule of
# three and punchy closers are not here: claudisms.py counts them structurally.
# Concessive pivot, meta writing and hedge-then-assert were dropped because
# the annotations gave them almost no support.

CLAUDISM_CATEGORIES_V2: dict[str, str] = {
    "salience_flag": (
        "the prose says something is important instead of showing why: "
        '"The interaction matters", "the critical detail", "a fact worth '
        'internalising", "deserves a moment".'
    ),
    "contrast_reframe": (
        "one framing negated and replaced with a sharper one: \"Access is not "
        'ownership", "a difference of degree, not of kind", "It is not X. It '
        'is Y."'
    ),
    "verdict_intensifier": (
        "a word that marks a claim as final or sincere without adding "
        'information: "that\'s the whole point", "the honest answer", "that\'s '
        'a real difference", "that\'s not accidental".'
    ),
    "signpost": (
        'announces an insight instead of delivering it: "Here\'s the part '
        'that...", "Think about what that means", "Two things to keep in mind".'
    ),
    "gotcha_framing": (
        'presents a detail as a hidden trap: "The trap is...", "The catch '
        'is...", "one detail bites everyone".'
    ),
    "stock_metaphor": (
        "mechanical or economic metaphor for an abstract claim: "
        '"load-bearing", "doing a lot of work", "earns its keep", "a useful '
        'lens". Always tag any use of "load-bearing" (literal or figurative, '
        'hyphenated or not) and close variants like "bears the load" or '
        '"carries the weight".'
    ),
}

# Instances per 1000 words of prose -> label. The lower bound of each band,
# checked from the top. Provisional: set so the hand-flagged Opus 5 density
# (~2.9 flags per 1000 words, and the flags were not exhaustive) lands in
# "moderate" to "strong". Recalibrate on the r1 posts only (see validate.py).
DENSITY_BANDS: list[tuple[float, str]] = [
    (6.0, "saturated"),
    (3.0, "strong"),
    (1.0, "moderate"),
    (0.01, "faint"),
    (0.0, "absent"),
]


def render_template_v2() -> str:
    """Build the v2 AX judge prompt. `{output}` is the only variable.

    The JSON shape is described in words, not shown as an example, because
    literal braces in an AX template can be read as extra variables.

    This judge runs locally (``judge.py``), not in AX. AX template evaluators
    must return a classification label (a freeform one is rejected with HTTP
    422), and AX appends its own "explain, then label" instruction, which
    overrides any request to put JSON in the explanation. So a hosted template
    evaluator cannot return spans.
    """
    constructions = "\n".join(
        f"{i}. {name} - {desc}"
        for i, (name, desc) in enumerate(CLAUDISM_CATEGORIES_V2.items(), 1)
    )
    names = ", ".join(CLAUDISM_CATEGORIES_V2)
    return f"""\
You are a forensic style analyst. You judge the FORM of prose, never its subject matter, accuracy, or quality.

Below is a blog post. Find every instance of the constructions listed. Quote each one exactly, using the shortest span that shows the construction (usually one clause or sentence).

CONSTRUCTIONS
{constructions}

RULES
- Judge prose only. Ignore code blocks, headings, list formatting, bold, and punctuation.
- A plain factual statement is not a salience flag. "Latency matters for voice agents because users hang up after two seconds" gives the reason; flag only when the importance is asserted and the reason is missing or comes after.
- One span can have one category. Pick the best fit.
- If there are none, return an empty list.

BLOG POST
{{output}}

Respond with JSON only: one object with a single key, "instances", whose value is a list. Each list item is an object with two keys: "quote" (the exact text) and "category" (one of: {names}).
"""


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_judge_output(raw: str) -> list[dict[str, str]]:
    """Pull the instance list out of the judge's reply.

    Tolerates code fences and stray prose around the JSON, because freeform
    judge output is not guaranteed to be clean. Drops instances with an unknown
    category or an empty quote rather than failing the whole post. Raises
    ValueError if there is no parseable JSON at all.
    """
    match = _JSON_OBJECT.search(raw or "")
    if not match:
        raise ValueError("no JSON object in judge output")
    data = json.loads(match.group(0))
    instances = data.get("instances", []) if isinstance(data, dict) else []
    clean = []
    for item in instances:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        category = str(item.get("category", "")).strip()
        if quote and category in CLAUDISM_CATEGORIES_V2:
            clean.append({"quote": quote, "category": category})
    return clean


def density_label(per_1k: float) -> tuple[int, str]:
    """Map instances per 1000 words to the shared 1-5 scale."""
    for floor, label in DENSITY_BANDS:
        if per_1k >= floor:
            return RATING_SCALE[label][0], label
    return RATING_SCALE["absent"][0], "absent"


def score_instances(instances: list[dict[str, str]], word_count: int) -> dict:
    """Turn judge spans into a v2 score comparable with v1's label."""
    per_1k = round(len(instances) * 1000 / word_count, 2) if word_count else 0.0
    score, label = density_label(per_1k)
    by_category: dict[str, int] = {}
    for item in instances:
        by_category[item["category"]] = by_category.get(item["category"], 0) + 1
    return {
        "score": score,
        "label": label,
        "instances_per_1k": per_1k,
        "instance_count": len(instances),
        "by_category": by_category,
    }


def _check(path: Path, rendered: str, write: bool) -> bool:
    if write:
        path.write_text(rendered)
        print(f"wrote {path}")
        return True
    on_disk = path.read_text() if path.exists() else ""
    if on_disk == rendered:
        print(f"{path.name} is up to date")
        return True
    print(f"{path.name} is STALE -- run with --write", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m blogwriter.judge_spec",
        description="Render or check the AX judge templates.",
    )
    parser.add_argument(
        "--write", action="store_true", help="write both templates to disk"
    )
    args = parser.parse_args()

    ok = _check(TEMPLATE_PATH, render_template(), args.write)
    ok = _check(TEMPLATE_V2_PATH, render_template_v2(), args.write) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
