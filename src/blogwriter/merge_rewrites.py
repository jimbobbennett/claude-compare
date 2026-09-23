"""Merge several de-styled rewrites into one document, section by section.

Different models strip different things. In the first run on this repo's README,
Opus 5.5 removed em-dashes but left a few, and reduced rule-of-three; codex
removed every em-dash but *increased* rule-of-three and short punchy sentences,
and dropped 151 words. Neither was best everywhere.

So rather than pick a winner overall, this scores each section of each variant
with the deterministic scorer and takes the best one, subject to a content
guard: a section that lost a number or shrank materially against the original
is disqualified no matter how clean it reads.

The merged document is then checked as a whole against the original, so a
per-section choice cannot corrupt the result.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from .claudisms import score_text
from .destyle import (
    FENCE_RX,
    HEADING_RX,
    TABLE_RX,
    numbers_in,
    split_sections,
)

# Weights for the composite style penalty. Em-dashes dominate because they are
# the signal the experiment found to be both strongest and cleanest; the others
# are secondary structural tells. Short sentences are weighted lightly because
# some are legitimate in technical prose.
WEIGHTS = {
    "em_dash_per_1k": 1.0,
    "rule_of_three_per_1k": 0.8,
    "bold_leadin_bullet_per_1k": 0.5,
    "claude_leaning_per_1k": 1.0,
    "short_sentence_per_1k": 0.15,
}

# A section may not lose this fraction of its words relative to the original.
MIN_LENGTH_RATIO = 0.80

# Per-1000-word densities are meaningless on a very short section: one match in
# twenty words reads as 50 per 1000. Below this, keep the original rather than
# letting noise pick a winner.
MIN_WORDS_TO_JUDGE = 60


@dataclass
class Choice:
    heading: str
    winner: str
    penalty: float
    rejected: dict[str, str]


def style_penalty(text: str) -> float:
    densities = score_text(text).densities()
    return round(
        sum(weight * densities.get(key, 0.0) for key, weight in WEIGHTS.items()), 3
    )


def disqualify(original: str, candidate: str) -> str | None:
    """Return why a candidate section is unusable, or None if it is fine."""
    missing = numbers_in(original) - numbers_in(candidate)
    if missing:
        return f"lost numbers {sorted(missing)[:4]}"
    if FENCE_RX.findall(original) != FENCE_RX.findall(candidate):
        return "code blocks differ"
    if TABLE_RX.findall(original) != TABLE_RX.findall(candidate):
        return "tables differ"
    if HEADING_RX.findall(original) != HEADING_RX.findall(candidate):
        return "headings differ"
    ow, cw = len(original.split()), len(candidate.split())
    if ow and cw / ow < MIN_LENGTH_RATIO:
        return f"shrank to {round(100 * cw / ow)}% of original"
    # Horizontal rules are document structure. A model that adds or drops one
    # has restructured rather than restyled.
    o_rules = original.count("\n---\n")
    c_rules = candidate.count("\n---\n")
    if o_rules != c_rules:
        return f"horizontal rules {o_rules} -> {c_rules}"
    return None


def merge(
    original: str, variants: dict[str, str]
) -> tuple[str, list[Choice]]:
    base = split_sections(original)
    split_variants = {name: split_sections(text) for name, text in variants.items()}

    for name, sections in split_variants.items():
        if [h for h, _ in sections] != [h for h, _ in base]:
            raise ValueError(f"{name} has a different section structure")

    out: list[str] = []
    choices: list[Choice] = []
    for index, (heading, original_body) in enumerate(base):
        label = heading or "(preamble)"
        if len(original_body.split()) < MIN_WORDS_TO_JUDGE:
            out.append(original_body)
            choices.append(Choice(label, "original (too short to judge)", 0.0, {}))
            continue
        candidates: dict[str, str] = {"original": original_body}
        rejected: dict[str, str] = {}
        for name, sections in split_variants.items():
            body = sections[index][1]
            reason = disqualify(original_body, body)
            if reason:
                rejected[name] = reason
            else:
                candidates[name] = body

        winner = min(candidates, key=lambda n: (style_penalty(candidates[n]), n))
        out.append(candidates[winner])
        choices.append(
            Choice(label, winner, style_penalty(candidates[winner]), rejected)
        )

    return "".join(out), choices


def run(args: argparse.Namespace) -> int:
    original = Path(args.original).read_text()
    variants = {}
    for spec in args.variant:
        if "=" not in spec:
            print(f"error: --variant needs name=path, got {spec!r}", file=sys.stderr)
            return 2
        name, path = spec.split("=", 1)
        variants[name] = Path(path).read_text()

    try:
        merged, choices = merge(original, variants)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"  {'section':44}{'winner':12}{'penalty':>9}")
    print("  " + "-" * 63)
    for choice in choices:
        print(f"  {choice.heading[:42]:44}{choice.winner:12}{choice.penalty:>9}")
        for name, reason in choice.rejected.items():
            print(f"      rejected {name}: {reason}")

    problem = disqualify(original, merged)
    print()
    if problem:
        print(f"  MERGED DOCUMENT FAILED VERIFICATION: {problem}", file=sys.stderr)
        return 1
    print("  merged document verified against the original:")
    print("    numbers, code blocks, tables and headings all preserved")

    before, after = style_penalty(original), style_penalty(merged)
    print(f"  style penalty {before} -> {after}")
    tally: dict[str, int] = {}
    for choice in choices:
        tally[choice.winner] = tally.get(choice.winner, 0) + 1
    print(f"  sections taken from: {tally}")

    Path(args.out).write_text(merged)
    print(f"  -> {args.out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="blogwriter-merge",
        description="Merge de-styled rewrites section by section, keeping the "
        "cleanest version that has not lost content.",
    )
    parser.add_argument("original", help="the original document")
    parser.add_argument(
        "--variant",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="a rewrite to consider (repeatable)",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
