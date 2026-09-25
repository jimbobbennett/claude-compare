"""Read AX evaluation results back and rank the models.

The evaluators run **in Arize AX** (see the README), not here. This module
only reads what AX produced and aggregates it, so the answer to "which model
scores best" comes out of AX's own scoring rather than a local reimplementation.

Two things about the AX shape are easy to get wrong and are handled here:

- **Eval results arrive in a top-level ``evaluations`` array on each span**, not
  under ``attributes``. Looking for ``attributes.eval.*`` finds nothing.
- **The eval index wants full attribute paths in filters.** ``span_kind =
  'CHAIN'`` matches zero rows; ``attributes.openinference.span.kind = 'CHAIN'``
  is what works.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from .ax_experiments import ax_binary
from .determinism import print_stderr

DEFAULT_PROJECT = "claude-compare-blogwriter"
# No default space: it is account-specific. Set ARIZE_SPACE or pass --space.
DEFAULT_SPACE = os.environ.get("ARIZE_SPACE", "")
# Only spans AX has actually scored.
SCORED_FILTER = "eval.claudism_density.label IS NOT NULL"
BRIEF_GROUP = "BRIEFS (baseline)"

# --- colour ----------------------------------------------------------------
#
# **Red = obviously Claude. Green = doesn't read as Claude.**
#
# Higher claudism density is the thing being flagged, so the scale runs the way
# a warning scale runs: red for saturated signature style, green for prose that
# reads as unmarked. The evaluator in AX is set to MINIMIZE to match, so its own
# column colouring agrees with this table rather than contradicting it.

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
BRIGHT_GREEN = "\033[92m"
AMBER = "\033[33m"
RED = "\033[31m"
BRIGHT_RED = "\033[91m"

LABEL_COLOURS: dict[str, str] = {
    "saturated": BRIGHT_RED,
    "strong": RED,
    "moderate": AMBER,
    "faint": GREEN,
    "absent": BRIGHT_GREEN,
    # code-evaluator labels
    "heavy": BRIGHT_RED,
    "light": GREEN,
    "none": BRIGHT_GREEN,
    "no_text": DIM,
}


def _use_colour(force: bool = False) -> bool:
    """Colour only when it will be read by a human.

    Off when piped, so escape codes never land in captured output, and off when
    NO_COLOR is set. An explicit ``--color`` overrides both, matching how
    ``--color=always`` behaves in ripgrep and friends.
    """
    import os

    if force:
        return True
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class Paint:
    """Wraps colouring so every call site stays readable."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, text: str, colour: str) -> str:
        return f"{colour}{text}{RESET}" if self.enabled else text

    def label(self, text: str) -> str:
        return self._wrap(text, LABEL_COLOURS.get(text, ""))

    def score(self, value: float | None, *, amber_at: float, red_at: float) -> str:
        """Colour a number where HIGHER is more obviously Claude.

        Thresholds are named for the band they open so the direction of the
        scale is unmistakable at the call site.
        """
        if value is None:
            return "-"
        if value >= red_at:
            colour = RED
        elif value >= amber_at:
            colour = AMBER
        else:
            colour = GREEN
        return self._wrap(str(value), colour)

    def not_applicable(self, value: float | None) -> str:
        """Dim a figure that is real but not comparable on this metric."""
        if value is None:
            return "-"
        return self._wrap(f"{value}*", DIM)

    def bold(self, text: str) -> str:
        return self._wrap(text, BOLD)

    def dim(self, text: str) -> str:
        return self._wrap(text, DIM)


