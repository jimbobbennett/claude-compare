"""Stage A -- brief generation.

Briefs are **fixtures**, not a pipeline stage. They are generated once, written
to briefs/<slug>.md, recorded in briefs/briefs.lock.json, and then left alone.
Regenerating requires --refresh-briefs, which rewrites the lockfile and thereby
marks every earlier result as belonging to a different input generation.

That is what removes research drift from the comparison: the writer reads a
file under version control instead of running its own research.

Research needs the web, but not an agent loop -- the server-side web search
tool runs on Anthropic's infrastructure, so this is still a single request
(continued across ``pause_turn`` boundaries). Note that
``web_search_20260209`` does its own dynamic filtering via code execution
internally, so ``code_execution`` must NOT be declared separately.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import run_model
from .determinism import (
    BriefRecord,
    brief_path,
    capture_versions,
    print_stderr,
    read_lock,
    sha256_text,
    utc_now,
    write_lock,
)
from .models import DEFAULT_EFFORT, RESEARCH_MODEL
from .prompts import (
    RESEARCH_PROMPT_VERSION,
    RESEARCH_SYSTEM,
    build_research_prompt,
    normalize_brief,
)
from .topics import DEFAULT_TOPICS_PATH, Topic, load_topics
from .tracing import init_tracing, shutdown_tracing

# Server-side: runs on Anthropic's infrastructure, no client execution loop.
WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 12,
}


def research_topic(topic: Topic, run_id: str) -> tuple[str, float | None]:
    prompt = build_research_prompt(topic.topic)
    metadata = {
        # Tagged so research spans never mix into the writer comparison in AX.
        "stage": "research",
        "topic_slug": topic.slug,
        "genre": topic.genre,
        "domain": topic.domain,
        "model_id": RESEARCH_MODEL,
        "effort": DEFAULT_EFFORT,
        "run_id": run_id,
        "prompt_version": RESEARCH_PROMPT_VERSION,
        "prompt_sha256": sha256_text(prompt),
    }
    call = run_model(
        prompt=prompt,
        system_prompt=RESEARCH_SYSTEM,
        model_id=RESEARCH_MODEL,
        effort=DEFAULT_EFFORT,
        metadata=metadata,
        span_name=f"research[{topic.slug}]",
        tools=[WEB_SEARCH_TOOL],
        # Only consumed if the server tool pauses the turn.
        max_turns=8,
    )
    return normalize_brief(call.text), call.cost_usd


def run(args: argparse.Namespace) -> int:
    topics = load_topics(Path(args.topics) if args.topics else None)
    if args.only:
        wanted = set(args.only)
        unknown = wanted - {t.slug for t in topics}
        if unknown:
            print_stderr(f"unknown topic slug(s): {', '.join(sorted(unknown))}")
            return 2
        topics = [t for t in topics if t.slug in wanted]

    records = read_lock()
    todo: list[Topic] = []
    for topic in topics:
        if brief_path(topic.slug).exists() and not args.refresh_briefs:
            print(f"  skip   {topic.slug} (brief exists; --refresh-briefs to replace)")
            continue
        todo.append(topic)

    if not todo:
        print("\nNothing to do. Briefs are fixtures -- that is the intent.")
        return 0

    run_id = f"research-{utc_now().replace(':', '').replace('-', '')}"
    init_tracing()
    failures: list[str] = []
    total_cost = 0.0
    try:
        for topic in todo:
            print(f"  research  {topic.slug} ...", flush=True)
            try:
                brief, cost = research_topic(topic, run_id)
            except Exception as exc:  # one bad topic must not lose the others
                print_stderr(f"  FAILED    {topic.slug}: {exc}")
                failures.append(topic.slug)
                continue

            path = brief_path(topic.slug)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(brief.rstrip() + "\n")
            digest = sha256_text(path.read_text())
            records[topic.slug] = BriefRecord(
                slug=topic.slug,
                sha256=digest,
                research_model=RESEARCH_MODEL,
                generated_at=utc_now(),
            )
            write_lock(records, capture_versions())
            total_cost += cost or 0.0
            words = len(brief.split())
            print(
                f"  wrote     briefs/{topic.slug}.md  {digest[:12]}  "
                f"{words} words  ${cost if cost is not None else '?'}"
            )
    finally:
        shutdown_tracing()

    if failures:
        print_stderr(f"\n{len(failures)} topic(s) failed: {', '.join(failures)}")
        return 1
    print(
        f"\n{len(todo)} brief(s) written and locked, ${round(total_cost, 4)} total. "
        "Commit briefs/ to freeze them."
    )
    return 0


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="blogwriter-research",
        description="Generate the frozen research briefs the writer reads.",
    )
    parser.add_argument(
        "--topics", default=str(DEFAULT_TOPICS_PATH), help="path to topics.yaml"
    )
    parser.add_argument(
        "--only", action="append", help="restrict to this topic slug (repeatable)"
    )
    parser.add_argument(
        "--refresh-briefs",
        action="store_true",
        help="replace existing briefs. Invalidates comparison with earlier runs.",
    )
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
