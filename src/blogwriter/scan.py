"""Local deterministic scan of generated posts and briefs.

This is the **free, offline** half of scoring: fixed phrases and structural
counts, no model calls, no variance. It exists alongside the AX evaluators for
two reasons:

- the AX eval index lags ingestion by 1-2 hours, so this gives an immediate
  read while iterating on patterns;
- it produces the per-match detail (every matched phrase, verbatim) that a
  single AX label cannot.

**AX is the source of truth for results.** The LLM judge runs there, not here --
see the README. If a number in a report needs to be defensible, take it from
`blogwriter-ax-report`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .claudisms import PATTERN_VERSION, score_text
from .determinism import BRIEFS_DIR, REPO_ROOT, print_stderr, utc_now


@dataclass
class DocumentScan:
    doc_id: str
    kind: str  # "post" or "brief"
    model_alias: str | None
    topic_slug: str
    word_count: int
    deterministic: dict = field(default_factory=dict)


def front_matter_value(text: str, key: str) -> str | None:
    """Read one key out of the YAML front-matter the harness writes."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3 : end if end != -1 else len(text)]
    for line in block.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def scan_document(
    *, path: Path, kind: str, topic_slug: str, model_alias: str | None
) -> DocumentScan:
    score = score_text(path.read_text())
    return DocumentScan(
        doc_id=path.name,
        kind=kind,
        model_alias=model_alias,
        topic_slug=topic_slug,
        word_count=score.word_count,
        deterministic={
            "pattern_version": PATTERN_VERSION,
            "claude_leaning": score.claude_leaning,
            "claude_leaning_total": score.claude_leaning_total,
            "generic_llm": score.generic_llm,
            "generic_llm_total": score.generic_llm_total,
            "structural": score.structural,
            "densities": score.densities(),
            "matches": score.matches,
        },
    )


def collect_posts(out_root: Path, run_id: str) -> list[tuple[Path, str, str]]:
    """Return (path, model_alias, topic_slug) for every post in a run."""
    run_dir = out_root / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"no such run: {run_dir}")
    found = []
    for path in sorted(run_dir.glob("*/*.md")):
        text = path.read_text()
        alias = front_matter_value(text, "model_alias") or path.parent.name
        slug = front_matter_value(text, "slug") or path.stem.split(".r")[0]
        found.append((path, alias, slug))
    return found


def _mean(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(statistics.mean(clean), 2) if clean else None


def summarise(scans: list[DocumentScan]) -> dict:
    groups: dict[str, list[DocumentScan]] = {}
    for scan in scans:
        key = scan.model_alias if scan.kind == "post" else "BRIEFS (baseline)"
        groups.setdefault(key or "-", []).append(scan)

    out: dict[str, dict] = {}
    for key, items in sorted(groups.items()):
        dens = [i.deterministic["densities"] for i in items]
        out[key] = {
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
    return out


def print_table(summary: dict) -> None:
    cols = [
        ("documents", "docs", 6),
        ("mean_word_count", "words", 8),
        ("claude_leaning_per_1k", "claude/1k", 11),
        ("generic_llm_per_1k", "generic/1k", 11),
        ("em_dash_per_1k", "emdash/1k", 10),
        ("bold_leadin_bullet_per_1k", "bold/1k", 8),
        ("rule_of_three_per_1k", "three/1k", 9),
    ]
    header = f"  {'group':22}" + "".join(f"{label:>{w}}" for _, label, w in cols)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for key, row in summary.items():
        line = f"  {key:22}"
        for name, _, w in cols:
            value = row.get(name)
            line += f"{(value if value is not None else '-'):>{w}}"
        print(line)


def run(args: argparse.Namespace) -> int:
    out_root = Path(args.out)
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
        print_stderr("error: nothing to scan. Pass --run-id and/or --briefs.")
        return 2

    scans = [
        scan_document(path=path, kind=kind, topic_slug=slug, model_alias=alias)
        for path, kind, slug, alias in docs
    ]
    for scan in scans:
        dens = scan.deterministic["densities"]
        print(
            f"  {scan.kind:6} {(scan.model_alias or '-'):9} {scan.doc_id[:34]:36}"
            f"{scan.word_count:6}w  claude/1k={dens['claude_leaning_per_1k']:6}"
            f"  emdash/1k={dens['em_dash_per_1k']:6}"
        )

    summary = summarise(scans)
    print()
    print_table(summary)
    print(
        "\n  Deterministic only. The LLM judge runs in AX -- "
        "use `blogwriter-ax-report` for the graded comparison."
    )

    if args.json:
        report = {
            "generated_at": utc_now(),
            "run_id": args.run_id,
            "pattern_version": PATTERN_VERSION,
            "summary": summary,
            "documents": [asdict(s) for s in scans],
        }
        dest = Path(args.json)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2) + "\n")
        shown = dest.relative_to(REPO_ROOT) if dest.is_relative_to(REPO_ROOT) else dest
        print(f"  -> {shown}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="blogwriter-scan",
        description="Deterministic local scan of posts and briefs (no model calls).",
    )
    parser.add_argument("--run-id", help="scan the posts in output/<run_id>/")
    parser.add_argument(
        "--briefs", action="store_true", help="also scan briefs/ as the baseline"
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "output"))
    parser.add_argument("--json", help="write the full per-match detail to this path")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