def export_scored_spans(project: str, space: str, limit: int) -> list[dict]:
    """Shell out to `ax spans export` and return the span objects."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                ax_binary(), "spans", "export", project,
                "--space", space,
                "--filter", SCORED_FILTER,
                "-l", str(limit),
                "--output-dir", tmp,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        files = list(Path(tmp).glob("*/spans.json"))
        if not files:
            raise RuntimeError(
                "ax spans export produced no file.\n"
                f"stdout: {result.stdout[-400:]}\nstderr: {result.stderr[-400:]}"
            )
        return json.loads(files[0].read_text())


# Model alias -> the model ID that must have served the span. A span whose
# recorded model does not match its label is not usable evidence: it is either
# an aborted run (no post) or a substituted model (wrong author).
EXPECTED_MODEL = {"opus-5": "claude-opus-5", "opus-5.5": "claude-opus-5-5"}


def integrity_problem(span: dict) -> str | None:
    """Return why a span is unusable, or None if it is sound.

    The model gate prevents mislabelled posts from being *written*, but spans
    from before the gate existed -- and from runs the gate aborted midway --
    are still in the project and will otherwise be scored and averaged in.
    """
    attributes = span.get("attributes") or {}
    metadata = attributes.get("metadata") or {}
    alias = metadata.get("model_alias")
    served = attributes.get("llm.model_name")
    if alias in EXPECTED_MODEL:
        if not served:
            return "no llm.model_name (aborted run, no post written)"
        if served != EXPECTED_MODEL[alias]:
            return f"labelled {alias} but served by {served}"
    return None


def group_key(span: dict) -> str | None:
    """Posts group by model alias; research spans are the brief baseline."""
    name = span.get("name") or ""
    metadata = (span.get("attributes") or {}).get("metadata") or {}
    if name.startswith("write_post"):
        return metadata.get("model_alias") or name
    if name.startswith("research"):
        return BRIEF_GROUP
    return None


def aggregate(
    spans: list[dict],
    *,
    run_ids: set[str] | None = None,
    include_unsound: bool = False,
) -> tuple[dict[str, dict], list[str]]:
    """Aggregate scored spans, returning (summary, excluded reasons)."""
    groups: dict[str, list[dict]] = {}
    excluded: list[str] = []
    for span in spans:
        key = group_key(span)
        if key is None:
            continue
        metadata = (span.get("attributes") or {}).get("metadata") or {}
        if run_ids and metadata.get("run_id") not in run_ids:
            continue
        problem = integrity_problem(span)
        if problem and not include_unsound:
            excluded.append(
                f"{metadata.get('run_id', '?')}/{metadata.get('model_alias', '?')}"
                f": {problem}"
            )
            continue
        evals = {
            e["name"]: e for e in (span.get("evaluations") or []) if e.get("name")
        }
        if evals:
            groups.setdefault(key, []).append(evals)

    out: dict[str, dict] = {}
    for key, rows in groups.items():
        claudism = [
            r["claudism_density"]["score"]
            for r in rows
            if "claudism_density" in r
            and isinstance(r["claudism_density"].get("score"), (int, float))
        ]
        em_dash = [
            r["em_dash_density"]["score"]
            for r in rows
            if "em_dash_density" in r
            and isinstance(r["em_dash_density"].get("score"), (int, float))
        ]
        labels = [
            r["claudism_density"]["label"] for r in rows if "claudism_density" in r
        ]
        out[key] = {
            "n": len(rows),
            "claudism_mean": round(statistics.mean(claudism), 2) if claudism else None,
            "claudism_stdev": (
                round(statistics.stdev(claudism), 2) if len(claudism) > 1 else None
            ),
            "claudism_modal_label": (
                Counter(labels).most_common(1)[0][0] if labels else None
            ),
            "em_dash_mean": round(statistics.mean(em_dash), 2) if em_dash else None,
            "label_counts": dict(Counter(labels)),
        }
    return out, excluded


_ANSI = re.compile(r"\033\[[0-9;]*m")


def _visible_len(text: str) -> int:
    return len(_ANSI.sub("", text))


def _rpad(text: str, width: int) -> str:
    """Right-align to a visible width, ignoring ANSI escapes.

    Plain f-string padding counts escape bytes and silently misaligns every
    coloured column.
    """
    return " " * max(0, width - _visible_len(text)) + text


def _lpad(text: str, width: int) -> str:
    return text + " " * max(0, width - _visible_len(text))


def print_report(summary: dict[str, dict], paint: Paint) -> None:
    def sort_key(item: tuple[str, dict]) -> tuple:
        # Baseline last; otherwise highest claudism score first.
        key, row = item
        return (key == BRIEF_GROUP, -(row["claudism_mean"] or 0))

    rows = sorted(summary.items(), key=sort_key)
    header = (
        f"  {'group':22}{'n':>4}{'claudism':>10}{'sd':>7}"
        f"{'modal label':>14}{'em_dash/1k':>12}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for key, row in rows:
        # Bands for the 1-5 rubric: >=3.5 reads as Claude, <2.5 does not.
        claudism = paint.score(row["claudism_mean"], amber_at=2.5, red_at=3.5)
        # The briefs' em-dashes are list punctuation, not prose style, so the
        # figure is shown but never coloured as if it were comparable.
        em_dash = (
            paint.not_applicable(row["em_dash_mean"])
            if key == BRIEF_GROUP
            else paint.score(row["em_dash_mean"], amber_at=3.0, red_at=10.0)
        )
        label = paint.label(row["claudism_modal_label"] or "-")
        sd = row["claudism_stdev"]
        print(
            f"  {_lpad(key, 22)}{row['n']:>4}"
            f"{_rpad(claudism, 10)}"
            f"{(sd if sd is not None else '-'):>7}"
            f"{_rpad(label, 14)}"
            f"{_rpad(em_dash, 12)}"
        )

    if BRIEF_GROUP in summary:
        print(
            "  "
            + paint.dim("* brief em-dashes are list punctuation, not prose style")
        )

    legend = (
        "  "
        + paint.dim("scale: ")
        + " ".join(
            paint.label(name)
            for name in ("absent", "faint", "moderate", "strong", "saturated")
        )
        + paint.dim("  (red = obviously Claude, green = doesn't read as Claude)")
    )
    print()
    print(legend)

    models = [(k, v) for k, v in rows if k != BRIEF_GROUP and v["claudism_mean"]]
    if len(models) < 2:
        return
    top, second = models[0], models[1]
    margin = round(top[1]["claudism_mean"] - second[1]["claudism_mean"], 2)
    least = models[-1]
    print(
        f"\n  Most obviously Claude: {paint.bold(top[0])} "
        f"({paint.score(top[1]['claudism_mean'], amber_at=2.5, red_at=3.5)})"
        f"   Least: {paint.bold(least[0])} "
        f"({paint.score(least[1]['claudism_mean'], amber_at=2.5, red_at=3.5)})"
        f"   gap {margin}"
    )
    baseline = summary.get(BRIEF_GROUP, {}).get("claudism_mean")
    if baseline is not None:
        print(
            f"  Brief baseline "
            f"{paint.score(baseline, amber_at=2.5, red_at=3.5)}"
            " - the gap to it is what makes the post scores meaningful."
        )
    smallest = min(v["n"] for _, v in models)
    if smallest < 10:
        print(
            "  "
            + paint._wrap("CAUTION", AMBER)
            + f": smallest group has n={smallest}. Treat the ranking as "
            "directional until the full matrix is scored."
        )


def crosstab(
    spans: list[dict], dimension: str, *, include_unsound: bool = False
) -> dict[str, dict[str, float | None]]:
    """Mean claudism score per (dimension value x model alias).

    This is what the domain axis is for: it answers whether the gap between the
    models holds outside AI topics, or is an artefact of dense technical prose.
    """
    cells: dict[tuple[str, str], list[float]] = {}
    for span in spans:
        if not (span.get("name") or "").startswith("write_post"):
            continue
        if integrity_problem(span) and not include_unsound:
            continue
        metadata = (span.get("attributes") or {}).get("metadata") or {}
        alias = metadata.get("model_alias")
        value = metadata.get(dimension) or "unspecified"
        evals = {e["name"]: e for e in (span.get("evaluations") or [])}
        score = evals.get("claudism_density", {}).get("score")
        if alias and isinstance(score, (int, float)):
            cells.setdefault((value, alias), []).append(score)
    out: dict[str, dict[str, float | None]] = {}
    for (value, alias), scores in cells.items():
        out.setdefault(value, {})[alias] = round(statistics.mean(scores), 2)
    return out


def print_crosstab(
    table: dict[str, dict[str, float | None]], dimension: str, paint: Paint
) -> None:
    aliases = sorted({a for row in table.values() for a in row})
    if not aliases:
        return
    header = f"  {dimension:22}" + "".join(f"{a:>11}" for a in aliases) + f"{'gap':>8}"
    print(f"\n  claudism score by {dimension}:")
    print(header)
    print("  " + "-" * (len(header) - 2))
    for value in sorted(table):
        row = table[value]
        line = f"  {_lpad(value, 22)}"
        for alias in aliases:
            line += _rpad(
                paint.score(row.get(alias), amber_at=2.5, red_at=3.5), 11
            )
        present = [row.get(a) for a in aliases if row.get(a) is not None]
        gap = round(max(present) - min(present), 2) if len(present) > 1 else None
        line += f"{(gap if gap is not None else '-'):>8}"
        print(line)


def run(args: argparse.Namespace) -> int:
    if not args.space:
        print_stderr(
            "error: no Arize space given. Pass --space, or set ARIZE_SPACE. "
            "List them with: ax spaces list"
        )
        return 2
    try:
        spans = export_scored_spans(args.project, args.space, args.limit)
    except Exception as exc:
        print_stderr(f"error: {exc}")
        return 1

    paint = Paint(_use_colour(force=args.color))
    run_ids = set(args.run_id) if args.run_id else None
    summary, excluded = aggregate(
        spans, run_ids=run_ids, include_unsound=args.include_unsound
    )
    if not summary:
        print_stderr(
            "no scored spans found. Either the AX task has not run yet, or the "
            "eval index has not caught up (it lags ingestion by 1-2 hours)."
        )
        return 1

    print(f"scored spans: {sum(r['n'] for r in summary.values())}")
    if run_ids:
        print(f"  restricted to run_id: {', '.join(sorted(run_ids))}")
    for reason in excluded:
        print("  " + paint._wrap(f"excluded {reason}", AMBER))
    print()
    print_report(summary, paint)

    if args.by:
        table = crosstab(
            spans, args.by, include_unsound=args.include_unsound
        )
        if run_ids:
            # crosstab reads the raw spans, so apply the same run filter.
            table = crosstab(
                [
                    sp
                    for sp in spans
                    if ((sp.get("attributes") or {}).get("metadata") or {}).get(
                        "run_id"
                    )
                    in run_ids
                ],
                args.by,
                include_unsound=args.include_unsound,
            )
        print_crosstab(table, args.by, paint)

    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2) + "\n")
        print(f"\n  -> {args.json}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="blogwriter-ax-report",
        description="Read AX evaluation results and rank the models.",
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument(
        "--space",
        default=DEFAULT_SPACE,
        help="Arize space name or ID. Defaults to $ARIZE_SPACE.",
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--run-id",
        action="append",
        help="only include this run_id (repeatable). Use it to exclude "
        "harness-development runs from a result.",
    )
    parser.add_argument(
        "--include-unsound",
        action="store_true",
        help="keep spans whose recorded model contradicts their label "
        "(aborted or substituted runs). Off by default.",
    )
    parser.add_argument(
        "--by",
        choices=["domain", "genre"],
        help="also break the claudism score down by this dimension, to show "
        "whether the gap between models holds across subject areas",
    )
    parser.add_argument("--json", help="also write the summary to this path")
    parser.add_argument(
        "--color",
        action="store_true",
        help="force colour even when piped or when NO_COLOR is set "
        "(as an explicit --color=always would); otherwise colour is used only "
        "on a TTY with NO_COLOR unset",
    )
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
