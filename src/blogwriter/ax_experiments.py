"""Represent one batch in Arize AX as a dataset, experiments and annotations.

The posts already exist, written by the harness and traced to AX when they
were generated. This puts the same material into AX's experiment model, so
the comparison lives where AX compares things:

- **dataset**: one example per topic, holding the brief and the exact writer
  prompt both models received (with its SHA-256).
- **experiments**: one per model and repeat (``full-v1 opus-5 r1`` ...), each
  run's output being the post that model wrote for that topic. The runs carry
  the served model, tokens, cost and hashes, so every run traces back to the
  harness record that produced it.
- **annotations**: the hand-flagged claudisms, on the Opus 5 runs, as
  ``claudisms`` (``start-end | quote`` lines) and ``claudism_count``.
- **evaluations**: written by AX itself, from the remote ``claudism_spans``
  evaluator (``eval_server.py``) and the ``Em Dash Density`` code
  evaluator. Nothing here writes an evaluation.

``recall`` reads the evaluator's spans back and scores them against the
annotations, writing ``claudism_recall`` onto each annotated run. ``report``
aggregates the lot.

Subcommands run in order: ``upload``, ``annotate``, then (after the
evaluators have run in AX) ``recall`` and ``report``. State - dataset and
experiment IDs - is kept in ``output/<run>/ax/state.json``.
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
import time
from pathlib import Path

from .claudisms import strip_front_matter
from .determinism import REPO_ROOT, load_verified_brief, print_stderr, sha256_text
from .positions import MAX_TEXT, Located, format_lines, locate, parse_lines
from .prompts import build_writer_prompt
from .topics import load_topics
from .validate import KNOWN_LOAD_BEARING, overlaps

DEFAULT_SPACE = os.environ.get("ARIZE_SPACE", "")
ANNOTATIONS = REPO_ROOT / "annotations" / "opus-5-full-v1.json"
EXPECTED_MODEL = {"opus-5": "claude-opus-5", "opus-5.5": "claude-opus-5-5"}

FLAGS_CONFIG = "claudisms"
COUNT_CONFIG = "claudism_count"
RECALL_CONFIG = "claudism_recall"
SPANS_EVAL = "claudism_spans"
EMDASH_EVAL = "em_dash_density"

# Passed through as extra columns on each experiment run.
RUN_FIELDS = (
    "model_alias",
    "model_id",
    "served_model",
    "repeat",
    "topic_slug",
    "genre",
    "word_count",
    "output_tokens",
    "thinking_tokens",
    "cost_usd_estimated",
    "prompt_sha256",
    "brief_sha256",
)


# --- ax plumbing -----------------------------------------------------------


# Transient server errors worth retrying. A create is never retried blindly,
# because it can take effect even when the call reports failure.
TRANSIENT = ("502", "503", "504", "429", "timed out")


def ax_binary() -> str:
    """The ``ax`` to run: ``$AX_BIN``, else the first on PATH outside Python.

    A Python interpreter puts its own ``bin`` first on PATH for subprocesses.
    If an old ``ax`` was ever pip-installed into that interpreter, it shadows
    the real CLI, and an old CLI fails on fields newer servers return (seen:
    "additional fields (not defined in Experiment) in the input: space_id").
    """
    if os.environ.get("AX_BIN"):
        return os.environ["AX_BIN"]
    skip = {Path(sys.executable).parent.resolve(),
            (Path(sys.base_prefix) / "bin").resolve()}
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or Path(entry).resolve() in skip:
            continue
        candidate = Path(entry) / "ax"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "ax"


def ax(*args: str, parse: bool = True, retries: int = 8):
    """Run an ``ax`` command, retrying transient errors, raising on failure."""
    for attempt in range(retries):
        result = subprocess.run(
            [ax_binary(), *args], capture_output=True, text=True, check=False
        )
        detail = (result.stderr or result.stdout)[-800:]
        if result.returncode == 0:
            break
        # Never blindly retry a create: it may have taken effect.
        if "create" in args or not any(t in detail for t in TRANSIENT):
            raise RuntimeError(f"ax {' '.join(args[:3])} failed:\n{detail}")
        if attempt == retries - 1:
            raise RuntimeError(f"ax {' '.join(args[:3])} failed:\n{detail}")
        wait = min(60, 5 * 2**attempt)
        print_stderr(f"  ax {args[0]} {args[1]}: transient error, retry in {wait}s")
        time.sleep(wait)
    if not parse:
        return result.stdout
    out = result.stdout
    starts = [i for i in (out.find("{"), out.find("[")) if i >= 0]
    if not starts:
        raise RuntimeError(f"no JSON from ax {' '.join(args[:3])}: {out[-400:]}")
    return json.loads(out[min(starts) :])


def with_file(payload, *args: str, parse: bool = True):
    """Run an ``ax`` command whose ``--file`` is ``payload`` as JSON."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        if not parse:
            return ax(*args, "--file", path, parse=False)
        return ax(*args, "--file", path, "-o", "json")
    finally:
        os.unlink(path)


