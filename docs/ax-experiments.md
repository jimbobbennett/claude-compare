# The comparison as an Arize AX experiment

This document covers the second way the comparison runs in Arize AX. The first
way scores the traces the harness produced (see the README). This way
represents the same batch in AX's experiment model:

- a dataset of prompts
- one experiment per model and repeat, holding the posts
- the hand-flagged claudisms as annotations
- two evaluators that AX runs over the experiments

It also records everything learned about AX along the way, because several of
those findings change how the workflow has to be built.

The batch is `full-v1`: 20 topics × 2 models × 2 repeats, which is 80 posts.

## Results

The scores below were computed in AX, with one task per experiment.

| per 1,000 words | opus-5 | opus-5.5 | change |
|---|---|---|---|
| claudism spans (remote evaluator, v2.2 prompt, `gpt-6-luna`) | 4.79 | 2.38 | −50% |
| em-dashes (code evaluator) | 12.9 | 0.05 | −100% |

| experiment | claudism spans | em-dashes | hand flags per post | recall |
|---|---|---|---|---|
| `full-v1 opus-5 r1` | 4.88 | 12.8 | 4.15 | 0.65 |
| `full-v1 opus-5 r2` | 4.70 | 13.0 | 3.50 | 0.61 |
| `full-v1 opus-5.5 r1` | 2.49 | 0.07 | - | - |
| `full-v1 opus-5.5 r2` | 2.26 | 0.03 | - | - |

Recall is how many of the hand flags the evaluator's spans cover.

- Per experiment: the recall column is the mean of the per-run values.
- Pooled: 54 of 83 flags on r1 (65%) and 41 of 70 on r2 (59%).
- Load-bearing: all three load-bearing sentences are caught.
- Hand flags: there are only hand flags for Opus 5.

These match the local runs, which gave 4.79 vs 2.43 spans per 1k and 69% and
63% recall. The differences come from judge variance: `gpt-6-luna` does not
accept `temperature=0`, so two passes over the same post differ a little. The
summary is in `results/full-v1-ax-experiments.json`.

## What is in AX

| Object | Name | Contents |
|---|---|---|
| Dataset | `claude-compare-full-v1` | 20 examples, one per topic (see below) |
| Experiments | `full-v1 <model> r<repeat>` | 4 experiments of 20 runs |
| Annotation configs | `claudisms` (freeform), `claudism_count` (continuous 0-100), `claudism_recall` (continuous 0-1) | the hand flags, and recall |
| Code evaluator | `Em Dash Density` | em-dashes per 1,000 words |
| Remote evaluator | `claudism_spans` | the v2.2 span judge, served by `blogwriter-eval-server` |
| Integration | `claudism_spans endpoint` (type `EVALUATOR`) | endpoint URL, bearer header, input schema |
| Tasks | `Em Dash Density · <experiment>` and one remote task per experiment | one task per experiment |

**Dataset examples.** Each example holds the following fields:

- `topic_slug`, `topic`, `genre` and `domain`
- the `brief` and its `brief_sha256`
- the exact rendered writer `prompt` and its `prompt_sha256`
- the `word_target`

`upload` renders each prompt again and refuses to continue unless its hash
matches the one the batch manifest recorded for that topic. That check is what
guarantees the dataset describes what the models actually saw.

**Experiment runs.** Each run's `output` is a post with its front-matter
removed. The run also carries these fields, from the batch manifest:

- `model_alias`, `model_id` and `served_model`
- `repeat`, `topic_slug`, `genre` and `word_count`
- `output_tokens`, `thinking_tokens` and `cost_usd_estimated`
- `prompt_sha256` and `brief_sha256`
- `source_run_id` and `post_sha256`

`upload` refuses any post whose served model differs from its label. After
upload, every output was checked byte for byte against the local file.

**The posts were not regenerated.** The experiments hold the posts the
harness wrote and traced when the batch ran. Uploading them as experiment
runs is a change of representation, not a new generation.

## Running it

It needs:

- the `server` dependency group
- `cloudflared` for the tunnel
- an `ax` profile
- `OPENAI_API_KEY` in `.env` for the judge

```bash
uv sync --group server
export ARIZE_SPACE="<your space name>"

uv run blogwriter-ax-experiments upload      # dataset + 4 experiments
uv run blogwriter-ax-experiments annotate    # hand flags onto the Opus 5 runs
uv run blogwriter-ax-experiments tasks --evaluator "Em Dash Density"
```

Every subcommand can be run again safely:

- `upload` reuses the dataset and any complete experiments, and stops if an
  experiment exists with the wrong number of runs.
- `annotate` upserts.
- `tasks` skips experiments that already have a task, unless you pass
  `--rerun`.

State (the dataset and experiment IDs, and the task IDs) is kept in
`output/<run>/ax/state.json`.

### The remote evaluator

Start the server and the tunnel, and leave them running:

```bash
PORT=8765 ./scripts/serve-evaluator.sh
```

The script does four things:

- starts `blogwriter-eval-server` on `127.0.0.1:$PORT`
- starts a Cloudflare quick tunnel in front of it
- generates a bearer token into `.eval-token` (gitignored) the first time it
  runs
