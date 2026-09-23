"""Batch runner: the model x topic x repeat matrix.

One run_id covers the whole matrix so a batch is a single comparable unit in
Arize. Every brief hash is verified up front -- failing before spending money
beats failing halfway through.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import write_output, write_post
from .determinism import (
    REPO_ROOT,
    BriefIntegrityError,
    capture_versions,
    load_verified_brief,
    lock_digest,
    print_stderr,
    utc_now,
)
from .models import (
    DEFAULT_EFFORT,
    DEFAULT_WORD_TARGET,
    ModelError,
    resolve_effort,
    resolve_model,
)
from .prompts import PROMPT_VERSION
from .topics import DEFAULT_TOPICS_PATH, load_topics
from .tracing import init_tracing, shutdown_tracing


def run(args: argparse.Namespace) -> int:
    try:
        models = [resolve_model(m) for m in args.models.split(",") if m.strip()]
        effort = resolve_effort(args.effort)
    except ModelError as exc:
        print_stderr(f"error: {exc}")
        return 2
    if not models:
        print_stderr("error: --models must name at least one model")
        return 2

    topics = load_topics(Path(args.topics) if args.topics else None)
    if args.only:
        wanted = set(args.only)
        topics = [t for t in topics if t.slug in wanted]
        if not topics:
            print_stderr("error: --only matched no topics")
            return 2

    # Verify every brief before starting.
    try:
        for topic in topics:
            load_verified_brief(topic.slug)
    except BriefIntegrityError as exc:
        print_stderr(f"error: {exc}")
        return 3

    run_id = args.run_id or f"batch-{utc_now().replace(':', '').replace('-', '')}"
    out_root = Path(args.out)
    cells = [
        (topic, alias, model_id, repeat)
        for topic in topics
        for (alias, model_id) in models
        for repeat in range(1, args.repeats + 1)
    ]
    print(
        f"run_id={run_id}  {len(cells)} cells "
        f"({len(topics)} topics x {len(models)} models x {args.repeats} repeats) "
        f"effort={effort}"
    )

    manifest = {
        "run_id": run_id,
        "started_at": utc_now(),
        # The pinned surface, recorded once for the whole batch.
        "pinned": {
            "effort": effort,
            "word_target": args.word_target,
            "prompt_version": PROMPT_VERSION,
            "briefs_lock_digest": lock_digest(),
            "harness": capture_versions(),
            "models": {alias: model_id for alias, model_id in models},
        },
        "cells": [],
    }

    init_tracing()
    failures = 0
    try:
        for topic, alias, model_id, repeat in cells:
            label = f"{alias:9} {topic.slug:38} r{repeat}"
            try:
                post = write_post(
                    slug=topic.slug,
                    topic=topic.topic,
                    model_alias=alias,
                    model_id=model_id,
                    effort=effort,
                    word_target=args.word_target,
                    run_id=run_id,
                    repeat=repeat,
                    genre=topic.genre,
                    domain=topic.domain,
                )
            except Exception as exc:  # a failed cell is recorded, never fatal
                failures += 1
                print_stderr(f"  FAIL  {label}  {exc}")
                manifest["cells"].append(
                    {
                        "topic_slug": topic.slug,
                        "genre": topic.genre,
                        "model_alias": alias,
                        "model_id": model_id,
                        "repeat": repeat,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                continue

            path = write_output(post, out_root)
            c = post.call
            print(
                f"  ok    {label}  {post.word_count:5} words  "
                f"{c.total_tokens or '?':>7} tok  "
                f"think={c.thinking_tokens if c.thinking_tokens is not None else '?'}  "
                f"${c.cost_usd if c.cost_usd is not None else '?'}"
            )
            manifest["cells"].append(
                {
                    "topic_slug": topic.slug,
                    "genre": topic.genre,
                    "model_alias": alias,
                    "model_id": model_id,
                    "served_model": c.served_model,
                    "repeat": repeat,
                    "status": "ok",
                    "path": str(path.relative_to(REPO_ROOT)),
                    "word_count": post.word_count,
                    "input_tokens": c.input_tokens,
                    "input_tokens_uncached": c.uncached_input_tokens,
                    "cache_read_tokens": c.cache_read_tokens,
                    "cache_creation_tokens": c.cache_creation_tokens,
                    "output_tokens": c.output_tokens,
                    "thinking_tokens": c.thinking_tokens,
                    "total_tokens": c.total_tokens,
                    "cost_usd_estimated": c.cost_usd,
                    "stop_reason": c.stop_reason,
                    "prompt_sha256": post.prompt_sha256,
                    "brief_sha256": post.brief_sha256,
                }
            )
    finally:
        shutdown_tracing()

    manifest["finished_at"] = utc_now()
    ok_cells = [c for c in manifest["cells"] if c["status"] == "ok"]
    manifest["summary"] = {
        "cells": len(cells),
        "ok": len(ok_cells),
        "failed": failures,
        "total_cost_usd": round(
            sum(cell.get("cost_usd_estimated") or 0.0 for cell in ok_cells), 4
        ),
    }
    manifest_path = out_root / run_id / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(
        f"\n{len(ok_cells)}/{len(cells)} ok, {failures} failed, "
        f"${manifest['summary']['total_cost_usd']} total"
    )
    print(f"  -> {manifest_path.relative_to(REPO_ROOT)}")
    return 1 if failures else 0


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="blogwriter-batch",
        description="Run the model x topic matrix from frozen briefs.",
    )
    parser.add_argument("--models", default="opus-5,opus-5.5")
    parser.add_argument("--topics", default=str(DEFAULT_TOPICS_PATH))
    parser.add_argument("--only", action="append", help="restrict to slug (repeatable)")
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="samples per cell. Generation is stochastic; 1 is an anecdote.",
    )
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--word-target", type=int, default=DEFAULT_WORD_TARGET)
    parser.add_argument("--out", default=str(REPO_ROOT / "output"))
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