def export_runs(experiment: str, dataset_id: str) -> list[dict]:
    return ax("experiments", "export", experiment, "--dataset", dataset_id,
              "--stdout")


def experiment_name(run_id: str, alias: str, repeat: int) -> str:
    return f"{run_id} {alias} r{repeat}"


# --- state -----------------------------------------------------------------


def state_path(run_id: str) -> Path:
    return REPO_ROOT / "output" / run_id / "ax" / "state.json"


def load_state(run_id: str) -> dict:
    path = state_path(run_id)
    if not path.exists():
        raise SystemExit(f"no AX state for {run_id}; run `upload` first")
    return json.loads(path.read_text())


# --- building the records --------------------------------------------------


def load_manifest(run_id: str) -> dict:
    return json.loads((REPO_ROOT / "output" / run_id / "manifest.json").read_text())


def build_examples(manifest: dict) -> list[dict]:
    """One dataset example per topic, verified against the batch manifest."""
    word_target = manifest["pinned"]["word_target"]
    by_slug: dict[str, set[str]] = {}
    for cell in manifest["cells"]:
        by_slug.setdefault(cell["topic_slug"], set()).add(cell["prompt_sha256"])

    examples = []
    for topic in load_topics():
        if topic.slug not in by_slug:
            continue
        brief, brief_sha = load_verified_brief(topic.slug)
        prompt = build_writer_prompt(topic.topic, brief, word_target)
        prompt_sha = sha256_text(prompt)
        if by_slug[topic.slug] != {prompt_sha}:
            raise SystemExit(
                f"{topic.slug}: the rendered prompt does not match the one the "
                "batch used; the dataset would not describe what the models saw"
            )
        examples.append(
            {
                "topic_slug": topic.slug,
                "topic": topic.topic,
                "genre": topic.genre,
                "domain": topic.domain,
                "brief": brief,
                "brief_sha256": brief_sha,
                "prompt": prompt,
                "prompt_sha256": prompt_sha,
                "word_target": word_target,
            }
        )
    return examples


def build_runs(manifest: dict, example_ids: dict[str, str]) -> dict[str, list[dict]]:
    """Experiment runs keyed by experiment name, one per post."""
    experiments: dict[str, list[dict]] = {}
    for cell in manifest["cells"]:
        alias = cell["model_alias"]
        if cell["status"] != "ok":
            raise SystemExit(f"{cell['path']}: status {cell['status']}")
        if not cell["served_model"] == cell["model_id"] == EXPECTED_MODEL[alias]:
            raise SystemExit(
                f"{cell['path']}: served by {cell['served_model']}, labelled {alias}"
            )
        post = strip_front_matter((REPO_ROOT / cell["path"]).read_text())
        run = {
            "example_id": example_ids[cell["topic_slug"]],
            "output": post,
            "source_run_id": manifest["run_id"],
            "post_sha256": sha256_text(post),
            **{k: cell.get(k) for k in RUN_FIELDS},
        }
        name = experiment_name(manifest["run_id"], alias, cell["repeat"])
        experiments.setdefault(name, []).append(run)
    return experiments


# --- upload ----------------------------------------------------------------


def list_experiments(dataset_id: str) -> dict[str, str]:
    data = ax("experiments", "list", "--dataset", dataset_id, "-o", "json")
    return {e["name"]: e["id"] for e in data.get("experiments", [])}


