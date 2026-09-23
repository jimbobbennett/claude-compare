"""Score generated posts for claudism density, and compare the models.

Two scorers run over each document:

- the deterministic one (``claudisms.py``): fixed phrases and structural
  patterns, no model, no cost, no variance;
- the LLM judge (``judge.py``): the constructions regex cannot see, run on
  OpenAI so the judge is not scoring its own house style.

Everything is normalised per 1000 words, because Opus 5.5 writes longer at the
same word target and raw counts would report "more claudisms" from length
alone.

``--briefs`` scores the research briefs with the same scorers. That is the
contamination control: if brief density is near zero and post density is not,
the posts are the source. If the briefs score high, the writers may simply be
echoing their input and the headline number means much less.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from openinference.instrumentation import using_metadata
from openinference.semconv.trace import (
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import Status, StatusCode

from .claudisms import PATTERN_VERSION, score_text, strip_front_matter
from .determinism import BRIEFS_DIR, REPO_ROOT, print_stderr, utc_now
from .judge import DEFAULT_JUDGE_MODEL, JudgeResult, judge_document
from .tracing import get_tracer, init_tracing, shutdown_tracing


@dataclass
class DocumentScore:
    doc_id: str
    kind: str  # "post" or "brief"
    model_alias: str | None
    topic_slug: str
    word_count: int
    deterministic: dict = field(default_factory=dict)
    judge: dict | None = None


def _front_matter_value(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3 : end if end != -1 else len(text)]
    for line in block.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def score_document(
    *,
    path: Path,
    kind: str,
    topic_slug: str,
    model_alias: str | None,
    run_id: str,
    judge_model: str | None,
    judge_passes: int,
) -> DocumentScore:
    raw = path.read_text()
    body = strip_front_matter(raw)
    det = score_text(raw)

    result = DocumentScore(
        doc_id=path.name,
        kind=kind,
        model_alias=model_alias,
        topic_slug=topic_slug,
        word_count=det.word_count,
        deterministic={
            "pattern_version": PATTERN_VERSION,
            "claude_leaning": det.claude_leaning,
            "claude_leaning_total": det.claude_leaning_total,
            "generic_llm": det.generic_llm,
            "generic_llm_total": det.generic_llm_total,
            "structural": det.structural,
            "densities": det.densities(),
            "matches": det.matches,
        },
    )

    if judge_model is None:
        return result

    tracer = get_tracer()
    metadata = {
        "stage": "evaluate",
        "kind": kind,
        "topic_slug": topic_slug,
        "model_alias": model_alias or "-",
        "run_id": run_id,
        "judge_model": judge_model,
        "pattern_version": PATTERN_VERSION,
    }
    with using_metadata(metadata):
        with tracer.start_as_current_span(f"judge[{path.name}]") as span:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.EVALUATOR.value,
            )
            span.set_attribute(SpanAttributes.INPUT_VALUE, body[:20000])
            jr: JudgeResult = judge_document(
                body, model=judge_model, passes=judge_passes
            )
            per_1k = (
                round(jr.verified_total * 1000 / det.word_count, 2)
                if det.word_count
                else 0.0
            )
            result.judge = {
                "model": jr.model,
                "prompt_version": jr.prompt_version,
                "passes": jr.passes,
                "rating": jr.rating,
                "rationale": jr.rationale,
                "counts": jr.counts,
                "verified_total": jr.verified_total,
                "verified_per_1k": per_1k,
                "unverified_total": len(jr.unverified),
                "verified": jr.verified,
                "unverified": jr.unverified,
                "input_tokens": jr.input_tokens,
                "output_tokens": jr.output_tokens,
            }
            span.set_attribute(
                SpanAttributes.OUTPUT_VALUE,
                json.dumps({"rating": jr.rating, "counts": jr.counts}),
            )
            if jr.rating is not None:
                span.set_attribute("eval.claudism.rating", jr.rating)
            span.set_attribute("eval.claudism.verified_per_1k", per_1k)
            span.set_attribute("eval.claudism.unverified_total", len(jr.unverified))
            # start_as_current_span never sets OK, only ERROR on an exception.
            span.set_status(Status(StatusCode.OK))

    return result


def _mean(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(statistics.mean(clean), 2) if clean else None


def summarise(scores: list[DocumentScore]) -> dict:
    """Aggregate per model (posts) and overall (briefs)."""
    groups: dict[str, list[DocumentScore]] = {}
    for s in scores:
        key = s.model_alias if s.kind == "post" else "BRIEFS (baseline)"
        groups.setdefault(key or "-", []).append(s)

    out: dict[str, dict] = {}
    for key, items in sorted(groups.items()):
        dens = [i.deterministic["densities"] for i in items]
        summary = {
            "documents": len(items),
            "mean_word_count": _mean([float(i.word_count) for i in items]),
            "claude_leaning_per_1k": _mean([d["claude_leaning_per_1k"] for d in dens]),
            "generic_llm_per_1k": _mean([d["generic_llm_per_1k"] for d in dens]),
            "em_dash_per_1k": _mean([d["em_dash_per_1k"] for d in dens]),
            "bold_leadin_bullet_per_1k": _mean(
                [d["bold_leadin_bullet_per_1k"] for d in dens]
            ),
            "rule_of_three_per_1k": _mean([d["rule_of_three_per_1k"] for d in dens]),
        }
        judged = [i.judge for i in items if i.judge]
        if judged:
            summary["judge_verified_per_1k"] = _mean(
                [j["verified_per_1k"] for j in judged]
            )
            summary["judge_rating"] = _mean(
                [float(j["rating"]) for j in judged if j["rating"] is not None]
            )
            summary["judge_unverified_total"] = sum(
                j["unverified_total"] for j in judged
            )
        out[key] = summary
    return out


def _print_table(summary: dict) -> None:
    cols = [
        ("documents", "docs", 5),
        ("mean_word_count", "words", 7),
        ("claude_leaning_per_1k", "claude/1k", 10),
        ("generic_llm_per_1k", "generic/1k", 11),
        ("em_dash_per_1k", "emdash/1k", 10),
        ("rule_of_three_per_1k", "three/1k", 9),
        ("judge_verified_per_1k", "judge/1k", 9),
        ("judge_rating", "rating", 7),
    ]
    header = f"  {'group':20}" + "".join(f"{label:>{w}}" for _, label, w in cols)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for key, row in summary.items():
        line = f"  {key:20}"
        for field_name, _, w in cols:
            value = row.get(field_name)
            line += f"{(value if value is not None else '-'):>{w}}"
        print(line)


def collect_posts(out_root: Path, run_id: str) -> list[tuple[Path, str, str]]:
    """Return (path, model_alias, topic_slug) for every post in a run."""
    run_dir = out_root / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"no such run: {run_dir}")
    found = []
    for path in sorted(run_dir.glob("*/*.md")):
        model_alias = _front_matter_value(path.read_text(), "model_alias")
        slug = _front_matter_value(path.read_text(), "slug") or path.stem.split(".r")[0]
        found.append((path, model_alias or path.parent.name, slug))
    return found


def run(args: argparse.Namespace) -> int:
    out_root = Path(args.out)
    judge_model = None if args.no_judge else args.judge_model

    docs: list[tuple[Path, str, str, str | None]] = []
    if args.run_id:
        try:
            for path, alias, slug in collect_posts(out_root, args.run_id):
                docs.append((path, "post", slug, alias))
        except FileNotFoundError as exc:
            print_stderr(f"error: {exc}")
            return 2
    if args.briefs:
        for path in sorted(BRIEFS_DIR.glob("*.md")):
            docs.append((path, "brief", path.stem, None))

    if not docs:
        print_stderr("error: nothing to score. Pass --run-id and/or --briefs.")
        return 2

    print(
        f"scoring {len(docs)} document(s)  "
        f"judge={judge_model or 'DISABLED'}"
        + (f" x{args.judge_passes}" if judge_model else "")
    )

    if judge_model:
        init_tracing()
    scores: list[DocumentScore] = []
    failures = 0
    try:
        for path, kind, slug, alias in docs:
            label = f"{kind:6} {(alias or '-'):9} {path.name}"
            try:
                score = score_document(
                    path=path,
                    kind=kind,
                    topic_slug=slug,
                    model_alias=alias,
                    run_id=args.run_id or "briefs-only",
                    judge_model=judge_model,
                    judge_passes=args.judge_passes,
                )
            except Exception as exc:
                failures += 1
                print_stderr(f"  FAIL  {label}  {exc}")
                continue
            scores.append(score)
            det = score.deterministic
            jt = score.judge["verified_per_1k"] if score.judge else "-"
            rating = score.judge["rating"] if score.judge else "-"
            print(
                f"  ok    {label}  {score.word_count:5}w  "
                f"claude/1k={det['densities']['claude_leaning_per_1k']:6}  "
                f"judge/1k={jt:6}  rating={rating}"
            )
    finally:
        if judge_model:
            shutdown_tracing()

    summary = summarise(scores)
    print()
    _print_table(summary)

    report = {
        "generated_at": utc_now(),
        "run_id": args.run_id,
        "pattern_version": PATTERN_VERSION,
        "judge_model": judge_model,
        "judge_passes": args.judge_passes if judge_model else 0,
        "summary": summary,
        "documents": [asdict(s) for s in scores],
    }
    dest = (
        out_root / args.run_id / "eval.json"
        if args.run_id
        else REPO_ROOT / "briefs-eval.json"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\n  -> {dest.relative_to(REPO_ROOT)}")

    if failures:
        print_stderr(f"{failures} document(s) failed")
        return 1
    return 0


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="blogwriter-eval",
        description="Score posts for claudism density and compare the models.",
    )
    parser.add_argument("--run-id", help="score the posts in output/<run_id>/")
    parser.add_argument(
        "--briefs",
        action="store_true",
        help="also score briefs/ as the contamination baseline",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help=f"OpenAI judge model (default {DEFAULT_JUDGE_MODEL})",
    )
    parser.add_argument(
        "--judge-passes",
        type=int,
        default=1,
        help="judge runs per document; these models reject temperature=0, so "
        "more passes damp variance",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="deterministic scoring only (free, no model calls)",
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "output"))
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
