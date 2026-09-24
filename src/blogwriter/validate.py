"""Check the v2 evaluator against human-flagged claudisms.

v1 returns one label per post, so there is nothing to compare it to a human
reader. v2 returns spans, and this module measures them against the 153
claudisms Jim flagged by hand in the Opus 5 posts (``annotations/``).

It checks both halves of the evaluator:

- **regex** (``claudisms.py``): always runs, offline and free.
- **judge** (the v2 span judge, run by ``blogwriter-judge``): runs when you
  pass ``--judge-spans``, pointing at the ``<alias>.json`` file it writes.

Three rules from the proposal are enforced here:

1. **Calibrate on r1, test on r2.** ``--split r1`` for tuning the prompt, then
   ``--split r2`` once for the number you report.
2. **Recall is the headline.** A flag counts as found if any span overlaps the
   flagged sentence. Precision needs a human, because the flags are not
   exhaustive: ``--unflagged-out`` writes the judge spans nobody flagged, for
   a spot check.
3. **Load-bearing is a must-catch.** Every known "load-bearing" sentence must
   be caught by each half that ran. A miss exits non-zero whatever the recall.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .claudisms import CLAUDE_LEANING, GENERIC_LLM
from .determinism import REPO_ROOT, print_stderr
from .judge_spec import parse_judge_output

DEFAULT_ANNOTATIONS = REPO_ROOT / "annotations" / "opus-5-full-v1.json"

# The load-bearing sentences in output/full-v1/opus-5, as (doc_id, snippet).
# Opus 5.5 used the phrase zero times in the same run.
KNOWN_LOAD_BEARING: list[tuple[str, str]] = [
    ("why-novels-open-with-prologues.r2.md", "It is load-bearing."),
    ("why-agent-demos-fail-in-production.r1.md", "becomes load-bearing on long runs"),
    ("against-the-stand-mixer.r1.md", "This is the load-bearing argument"),
]

_ALL_PATTERNS = {**CLAUDE_LEANING, **GENERIC_LLM}


def normalise(text: str) -> str:
    """Lower-case, letters and digits only.

    The annotation sentences were exported from a Google Doc, which dropped
    underscores and markdown, so matching has to ignore punctuation entirely.
    """
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def overlaps(span: str, sentence: str, anchor: str) -> bool:
    """True if a detected span and a flagged sentence share the construction."""
    s, sent, anc = normalise(span), normalise(sentence), normalise(anchor)
    if not s:
        return False
    return s in sent or sent in s or (bool(anc) and (anc in s or s in anc))


def regex_hits(sentence: str) -> list[str]:
    """Names of the regex patterns that fire on one sentence."""
    return [
        name
        for name, pattern in _ALL_PATTERNS.items()
        if re.search(pattern, sentence, flags=re.IGNORECASE)
    ]


def load_judge_spans(path: Path) -> dict[str, list[dict[str, str]]]:
    """Read judge output into {doc_id: instances}.

    Takes the ``<alias>.json`` file ``blogwriter-judge`` writes, or any JSON
    object mapping ``<slug>.r<N>.md`` to a raw reply string, an object with an
    ``instances`` key, or a bare instance list.
    """
    data = json.loads(path.read_text())
    out: dict[str, list[dict[str, str]]] = {}
    for doc_id, value in data.items():
        if isinstance(value, str):
            try:
                out[doc_id] = parse_judge_output(value)
            except ValueError:
                print_stderr(f"  unparseable judge output for {doc_id}")
        elif isinstance(value, dict):
            out[doc_id] = parse_judge_output(json.dumps(value))
        else:
            out[doc_id] = parse_judge_output(json.dumps({"instances": value}))
    return out


@dataclass
class Result:
    flags: int = 0
    regex_found: int = 0
    judge_found: int = 0
    judge_docs: int = 0
    judge_flags: int = 0  # flags on posts the judge actually scored
    regex_by_pattern: dict[str, int] = field(default_factory=dict)
    judge_by_category: dict[str, int] = field(default_factory=dict)
    unflagged: list[dict[str, str]] = field(default_factory=list)
    load_bearing_misses: list[str] = field(default_factory=list)


def validate(
    flags: list[dict],
    *,
    split: str = "all",
    judge: dict[str, list[dict[str, str]]] | None = None,
) -> Result:
    if split in ("r1", "r2"):
        wanted = int(split[1])
        flags = [f for f in flags if f["repeat"] == wanted]
    result = Result(flags=len(flags))

    for flag in flags:
        text = f"{flag['sentence']} {flag['quote']}"
        names = regex_hits(text)
        if names:
            result.regex_found += 1
            for name in names:
                result.regex_by_pattern[name] = result.regex_by_pattern.get(name, 0) + 1

    if judge is not None:
        docs = {f["doc_id"] for f in flags}
        scored = {d: judge[d] for d in docs if d in judge}
        result.judge_docs = len(scored)
        by_doc: dict[str, list[dict]] = {}
        for flag in flags:
            by_doc.setdefault(flag["doc_id"], []).append(flag)
        for doc_id, instances in scored.items():
            doc_flags = by_doc.get(doc_id, [])
            result.judge_flags += len(doc_flags)
            for flag in doc_flags:
                if any(
                    overlaps(i["quote"], flag["sentence"], flag["quote"])
                    for i in instances
                ):
                    result.judge_found += 1
            for inst in instances:
                cat = inst["category"]
                result.judge_by_category[cat] = result.judge_by_category.get(cat, 0) + 1
                if not any(
                    overlaps(inst["quote"], f["sentence"], f["quote"])
                    for f in doc_flags
                ):
                    result.unflagged.append({"doc_id": doc_id, **inst})

    # Load-bearing is checked on the posts it occurs in, regardless of split,
    # because it is a regression test rather than part of the recall figure.
    for doc_id, snippet in KNOWN_LOAD_BEARING:
        if not regex_hits(snippet).count("load_bearing"):
            result.load_bearing_misses.append(f"regex missed {doc_id}")
        if judge is not None and doc_id in judge:
            caught = any(
                "load" in i["quote"].lower() and "bear" in i["quote"].lower()
                for i in judge[doc_id]
            )
            if not caught:
                result.load_bearing_misses.append(f"judge missed {doc_id}")
    return result


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({round(100 * n / d)}%)" if d else "-"


def print_result(result: Result, split: str) -> None:
    print(f"  split: {split}   flags: {result.flags}")
    print(f"  regex recall: {_pct(result.regex_found, result.flags)}")
    if result.regex_by_pattern:
        top = sorted(result.regex_by_pattern.items(), key=lambda kv: -kv[1])
        print("    " + ", ".join(f"{k} {v}" for k, v in top))
    if result.judge_docs:
        print(
            f"  judge recall: {_pct(result.judge_found, result.judge_flags)}"
            f"   on {result.judge_docs} scored posts"
        )
        cats = sorted(result.judge_by_category.items(), key=lambda kv: -kv[1])
        print("    spans by category: " + ", ".join(f"{k} {v}" for k, v in cats))
        print(f"    spans nobody flagged: {len(result.unflagged)}")
    if result.load_bearing_misses:
        print("  LOAD-BEARING CHECK FAILED:")
        for miss in result.load_bearing_misses:
            print(f"    - {miss}")
    else:
        print(f"  load-bearing check: all {len(KNOWN_LOAD_BEARING)} caught")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="blogwriter-validate",
        description="Measure the v2 evaluator against hand-flagged claudisms.",
    )
    parser.add_argument("--annotations", default=str(DEFAULT_ANNOTATIONS))
    parser.add_argument(
        "--split",
        choices=("r1", "r2", "all"),
        default="all",
        help="r1 to calibrate, r2 once to report",
    )
    parser.add_argument(
        "--judge-spans",
        help="judge output from blogwriter-judge (output/<run>/judge-v2/opus-5.json)",
    )
    parser.add_argument(
        "--unflagged-out",
        help="write judge spans nobody flagged here, for a precision spot check",
    )
    args = parser.parse_args()

    flags = json.loads(Path(args.annotations).read_text())["flags"]
    judge = load_judge_spans(Path(args.judge_spans)) if args.judge_spans else None
    result = validate(flags, split=args.split, judge=judge)
    print_result(result, args.split)

    if args.unflagged_out and judge is not None:
        dest = Path(args.unflagged_out)
        dest.write_text(json.dumps(result.unflagged, indent=2) + "\n")
        print(f"  -> {dest}")
    return 1 if result.load_bearing_misses else 0


if __name__ == "__main__":
    sys.exit(main())
