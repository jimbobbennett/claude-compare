"""Run the v2 span judge over a batch of posts.

The v1 judge runs inside AX. v2 cannot: AX template evaluators must return a
classification label, and AX's own instructions override any attempt to put
structured spans in the explanation (see ``judge_spec.render_template_v2``).
So v2 runs here, with the same prompt text an AX evaluator would use and the
a newer judge model than v1, ``gpt-6-luna`` through OpenAI. The judge is still
deliberately not a Claude model.

For each post the judge returns every claudism it finds as an exact quote plus
a category. Output is one JSON file per model, mapping ``<slug>.r<N>.md`` to
the instances and the density score, which ``blogwriter-validate --judge-spans``
reads directly.

The OpenAI chat completions endpoint is called with the standard library, so
this adds no dependency. It needs ``OPENAI_API_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .claudisms import score_text, strip_front_matter
from .determinism import REPO_ROOT, print_stderr, utc_now
from .judge_spec import parse_judge_output, render_template_v2, score_instances
from .scan import collect_posts

DEFAULT_MODEL = "gpt-6-luna"
ENDPOINT = "https://api.openai.com/v1/chat/completions"


def build_prompt(post_text: str) -> str:
    """Fill the v2 template with one post, front-matter removed."""
    return render_template_v2().replace("{output}", strip_front_matter(post_text))


def call_judge(prompt: str, *, model: str, api_key: str, retries: int = 4) -> str:
    """Send one prompt and return the raw reply text."""
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
    ).encode()
    for attempt in range(retries):
        request = urllib.request.Request(
            ENDPOINT,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.loads(response.read())
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, KeyError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"judge call failed: {exc}") from exc
            time.sleep(2**attempt * 5)
    raise RuntimeError("unreachable")


def judge_post(path: Path, *, model: str, api_key: str) -> dict:
    text = path.read_text()
    raw = call_judge(build_prompt(text), model=model, api_key=api_key)
    instances = parse_judge_output(raw)
    return {
        "instances": instances,
        **score_instances(instances, score_text(text).word_count),
    }


def summarise(results: dict[str, dict]) -> dict:
    scores = [r["score"] for r in results.values()]
    per_1k = [r["instances_per_1k"] for r in results.values()]
    by_category: dict[str, int] = {}
    for r in results.values():
        for cat, n in r["by_category"].items():
            by_category[cat] = by_category.get(cat, 0) + n
    return {
        "n": len(results),
        "v2_mean": round(statistics.mean(scores), 2) if scores else None,
        "spans_per_1k": round(statistics.mean(per_1k), 2) if per_1k else None,
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="blogwriter-judge",
        description="Run the v2 span judge over one batch of posts.",
    )
    parser.add_argument("--run-id", required=True, help="batch under output/")
    parser.add_argument("--model", action="append", help="limit to a model alias")
    parser.add_argument("--judge-model", default=DEFAULT_MODEL)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--out-dir", help="where to write <alias>.json (default output/<run>/judge-v2)"
    )
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print_stderr("OPENAI_API_KEY is not set")
        return 2

    out_root = REPO_ROOT / "output"
    posts = collect_posts(out_root, args.run_id)
    if args.model:
        posts = [p for p in posts if p[1] in args.model]
    out_dir = (
        Path(args.out_dir) if args.out_dir else out_root / args.run_id / "judge-v2"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print_stderr(f"judging {len(posts)} posts with {args.judge_model}")
    results: dict[str, dict[str, dict]] = {}
    failures = 0

    def work(item: tuple[Path, str, str]) -> tuple[str, str, dict | None]:
        path, alias, _ = item
        try:
            return (
                alias,
                path.name,
                judge_post(path, model=args.judge_model, api_key=api_key),
            )
        except (RuntimeError, ValueError) as exc:
            print_stderr(f"  {alias}/{path.name}: {exc}")
            return alias, path.name, None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for alias, doc_id, result in pool.map(work, posts):
            if result is None:
                failures += 1
                continue
            results.setdefault(alias, {})[doc_id] = result

    summary = {}
    for alias, docs in sorted(results.items()):
        dest = out_dir / f"{alias}.json"
        dest.write_text(json.dumps(dict(sorted(docs.items())), indent=2) + "\n")
        summary[alias] = summarise(docs)
        print_stderr(f"  -> {dest}")

    meta = {
        "run_id": args.run_id,
        "judge_model": args.judge_model,
        "judged_at": utc_now(),
    }
    (out_dir / "summary.json").write_text(
        json.dumps({**meta, "models": summary}, indent=2) + "\n"
    )

    print(f"  {'model':12}{'n':>4}{'v2':>7}{'spans/1k':>10}  top categories")
    for alias, row in summary.items():
        top = ", ".join(f"{k} {v}" for k, v in list(row["by_category"].items())[:3])
        cells = f"{row['n']:>4}{row['v2_mean']:>7}{row['spans_per_1k']:>10}"
        print(f"  {alias:12}{cells}  {top}")
    if failures:
        print_stderr(f"{failures} posts failed; re-run to fill them in")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