def create_experiment(name: str, runs: list[dict], dataset_id: str) -> str:
    """Create one experiment, verifying it rather than trusting the reply.

    A create sent seconds after the dataset was made has failed with a
    spurious error while still creating the experiment. So on failure this
    looks for it, and on success it counts the runs AX actually holds.
    """
    for attempt in range(3):
        try:
            with_file(runs, "experiments", "create", "--name", name,
                      "--dataset", dataset_id)
            break
        except RuntimeError as exc:
            partial = list_experiments(dataset_id).get(name)
            if partial:
                ax("experiments", "delete", partial, "--force", parse=False)
            if attempt == 2:
                raise
            print_stderr(f"  {name}: create failed, retrying ({exc})")
            time.sleep(10 * (attempt + 1))
    exp_id = list_experiments(dataset_id)[name]
    held = export_runs(name, dataset_id)
    if len(held) != len(runs):
        raise SystemExit(f"{name}: AX holds {len(held)} runs, sent {len(runs)}")
    return exp_id


def cmd_upload(args: argparse.Namespace) -> int:
    """Create the dataset and experiments. Safe to re-run: it resumes."""
    manifest = load_manifest(args.run_id)
    examples = build_examples(manifest)
    dataset = f"claude-compare-{args.run_id}"
    path = state_path(args.run_id)
    state = json.loads(path.read_text()) if path.exists() else {}

    try:
        rows = export_dataset(dataset, args.space)
    except RuntimeError:
        rows = []
    if rows:
        print(f"  dataset {dataset}: exists, {len(rows)} examples")
    else:
        with_file(examples, "datasets", "create", "--name", dataset,
                  "--space", args.space)
        time.sleep(10)
        rows = export_dataset(dataset, args.space)
        print(f"  dataset {dataset}: created, {len(rows)} examples")
    held = {row_field(r, "topic_slug"): row_field(r, "prompt_sha256") for r in rows}
    wanted = {e["topic_slug"]: e["prompt_sha256"] for e in examples}
    if held != wanted:
        raise SystemExit(f"dataset {dataset} does not match the batch's prompts")
    example_ids = {row_field(r, "topic_slug"): r["id"] for r in rows}
    dataset_id = next(
        d["id"]
        for d in ax("datasets", "list", "--space", args.space, "-o", "json",
                    "--limit", "100")["datasets"]
        if d["name"] == dataset
    )

    state.update(dataset=dataset, dataset_id=dataset_id)
    state.setdefault("experiments", {})
    existing = list_experiments(dataset_id)
    for name, runs in sorted(build_runs(manifest, example_ids).items()):
        if name in existing:
            held = len(export_runs(name, dataset_id))
            if held != len(runs):
                raise SystemExit(f"{name} exists with {held} runs; delete it first")
            state["experiments"][name] = existing[name]
            print(f"  experiment {name}: exists, {held} runs")
            continue
        state["experiments"][name] = create_experiment(name, runs, dataset_id)
        print(f"  experiment {name}: created, {len(runs)} runs")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2) + "\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
    print(f"  -> {path}")
    return 0


def export_dataset(dataset: str, space: str) -> list[dict]:
    return ax("datasets", "export", dataset, "--space", space, "--stdout")


def row_field(row: dict, key: str):
    """A field from an exported example or run, top-level or passed through."""
    if key in row:
        return row[key]
    return (row.get("additional_properties") or {}).get(key)


# --- annotate --------------------------------------------------------------


def ensure_configs(space: str) -> None:
    existing = {
        c["name"]
        for c in ax("annotation-configs", "list", "--space", space, "-o", "json")
        .get("annotation_configs", [])
    }
    wanted = {
        FLAGS_CONFIG: ["freeform"],
        COUNT_CONFIG: ["continuous", "--min-score", "0", "--max-score", "100",
                       "--optimization-direction", "MINIMIZE"],
        RECALL_CONFIG: ["continuous", "--min-score", "0", "--max-score", "1",
                        "--optimization-direction", "MAXIMIZE"],
    }
    for name, spec in wanted.items():
        if name not in existing:
            ax("annotation-configs", "create", spec[0], "--name", name,
               "--space", space, *spec[1:], parse=False)
            print(f"  created annotation config {name}")


def run_doc_ids(
    runs: list[dict], slugs: dict[str, str], repeat: int
) -> dict[str, dict]:
    """Map ``<slug>.r<N>.md`` to its exported run."""
    return {f"{slugs[r['example_id']]}.r{repeat}.md": r for r in runs}


