"""Rewrite a markdown document to strip Claude's signature constructions.

This closes the loop on the experiment. The evaluator defines what a claudism
is; this uses those same definitions as an editing brief, hands a document to a
model, and asks for the constructions removed while the substance stays put.

The hard problem is not the rewriting, it is not corrupting the document. A
model asked to edit a technical README will happily round 3.45 to 3.4, reflow a
table, or drop a shell flag. Three mechanisms prevent that:

1. **Fenced code blocks and tables never reach the model.** They are extracted
   and replaced with sentinels, which the model is told to leave in place. They
   are substituted back afterwards, byte-identical.
2. **Headings are pinned.** Every heading line is preserved exactly, so the
   document's structure cannot drift.
3. **Numbers are verified.** Every numeric literal in the input must still be
   present in the output, or the section is rejected and the original kept.

A rejected section is reported, not silently swallowed.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import anthropic

from .judge_spec import CLAUDISM_CATEGORIES

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_TOKENS = 32000

SENTINEL = "⟦BLOCK{}⟧"
SENTINEL_RX = re.compile(r"⟦BLOCK\d+⟧")

# Fenced code blocks, and contiguous runs of markdown table rows.
FENCE_RX = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
TABLE_RX = re.compile(r"(?:^\|.*\|[ \t]*$\n?)+", re.MULTILINE)
HEADING_RX = re.compile(r"^#{1,6} .*$", re.MULTILINE)
NUMBER_RX = re.compile(r"\d+(?:[.,]\d+)*")

SYSTEM = (
    "You are a copy editor. You remove specific rhetorical constructions from "
    "technical documentation while leaving its substance, structure and every "
    "factual claim exactly as they are. You return only the edited text, with "
    "no preamble and no commentary."
)


def build_prompt(section: str) -> str:
    cats = "\n".join(
        f"{i}. {name} — {desc}"
        for i, (name, desc) in enumerate(CLAUDISM_CATEGORIES.items(), 1)
    )
    return f"""\
Rewrite the markdown below to remove the rhetorical constructions listed. The
goal is prose that reads as plain, unmarked technical writing.

CONSTRUCTIONS TO REMOVE

{cats}

Also remove:
- em-dash asides. Use a comma, a full stop, or parentheses instead.
- bolded lead-in phrases at the start of list items and paragraphs, where the
  bold is doing the work of a heading rather than emphasising a word.
- second-person editorialising about what the reader will find interesting,
  surprising or important.

RULES YOU MUST NOT BREAK

- Preserve every fact, number, name, file path, command and claim exactly.
  Do not round numbers. Do not rephrase a measurement.
- Do not add information. Do not remove information. If a sentence carries a
  fact, the fact survives the edit.
- Keep every line that begins with one or more # characters exactly as it is.
- Tokens that look like ⟦BLOCK7⟧ are placeholders for code and tables. Leave
  each one on its own line, in the same order, unchanged. Do not add or remove
  any.
- Keep markdown list structure. Keep links.
- Do not make the text terser at the cost of dropping content. Plainer, not
  shorter.

Return only the rewritten markdown.

MARKDOWN TO REWRITE
---
{section}
---
"""


@dataclass
class SectionResult:
    heading: str
    status: str  # "rewritten" | "kept: <reason>"
    before: str
    after: str


def protect(text: str) -> tuple[str, list[str]]:
    """Replace code fences and tables with sentinels."""
    blocks: list[str] = []

    def take(match: re.Match[str]) -> str:
        blocks.append(match.group(0))
        return SENTINEL.format(len(blocks) - 1)

    text = FENCE_RX.sub(take, text)
    text = TABLE_RX.sub(take, text)
    return text, blocks


def restore(text: str, blocks: list[str]) -> str:
    def put(match: re.Match[str]) -> str:
        index = int(re.search(r"\d+", match.group(0)).group(0))
        return blocks[index]

    return SENTINEL_RX.sub(put, text)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split on level-2 headings, returning (heading, body) pairs.

    The preamble before the first ## is returned with an empty heading.
    """
    parts = re.split(r"^(## .*)$", text, flags=re.MULTILINE)
    sections = [("", parts[0])]
    for i in range(1, len(parts), 2):
        sections.append((parts[i], parts[i] + parts[i + 1]))
    return sections


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER_RX.findall(text)}


