"""Single-run CLI: one topic, one model, one post."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import (
    ModelSubstitutionError,
    RefusalError,
    write_output,
    write_post,
)
from .determinism import (
    REPO_ROOT,
    BriefIntegrityError,
    load_verified_brief,
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
from .topics import DEFAULT_TOPICS_PATH, find_topic, load_topics

# Initialised before the Anthropic client is constructed, so the instrumentor
# is in place for every model call.
from .tracing import init_tracing, shutdown_tracing


def run(args: argparse.Namespace) -> int:
    # Resolve and validate everything before spending a token.
    try:
        model_alias, model_id = resolve_model(args.model)
        effort = resolve_effort(args.effort)
    except ModelError as exc:
        print_stderr(f"error: {exc}")
        return 2

    topics = load_topics(Path(args.topics) if args.topics else None)
    try:
        topic = find_topic(topics, args.topic_slug)
    except KeyError as exc:
        print_stderr(f"error: {exc}")
        return 2

    # Verify the brief before touching the network, so a missing or altered
    # fixture fails instantly rather than after tracing is wired up.
    try:
        load_verified_brief(topic.slug)
    except BriefIntegrityError as exc:
        print_stderr(f"error: {exc}")
        return 3

    run_id = args.run_id or f"run-{utc_now().replace(':', '').replace('-', '')}"

    init_tracing()
    try:
        post = write_post(
            slug=topic.slug,
            topic=topic.topic,
            model_alias=model_alias,
            model_id=model_id,
            effort=effort,
            word_target=args.word_target,
            run_id=run_id,
            genre=topic.genre,
            domain=topic.domain,
        )
    except BriefIntegrityError as exc:
        print_stderr(f"error: {exc}")
        return 3
    except ModelSubstitutionError as exc:
        print_stderr(f"error: {exc}")
        return 4
    except RefusalError as exc:
        print_stderr(f"error: {exc}")
        return 5
    finally:
        shutdown_tracing()

    path = write_output(post, Path(args.out))
    c = post.call
    print(
        f"{post.model_alias:9} {post.slug:38} {post.word_count:5} words  "
        f"{c.total_tokens or '?':>7} tok  "
        f"think={c.thinking_tokens if c.thinking_tokens is not None else '?'}  "
        f"${c.cost_usd if c.cost_usd is not None else '?'}"
    )
    print(f"  -> {path.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="blogwriter",
        description="Write one blog post from a frozen brief with a pinned model.",
    )
    parser.add_argument("--topic-slug", required=True, help="slug from topics.yaml")
    parser.add_argument(
        "--model", default="opus-5", help="alias (opus-5, opus-5.5) or full model ID"
    )
    parser.add_argument(
        "--effort",
        default=DEFAULT_EFFORT,
        help="pinned explicitly; model defaults differ (5=high, 5.5=medium)",
    )
    parser.add_argument("--word-target", type=int, default=DEFAULT_WORD_TARGET)
    parser.add_argument("--topics", default=str(DEFAULT_TOPICS_PATH))
    parser.add_argument("--out", default=str(REPO_ROOT / "output"))
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