def flag_lines(flags: list[dict], output: str) -> str:
    items = []
    for flag in flags:
        span = locate(flag["quote"], output)
        if span is None:
            raise SystemExit(f"cannot locate flag {flag['id']}: {flag['quote']!r}")
        items.append(Located(span[0], span[1], output[span[0]:span[1]]))
    text = format_lines(items)
    if len(text) > MAX_TEXT:
        raise SystemExit(f"{len(text)} chars of flags exceeds AX's {MAX_TEXT}")
    return text


def experiments_for(state: dict, alias: str) -> list[tuple[str, int]]:
    return sorted(
        (name, int(name.rsplit("r", 1)[1]))
        for name in state["experiments"]
        if name.split()[1] == alias
    )


def cmd_annotate(args: argparse.Namespace) -> int:
    state = load_state(args.run_id)
    ensure_configs(args.space)
    annotations = json.loads(ANNOTATIONS.read_text())
    if annotations["run_id"] != args.run_id:
        raise SystemExit(f"annotations are for {annotations['run_id']}")
    alias = annotations["model_alias"]
    by_doc: dict[str, list[dict]] = {}
    for flag in annotations["flags"]:
        by_doc.setdefault(flag["doc_id"], []).append(flag)

    slugs = {r["id"]: row_field(r, "topic_slug")
             for r in export_dataset(state["dataset"], args.space)}
    total = 0
    for name, repeat in experiments_for(state, alias):
        runs = run_doc_ids(export_runs(name, state["dataset_id"]),
                           slugs, repeat)
        records = []
        for doc_id, run in sorted(runs.items()):
            flags = by_doc.get(doc_id, [])
            values = [{"name": COUNT_CONFIG, "score": len(flags)}]
            if flags:
                values.append({"name": FLAGS_CONFIG,
                               "text": flag_lines(flags, run["output"])})
            records.append({"record_id": run["id"], "values": values})
            total += len(flags)
        with_file(records, "experiments", "annotate-runs", name,
                  "--dataset", state["dataset_id"], parse=False)
        print(f"  {name}: annotated {len(records)} runs")
    expected = len(annotations["flags"])
    print(f"  {total} flags written ({expected} in {ANNOTATIONS.name})")
    return 0 if total == expected else 1


# --- reading results back --------------------------------------------------


def evaluation(run: dict, name: str) -> dict | None:
    """An evaluation from an exported run, whichever shape the export uses.

    ``ax experiments export`` (0.35) puts task results in the run's
    ``additional_properties`` as flat ``eval.<name>.score`` / ``.label`` /
    ``.explanation`` keys. An ``evaluations`` object, as the docs describe,
    is read too.
    """
    props = run.get("additional_properties") or {}
    prefix = f"eval.{name}."
    flat = {k[len(prefix):]: v for k, v in props.items() if k.startswith(prefix)}
    if flat:
        return flat
    evals = run.get("evaluations") or {}
    if isinstance(evals, dict):
        return evals.get(name)
    return next((e for e in evals if e.get("name") == name), None)


def annotation(run: dict, name: str) -> dict | None:
    return next((a for a in run.get("annotations") or [] if a.get("name") == name),
                None)


def recall_for_run(run: dict, doc_id: str) -> dict | None:
    """Score one run's evaluator spans against its hand flags.

    Returns None if the run has not been evaluated yet. A flag counts as found
    when an evaluator span overlaps it by position, or failing that by text,
    which is how ``blogwriter-validate`` matches.
    """
    ev = evaluation(run, SPANS_EVAL)
    if not ev or ev.get("explanation") is None:
        return None
    spans = parse_lines(ev["explanation"])
    flags_ann = annotation(run, FLAGS_CONFIG)
    flags = parse_lines(flags_ann["text"]) if flags_ann else []

    def hit(flag: Located) -> bool:
        for s in spans:
            if s.start >= 0 and s.start < flag.end and flag.start < s.end:
                return True
            if overlaps(s.quote, flag.quote, flag.quote):
                return True
        return False

    found = sum(hit(f) for f in flags)
    load_bearing = [
        snippet for d, snippet in KNOWN_LOAD_BEARING if d == doc_id
    ]
    lb_missed = [
        snippet for snippet in load_bearing
        if not any("load" in s.quote.lower() and "bear" in s.quote.lower()
                   for s in spans)
    ]
    return {"flags": len(flags), "found": found, "spans": len(spans),
            "load_bearing_missed": lb_missed}