def check(before: str, after: str, block_count: int) -> str | None:
    """Return a rejection reason, or None if the rewrite is safe to keep."""
    got = len(SENTINEL_RX.findall(after))
    if got != block_count:
        return f"sentinel count {got} != {block_count}"

    before_h = HEADING_RX.findall(before)
    after_h = HEADING_RX.findall(after)
    if before_h != after_h:
        return "headings changed"

    missing = numbers_in(before) - numbers_in(after)
    if missing:
        shown = ", ".join(sorted(missing)[:6])
        return f"lost {len(missing)} number(s): {shown}"

    if not after.strip():
        return "empty result"
    # A section that shrinks a lot has probably dropped content, not just style.
    if len(after) < len(before) * 0.55:
        return f"shrank to {round(100 * len(after) / len(before))}% of original"
    return None


def rewrite_section(
    client: anthropic.Anthropic, body: str, model: str, effort: str
) -> str:
    # The model's reply is stripped, which would eat the blank line separating
    # this section from the next and glue two headings together. Keep the
    # original trailing whitespace and reapply it on the way out.
    trailing = body[len(body.rstrip()) :]
    protected, blocks = protect(body)
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=[{"role": "user", "content": build_prompt(protected)}],
    ) as stream:
        response = stream.get_final_message()

    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("model declined the edit")
    if response.model != model:
        raise RuntimeError(f"requested {model} but response came from {response.model}")

    text = "".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()
    # The model sometimes wraps its answer in a fence; unwrap a single one.
    if text.startswith("```") and text.endswith("```"):
        text = re.sub(r"^```[a-z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)

    reason = check(protected, text, len(blocks))
    if reason:
        raise ValueError(reason)
    return restore(text, blocks) + trailing


def run(args: argparse.Namespace) -> int:
    source = Path(args.source)
    text = source.read_text()
    client = anthropic.Anthropic()

    results: list[SectionResult] = []
    out_parts: list[str] = []
    for heading, body in split_sections(text):
        label = heading or "(preamble)"
        if not body.strip():
            out_parts.append(body)
            continue
        if args.only and args.only.lower() not in label.lower():
            out_parts.append(body)
            results.append(SectionResult(label, "skipped", body, body))
            continue
        print(f"  {label[:58]:60}", end="", flush=True)
        try:
            new = rewrite_section(client, body, args.model, args.effort)
        except ValueError as exc:
            print(f"KEPT ({exc})")
            results.append(SectionResult(label, f"kept: {exc}", body, body))
            out_parts.append(body)
            continue
        except Exception as exc:
            print(f"ERROR ({type(exc).__name__}: {exc})")
            results.append(SectionResult(label, f"error: {exc}", body, body))
            out_parts.append(body)
            continue
        print("rewritten")
        results.append(SectionResult(label, "rewritten", body, new))
        out_parts.append(new)

    dest = Path(args.out)
    dest.write_text("".join(out_parts))

    rewritten = sum(1 for r in results if r.status == "rewritten")
    kept = [r for r in results if r.status.startswith("kept")]
    errored = [r for r in results if r.status.startswith("error")]
    print(f"\n  {rewritten} rewritten, {len(kept)} kept, {len(errored)} errored")
    for r in kept + errored:
        print(f"    {r.heading[:50]:52} {r.status}")
    print(f"  -> {dest}")
    return 1 if errored else 0


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="blogwriter-destyle",
        description="Rewrite markdown to remove Claude's signature constructions, "
        "using the evaluator's own category definitions as the editing brief.",
    )
    parser.add_argument("source", help="markdown file to rewrite")
    parser.add_argument("--out", required=True, help="where to write the result")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--only", help="only rewrite sections whose heading matches")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
