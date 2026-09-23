"""The single definition of what counts as a claudism.

Two things consume this: the AX judge evaluator, and the de-styling tool in
``destyle.py``. Keeping one definition means a construction cannot be scored by
the evaluator but missed by the rewriter, or vice versa.

``ax/claudism_template.txt`` is generated from here. A test asserts the file on
disk matches ``render_template()``, so editing one without regenerating the
other fails the suite rather than silently drifting.

To change the definitions:

    1. edit CLAUDISM_CATEGORIES or RATING_SCALE below
    2. run: uv run python -m blogwriter.judge_spec --write
    3. create a new evaluator version in AX from the regenerated file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "ax" / "claudism_template.txt"

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


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m blogwriter.judge_spec",
        description="Render or check the AX judge template.",
    )
    parser.add_argument(
        "--write", action="store_true", help=f"write {TEMPLATE_PATH.name} to disk"
    )
    args = parser.parse_args()

    rendered = render_template()
    if args.write:
        TEMPLATE_PATH.write_text(rendered)
        print(f"wrote {TEMPLATE_PATH}")
        return 0

    on_disk = TEMPLATE_PATH.read_text() if TEMPLATE_PATH.exists() else ""
    if on_disk == rendered:
        print(f"{TEMPLATE_PATH.name} is up to date")
        return 0
    print(f"{TEMPLATE_PATH.name} is STALE -- run with --write", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
