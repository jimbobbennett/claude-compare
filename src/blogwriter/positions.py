"""Locate quotes in a post and write them as ``start-end | quote`` lines.

AX annotations and evaluator explanations are plain text on a whole record,
with no way to highlight part of the output. So both the hand-flagged
claudisms and the evaluator's spans are stored in one line format, with
character offsets into the run's ``output``:

    483-524 | That single announcement is a useful lens
    1178-1199 | contrast_reframe | That's not accidental

The human labels have two fields; the evaluator adds a category in the middle.
Offsets are what make the two comparable in code, since AX treats the text as
opaque.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# AX rejects a freeform annotation longer than this, and one oversized value
# fails the whole batch, so callers check before sending.
MAX_TEXT = 1500

# Markdown the Google Doc export dropped from some highlights, e.g. `effort`
# and *approximate*, which must be skipped when matching against the post.
_MARKUP = "[*_`]*"


@dataclass(frozen=True)
class Located:
    start: int
    end: int
    quote: str
    category: str | None = None

    def line(self) -> str:
        middle = f" | {self.category}" if self.category else ""
        return f"{self.start}-{self.end}{middle} | {self.quote}"


def locate(quote: str, text: str) -> tuple[int, int] | None:
    """Find ``quote`` in ``text``, tolerating dropped markdown and spacing.

    Returns the span in ``text`` itself, so ``text[start:end]`` is the passage
    as it appears in the post, markup included.
    """
    quote = quote.strip()
    if not quote:
        return None
    i = text.find(quote)
    if i >= 0:
        return i, i + len(quote)
    parts = []
    for ch in quote:
        if ch.isspace():
            if not parts or parts[-1] != r"\s+":
                parts.append(r"\s+")
        else:
            parts.append(re.escape(ch))
    pattern = _MARKUP.join(parts)
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match else None


def format_lines(items: list[Located]) -> str:
    return "\n".join(item.line() for item in sorted(items, key=lambda x: x.start))


_LINE = re.compile(r"^(-?\d+)-(-?\d+) \| (?:([a-z_]+) \| )?(.*)$")


def parse_lines(text: str) -> list[Located]:
    """Read lines written by ``format_lines``. Unparseable lines are skipped."""
    out = []
    for raw in (text or "").splitlines():
        m = _LINE.match(raw.strip())
        if m:
            out.append(Located(int(m[1]), int(m[2]), m[4], m[3]))
    return out