def cmd_recall(args: argparse.Namespace) -> int:
    state = load_state(args.run_id)
    alias = json.loads(ANNOTATIONS.read_text())["model_alias"]
    slugs = {r["id"]: row_field(r, "topic_slug")
             for r in export_dataset(state["dataset"], args.space)}
    failed = False
    for name, repeat in experiments_for(state, alias):
        runs = run_doc_ids(export_runs(name, state["dataset_id"]),
                           slugs, repeat)
        records, flags, found, pending = [], 0, 0, 0
        for doc_id, run in sorted(runs.items()):
            result = recall_for_run(run, doc_id)
            if result is None:
                pending += 1
                continue
            flags += result["flags"]
            found += result["found"]
            if result["load_bearing_missed"]:
                failed = True
                print_stderr(f"  load-bearing missed in {doc_id}")
            if result["flags"]:
                records.append({"record_id": run["id"], "values": [
                    {"name": RECALL_CONFIG,
                     "score": round(result["found"] / result["flags"], 3),
                     "text": f"{result['found']} of {result['flags']} flags "
                             f"found; {result['spans']} spans returned"}]})
        if pending:
            print_stderr(f"  {name}: {pending} runs not evaluated yet")
            failed = True
        if records:
            with_file(records, "experiments", "annotate-runs", name,
                      "--dataset", state["dataset_id"], parse=False)
        pct = f"{100 * found / flags:.0f}%" if flags else "-"
        print(f"  {name}: recall {found}/{flags} ({pct})")
    return 1 if failed else 0


def emdash_per_1k(text: str) -> float:
    """The ``Em Dash Density`` evaluator's calculation (``ax/emdash_code.py``)."""
    body = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    body = re.sub(r"`[^`]*`", " ", body)
    words = len(body.split())
    return round(body.count("\u2014") * 1000.0 / words, 2) if words else 0.0


def misattached_emdash(runs: list[dict]) -> int:
    """Runs whose AX em-dash score is not the score of their own output."""
    bad = 0
    for run in runs:
        score = (evaluation(run, EMDASH_EVAL) or {}).get("score")
        if score is None or abs(score - emdash_per_1k(run["output"])) > 0.01:
            bad += 1
    return bad


def cmd_tasks(args: argparse.Namespace) -> int:
    """Create and run one evaluation task per experiment.

    One task per experiment, not one task over all of them: a task covering
    several experiments wrote each experiment's results onto the runs of a
    different experiment (reproduced 2026-09-25 with ax 0.35.0; see the
    README). A single-experiment task attaches them correctly.
    """
    state = load_state(args.run_id)
    evaluator = next(
        (e for e in ax("evaluators", "list", "--space", args.space, "-o", "json",
                       "--limit", "100")["evaluators"]
         if e["name"] == args.evaluator),
        None,
    )
    if evaluator is None:
        raise SystemExit(f"no evaluator named {args.evaluator!r}")
    task_type = {"CODE": "CODE_EVALUATION", "TEMPLATE": "TEMPLATE_EVALUATION"}.get(
        evaluator["type"], args.task_type)
    if not task_type:
        raise SystemExit(f"{evaluator['type']} evaluator: pass --task-type")
    tasks = state.setdefault("tasks", {}).setdefault(args.evaluator, {})
    failed = False
    for name, exp_id in sorted(state["experiments"].items()):
        if args.model and name.split()[1] != args.model:
            continue
        if name in tasks and not args.rerun:
            print(f"  {name}: task exists ({tasks[name]}); --rerun to trigger again")
            continue
        task_id = tasks.get(name)
        if task_id is None:
            task = ax("tasks", "create-evaluation",
                      "--name", f"{args.evaluator} \u00b7 {name}",
                      "--task-type", task_type, "--dataset", state["dataset_id"],
                      "--experiment-ids", exp_id, "--no-continuous",
                      "--evaluators", json.dumps([{
                          "evaluator_id": evaluator["id"],
                          "column_mappings": {"output": "output"}}]),
                      "-o", "json")
            task_id = tasks[name] = task["id"]
            state_path(args.run_id).write_text(json.dumps(state, indent=2) + "\n")
        run = ax("tasks", "trigger-run", task_id, "--experiment-ids", exp_id,
                 "--wait", "-o", "json")
        ok = run.get("num_successes", 0)
        print(f"  {name}: {run.get('status')}, {ok} scored, "
              f"{run.get('num_errors', 0)} errors, {run.get('num_skipped', 0)} skipped")
        if run.get("status") != "COMPLETED" or ok == 0:
            failed = True
        elif evaluator["name"] == "Em Dash Density":
            time.sleep(15)
            bad = misattached_emdash(export_runs(name, state["dataset_id"]))
            print(f"    em-dash scores checked against local: {bad} wrong")
            failed = failed or bad > 0
    return 1 if failed else 0