- prints the public endpoint URL

It never prints the token. Ctrl+C stops both processes, and so does either
process exiting. So to restart only the server, stop it and run the tunnel on
its own:

```bash
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8765
```

Register it:

```bash
~/.local/share/uv/tools/arize-ax-cli/bin/python \
  scripts/register_remote_evaluator.py https://<tunnel>.trycloudflare.com \
  --space "$ARIZE_SPACE"
```

The script creates or updates the `EVALUATOR` integration and creates the
`claudism_spans` remote evaluator.

- Why the ax CLI's Python: the script calls the REST API through the SDK
  bundled with the `ax` CLI, and that SDK authenticates with the active `ax`
  profile. So no key is read or passed. The `ax` CLI itself cannot create an
  `EVALUATOR` integration.
- After a restart: a quick tunnel gets a new URL every time it starts. Run
  the script again; it updates the endpoint in place, and the evaluator
  follows because it references the integration.

Then, **in the AX UI**, create one evaluation task per experiment:

1. Use the dataset `claude-compare-full-v1` and the evaluator `claudism_spans`.
2. Select exactly one experiment per task.
3. Map `output` to the run's `output`, and run the task.

Four tasks in all. Then:

```bash
uv run blogwriter-ax-experiments recall
uv run blogwriter-ax-experiments report --json results/full-v1-ax-experiments.json
```

`recall` does three things:

- reads the evaluator's spans back
- matches them to the hand flags, first by position and then by text
- writes `claudism_recall` onto each annotated run

It fails if a load-bearing sentence was missed. `report` prints every
evaluator and annotation per experiment and per model. Both commands stop if
any stored span is not a passage of its own run's post (see the first
finding below).

### The request and response contract

AX sends:

```json
{
  "metadata": {"evaluator": "...", "record_id": "...", "request_id": "..."},
  "input": {"output": "<the post>"}
}
```

The endpoint returns:

```json
{
  "score": 4.29,
  "label": "strong",
  "explanation": "511-524 | stock_metaphor | a useful lens\n1178-1200 | verdict_intensifier | That's not accidental."
}
```

- Score: spans per 1,000 words of prose.
- Label: the v2 density band. The bands are uncalibrated (see the README),
  so use the score.
- Explanation: one line per span, `start-end | category | quote`, with
  character offsets into the output. An offset of `-1--1` means the judge's
  quote could not be located in the post.

**What the server does with each request:**

- It needs `Authorization: Bearer <.eval-token>`, and returns 401 without it.
- It returns 502 when the judge fails, so that AX retries.
- It shares one judge call between concurrent or repeated requests for the
  same post, keyed by the SHA-256 of the output. So AX's retries do not pay
  twice.
- It holds results in memory for the life of the process. A restart judges
  every post afresh. Posts judged earlier in the same process are answered
  from memory, which is the same result a fresh call would have given in that
  pass.
- It logs each request's field names, never their content, plus each result's
  score, span count and latency.

Through the tunnel, one call took about 16 seconds. With AX sending in
parallel, calls took about 80 seconds each.

### The line format

AX annotations and evaluator explanations are plain text attached to a whole
record. AX has no way to highlight or position part of an output. So positions
are carried in text, in one format shared by both sides:

```
483-524 | That single announcement is a useful lens              # a hand flag
1178-1199 | contrast_reframe | That's not accidental             # an evaluator span
```

`src/blogwriter/positions.py` writes and parses the format. `locate()` finds a
quote in a post by exact match first, then by a match that tolerates dropped
markdown (`*`, `_` and backticks) and differences in whitespace. That
tolerance is needed on both sides:

- Two of the 153 hand flags lost their markdown when they were exported from
  the Google Doc.
- The judge often drops markdown from its quotes, for example "cold open" for
  `**cold open**`.

A flag's line records the text as it appears in the post, markup included.

## What we learned about AX

These were found with ax CLI 0.35.0 and SDK 8.53.0, in September 2026.

### 1. A task over several experiments puts results on the wrong experiment

An evaluation task that covered more than one experiment stored each
experiment's results on the runs of a different experiment.

- It happened with both evaluator types. Once with the code evaluator
  (created and triggered through the CLI), and once with the remote evaluator
  (task created in the UI).
- It was reproduced deliberately. With two copies, A (Opus 5 posts, high
  em-dash rate) and B (Opus 5.5 posts, near zero), one task over both left
  A's 20 runs with B's scores (20 of 20) and B's runs with their own.
- Across the four experiments, the results were shifted by one. For both
  evaluators:

| results stored on | actually computed from |
|---|---|
| opus-5 r1 | opus-5 r2 |
| opus-5 r2 | opus-5.5 r1 |
| opus-5.5 r1 | opus-5.5 r2 |
| opus-5.5 r2 | opus-5.5 r2 |

For the em-dash evaluator this was shown by recomputing every score locally.
For the remote evaluator it was shown by locating each stored span's offsets
in the four posts on the same topic. Only one of the four fitted.

**A task that covers a single experiment attaches every result correctly.**
That was checked for all 80 runs with both evaluators. So:

- `tasks` creates one task per experiment.
- `tasks` recomputes every em-dash score locally and compares it.
- `recall` and `report` check that every stored span is a passage of its own
  run's post.

The reproduction (experiments `zz repro A` and `zz repro B`, and task `zz
repro em-dash A+B`) was left in the author's space. The local evidence (the
stored results and the server log) is kept outside the repository.

### 2. The API can create a remote evaluator, but not a task that runs one

The REST API (`/v2/spec.yaml`) supports:

- `POST /v2/integrations` with `type: EVALUATOR`, which takes the endpoint,
  the headers (encrypted at rest and never returned) and the input schema.
- `POST /v2/evaluators` with `type: REMOTE`.

Both are behind the remote evaluators feature flag, and both work.
`scripts/register_remote_evaluator.py` uses them.

**Tasks are the gap.** The task types in the API are `TEMPLATE_EVALUATION`,
`CODE_EVALUATION` and `RUN_EXPERIMENT`. A task created with either evaluation
type and the remote evaluator is accepted, but every trigger is cancelled
within seconds at 0 successes, 0 errors and 0 skipped, and the endpoint is
never called. Tasks created in the UI do run the remote evaluator. They also
do not appear in `ax tasks list` or `GET /v2/tasks`, so their status can only
be seen in the UI, or by watching the endpoint and the experiment results.

### 3. The input schema must nest the fields under `input`

The integration's input schema describes the whole request body. The UI's
evaluator configuration only maps variables from fields under `input`:

```json
{
  "type": "object",
  "required": ["input"],
  "properties": {
    "input": {
      "type": "object",
      "required": ["output"],
      "properties": {"output": {"type": "string"}}
    }
  }
}
```

A schema with `output` at the top level registers without error, but the UI
cannot map it. A task run with that schema made three calls, one of which the
server rejected, and then stopped without storing any results.

### 4. `record_id` is the dataset example ID

For an experiment task, the `record_id` in the request metadata is the
**dataset example** ID, not the experiment run ID. That means it is the same
for every experiment's post on a given topic. Don't use it to identify a run
or to cache results. The server keys its sharing of judge calls on the
output's hash instead.

### 5. Exported runs carry evaluations as flat keys

`ax experiments export` returns each run's evaluation results inside
`additional_properties`, as flat keys (`eval.<name>.score`, `.label`,
`.explanation`, `.metadata`). They are not in an `evaluations` object, as the
skill documentation describes. Annotations come back as an `annotations` list
of `{name, score | label | text, updated_at}`. The `--all` (Flight) export
returned neither. `evaluation()` in `ax_experiments.py` reads both the flat
keys and the `evaluations` object.

### 6. Smaller things

- Annotation text is limited to 1,500 characters, and exactly 1,500 is
  accepted. One oversized value rejects the whole `annotate-runs` batch, so
  `annotate` checks lengths before sending. The densest post's flags come to
  578 characters in the line format.
- An annotation is keyed by run and annotation name. A second value with
  the same name replaces the first, and there is no per-annotator or
  per-instance identifier. So all of a post's flags live in one `claudisms`
  value.
- `ax experiments create` takes only `example_id` and `output` from each
  row as run data. Every other column passes through to
  `additional_properties`. Evaluations in the create file are not attached as
  evaluations. They are attached later, with `annotate-runs` or a task.
- `ax experiments annotate-runs` has no `-o` option.
- **Re-triggering a task on runs that already have results is cancelled at
  0/0/0.** To re-score, recreate the experiments or use a new experiment.
- Delete and recreate is the way to clear wrong results. `upload` can
  rebuild the experiments, and `annotate` and `tasks` put back everything
  else.

### 7. A stale `ax` on the PATH

This one is about the local environment, not AX, but it cost the most time.

- The cause: a Python interpreter puts its own `bin` directory first on
  the PATH of the subprocesses it starts. An old `ax` had once been
  pip-installed into a pyenv Python, and it was built on SDK 8.43.1. Every
  `ax` call made from Python ran that one, not the current CLI.
- The symptom: the old CLI fails on the `space_id` field the server now
  returns on experiments, with "additional fields (not defined in Experiment)
  in the input: space_id". Its create calls reported that failure even when
  the experiment had been created.
- The fix: `ax_binary()` skips the interpreter's own `bin` directories
  when it looks for `ax`, and `AX_BIN` overrides the choice.
- Check for it with `which -a ax`. Remove any copy inside a Python
  installation with `pip uninstall arize-ax-cli`.

## Files

| File | Purpose |
|---|---|
| `src/blogwriter/ax_experiments.py` | `blogwriter-ax-experiments`: `upload`, `annotate`, `tasks`, `recall`, `report` |
| `src/blogwriter/eval_server.py` | `blogwriter-eval-server`: the remote evaluator |
| `src/blogwriter/positions.py` | the `start-end \| quote` format and tolerant matching |
| `scripts/serve-evaluator.sh` | runs the server behind a quick tunnel |
| `scripts/register_remote_evaluator.py` | creates the integration and remote evaluator through the REST API |
| `results/full-v1-ax-experiments.json` | the report summary |
