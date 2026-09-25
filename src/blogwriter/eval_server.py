"""The v2.2 span judge as an Arize AX remote evaluator.

AX template evaluators must return one label, which cannot carry the judge's
spans. A remote evaluator can: AX posts each record here and writes back
whatever ``label``, ``score`` and ``explanation`` this returns. So the scoring
is identical to ``blogwriter-judge`` - same prompt, same judge model, same
parsing - but AX runs it, over experiment runs or spans, and stores the result.

Request, as AX sends it::

    {"metadata": {"record_id": ..., ...}, "input": {"output": "<the post>"}}

(``output`` at the top level, beside ``arize_metadata``, is accepted too.)

Response::

    {"score": <spans per 1000 words>, "label": <density band>,
     "explanation": "start-end | category | quote" lines}

The explanation uses the same line format as the ``claudisms`` annotation, so
``blogwriter-ax-experiments recall`` can match the two by position.

Retries: AX retries a request that times out or fails. A judge call can take
a while, so identical concurrent or repeated requests share one call instead
of each paying for their own. Results are held in memory for the life of the
process only; a restart judges afresh.

Run with ``blogwriter-eval-server`` (or ``scripts/serve-evaluator.sh`` to add a
tunnel). Needs ``OPENAI_API_KEY`` and ``CLAUDISM_EVAL_TOKEN``; AX must send
``Authorization: Bearer <CLAUDISM_EVAL_TOKEN>``.
"""

# No `from __future__ import annotations`: FastAPI resolves the `Request`
# annotation at runtime, and it is imported inside create_app.
import asyncio
import hmac
import os
import sys
import time

from .determinism import print_stderr, sha256_text
from .judge import DEFAULT_MODEL, judge_text
from .judge_spec import render_template_v2
from .positions import Located, format_lines, locate

JUDGE_MODEL = os.environ.get("CLAUDISM_JUDGE_MODEL", DEFAULT_MODEL)
PROMPT_SHA = sha256_text(render_template_v2())[:12]


def to_response(result: dict, output: str) -> dict:
    """Turn a ``judge_text`` result into AX's remote evaluator response."""
    items = []
    for inst in result["instances"]:
        span = locate(inst["quote"], output)
        start, end = span if span else (-1, -1)
        items.append(Located(start, end, inst["quote"], inst["category"]))
    return {
        "score": result["instances_per_1k"],
        "label": result["label"],
        "explanation": format_lines(items),
    }


def create_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    api_key = os.environ.get("OPENAI_API_KEY", "")
    token = os.environ.get("CLAUDISM_EVAL_TOKEN", "")
    app = FastAPI()
    inflight: dict[str, asyncio.Task] = {}

    @app.get("/")
    async def health():
        return {
            "ok": bool(api_key and token),
            "judge_model": JUDGE_MODEL,
            "prompt_sha256": PROMPT_SHA,
            "openai_key_configured": bool(api_key),
            "token_configured": bool(token),
        }

    @app.post("/v1/evaluate")
    async def evaluate(req: Request):
        auth = req.headers.get("Authorization", "")
        if not token or not hmac.compare_digest(auth, f"Bearer {token}"):
            return JSONResponse({"error": "unauthorised"}, status_code=401)
        try:
            body = await req.json()
        except ValueError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        # The documented envelope is {"metadata": ..., "input": {fields}}; the
        # API spec describes the fields at the top level beside
        # "arize_metadata". Accept both.
        body = body if isinstance(body, dict) else {}
        fields = body.get("input") if isinstance(body.get("input"), dict) else body
        output = fields.get("output")
        if not isinstance(output, str) or not output.strip():
            return JSONResponse({"error": "input.output must be a non-empty string"},
                                status_code=400)

        key = sha256_text(output)
        task = inflight.get(key)
        if task is None or (task.done() and task.exception()):
            task = asyncio.create_task(asyncio.to_thread(
                judge_text, output, model=JUDGE_MODEL, api_key=api_key))
            inflight[key] = task
        meta = body.get("metadata") or body.get("arize_metadata") or {}
        record = meta.get("record_id", "?") if isinstance(meta, dict) else "?"
        started = time.monotonic()
        try:
            result = await asyncio.shield(task)
        except (RuntimeError, ValueError) as exc:
            print_stderr(f"  {record}: judge failed: {exc}")
            # 5xx so AX retries.
            return JSONResponse({"error": f"judge failed: {exc}"}, status_code=502)
        response = to_response(result, output)
        print_stderr(f"  {record}: {response['score']}/1k, "
                     f"{result['instance_count']} spans, "
                     f"{time.monotonic() - started:.1f}s")
        return response

    return app


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(create_app(), host="127.0.0.1", port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