def summarise_runs(runs: list[dict]) -> dict:
    def mean(values):
        values = [v for v in values if v is not None]
        return round(statistics.mean(values), 2) if values else None

    def ev_score(run, name):
        ev = evaluation(run, name)
        return ev.get("score") if ev else None

    def ann_score(run, name):
        a = annotation(run, name)
        return a.get("score") if a else None

    return {
        "n": len(runs),
        SPANS_EVAL: mean(ev_score(r, SPANS_EVAL) for r in runs),
        EMDASH_EVAL: mean(ev_score(r, EMDASH_EVAL) for r in runs),
        COUNT_CONFIG: mean(ann_score(r, COUNT_CONFIG) for r in runs),
        RECALL_CONFIG: mean(ann_score(r, RECALL_CONFIG) for r in runs),
    }


def cmd_report(args: argparse.Namespace) -> int:
    state = load_state(args.run_id)
    by_model: dict[str, list[dict]] = {}
    rows = {}
    for name in sorted(state["experiments"]):
        runs = export_runs(name, state["dataset_id"])
        rows[name] = summarise_runs(runs)
        by_model.setdefault(name.split()[1], []).extend(runs)
    models = {alias: summarise_runs(runs) for alias, runs in sorted(by_model.items())}

    cols = [SPANS_EVAL, EMDASH_EVAL, COUNT_CONFIG, RECALL_CONFIG]
    print(f"  {'experiment':22}{'n':>4}" + "".join(f"{c:>18}" for c in cols))
    for name, row in {**rows, **{f'{a} (all)': m for a, m in models.items()}}.items():
        cells = "".join(f"{'-' if row[c] is None else row[c]:>18}" for c in cols)
        print(f"  {name:22}{row['n']:>4}{cells}")

    change = {}
    if {"opus-5", "opus-5.5"} <= models.keys():
        for c in (SPANS_EVAL, EMDASH_EVAL):
            a, b = models["opus-5"][c], models["opus-5.5"][c]
            if a and b is not None:
                change[c] = round(100 * (b - a) / a)
                print(f"  {c}: opus-5 {a} -> opus-5.5 {b} ({change[c]:+d}%)")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"run_id": args.run_id, "experiments": rows, "models": models,
             "change_pct": change}, indent=2) + "\n")
        print(f"  -> {args.json}")
    return 0


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="blogwriter-ax-experiments",
        description="Represent a batch in AX as a dataset, experiments and "
        "annotations, then read the evaluators' results back.",
    )
    parser.add_argument(
        "command", choices=["upload", "annotate", "tasks", "recall", "report"])
    parser.add_argument("--run-id", default="full-v1")
    parser.add_argument("--space", default=os.environ.get("ARIZE_SPACE", DEFAULT_SPACE))
    parser.add_argument("--json", help="report: also write the summary here")
    parser.add_argument("--evaluator", help="tasks: evaluator name in AX")
    parser.add_argument("--task-type", help="tasks: override the task type")
    parser.add_argument("--model", help="tasks: only this model's experiments")
    parser.add_argument("--rerun", action="store_true",
                        help="tasks: trigger again where a task already exists")
    args = parser.parse_args()
    if not args.space:
        print_stderr("no space: set ARIZE_SPACE or pass --space")
        return 2
    return {
        "upload": cmd_upload,
        "annotate": cmd_annotate,
        "tasks": cmd_tasks,
        "recall": cmd_recall,
        "report": cmd_report,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
