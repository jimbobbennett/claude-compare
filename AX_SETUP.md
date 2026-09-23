# AX evaluator setup

The evaluators run **in Arize AX**, not locally. The local harness only
generates posts and traces them; AX scores them; `blogwriter-ax-report` reads
the scores back and ranks the models.

Space: `jbennett Space` · Project: `claude-compare-blogwriter`

## What exists in AX

| Object | Name | ID |
|---|---|---|
| Template evaluator (LLM judge) | `Claudism Density` (v2, MINIMIZE) | `RXZhbHVhdG9yOjE1NjYwOnVWcDQ=` |
| Code evaluator (deterministic) | `Em Dash Density` | `RXZhbHVhdG9yOjE1NjYxOlZPSWI=` |
| Task (LLM) | `Claudism Scoring (LLM judge)` | `T25saW5lVGFzazozODc2ODppZHla` |
| Task (code) | `Em Dash Scoring (code)` | `T25saW5lVGFzazozODc2OTpmWDFH` |

Judge model: `gpt-5.6-luna` via the existing OpenAI AI integration
`mastering-ai-agents-judge` (`TGxtSW50ZWdyYXRpb246NDQ5Mzo3TlB4`). That
integration is named for an unrelated project — worth creating a dedicated one
if this becomes permanent.

The judge is deliberately **not** a Claude model: the thing being measured is
Claude's own register, and a Claude judge carries a self-preference risk on
exactly that axis.

## Three gotchas that cost real time

**1. The eval index wants full attribute paths in filters.** `span_kind =
'CHAIN'` matches **zero** rows and `trigger-run` fails with
`400 No data found` — indistinguishable from an empty time window. This works:

```
attributes.openinference.span.kind = 'CHAIN'
```

`name LIKE 'write_post%'` also matched nothing. Filtering on CHAIN alone is
fine anyway: it catches `write_post` spans (the posts) *and* `research` spans
(the briefs), so the contamination baseline is scored by the same task, and
`ax_report.py` separates them by span name.

**2. Results come back in a top-level `evaluations` array**, not under
`attributes`. Looking for `attributes.eval.*` finds nothing:

```json
"evaluations": [
  {"name": "em_dash_density", "score": 0, "label": "none",
   "explanation": "0 em-dashes in 1316 words = 0.0 per 1000"},
  {"name": "claudism_density", "score": 3, "label": "moderate",
   "explanation": "..."}
]
```

**3. One task cannot mix evaluator types.** `All evaluators on a task must be
the same type` — hence two tasks, one `TEMPLATE_EVALUATION` and one
`CODE_EVALUATION`.

Also: this CLI's `--template` help says `{{variable}}`, but the server rejects
that with *"must contain at least one f-string expression like
{variable_name}"* — use **single** braces. And `--template @file` is not
expanded; pass the content (`--template "$(cat file)"`).

## Recreating it

```bash
SPACE="jbennett Space"
INT="TGxtSW50ZWdyYXRpb246NDQ5Mzo3TlB4"

# LLM judge -- template body lives in ax/claudism_template.txt
ax evaluators create-evaluator template \
  --name "Claudism Density" --space "$SPACE" \
  --commit-message "v1" --template-name "claudism_density" \
  --ai-integration-id "$INT" --model-name "gpt-5.6-luna" \
  --include-explanations --use-function-calling \
  --direction MINIMIZE --data-granularity span \
  --classification-choices '{"saturated":5,"strong":4,"moderate":3,"faint":2,"absent":1}' \
  --template "$(cat ax/claudism_template.txt)"

# Deterministic code evaluator
ax evaluators create-evaluator code \
  --name "Em Dash Density" --space "$SPACE" \
  --commit-message "v1" --code-type custom --code-name "em_dash_density" \
  --variables '["output"]' --data-granularity span \
  --imports "$(cat ax/emdash_imports.py)" --code "$(cat ax/emdash_code.py)"

# One task per evaluator type
ax tasks create-evaluation --name "Claudism Scoring (LLM judge)" \
  --task-type TEMPLATE_EVALUATION --project claude-compare-blogwriter \
  --space "$SPACE" --query-filter "attributes.openinference.span.kind = 'CHAIN'" \
  --evaluators '[{"evaluator_id":"<LLM_EVAL_ID>","column_mappings":{"output":"attributes.output.value"}}]' \
  --no-continuous

ax tasks create-evaluation --name "Em Dash Scoring (code)" \
  --task-type CODE_EVALUATION --project claude-compare-blogwriter \
  --space "$SPACE" --query-filter "attributes.openinference.span.kind = 'CHAIN'" \
  --evaluators '[{"evaluator_id":"<CODE_EVAL_ID>","column_mappings":{"output":"attributes.output.value"}}]' \
  --no-continuous
```

## Running a scoring pass

The **eval index lags ingestion by 1–2 hours**. A window ending "now" over
freshly written spans completes and scores nothing, so leave a gap.

```bash
# 1. generate posts (local)
uv run blogwriter-batch --models opus-5,opus-5.5 --repeats 3

# 2. wait for the eval index, then score in AX (both tasks)
ax tasks trigger-run T25saW5lVGFzazozODc2ODppZHla \
  --data-start-time "2026-09-22T19:00:00" --data-end-time "2026-09-22T23:20:00" \
  --max-spans 60 --wait
ax tasks trigger-run T25saW5lVGFzazozODc2OTpmWDFH \
  --data-start-time "2026-09-22T19:00:00" --data-end-time "2026-09-22T23:20:00" \
  --max-spans 60 --wait

# 3. read the answer back
uv run blogwriter-ax-report
```

Add `--is-continuous --sampling-rate 1.0` to a task (via `ax tasks update`) to
score new spans automatically instead of triggering backfills.

## Known limitation

The code evaluator's em-dash count does not strip markdown list markers, so the
**brief** baseline reads 34.88/1k — that is bullet punctuation, not prose style.
It does not affect the post comparison (posts are prose), but the brief figure
on that one metric should be ignored.

## Reading the report

`blogwriter-ax-report` colours labels and scores red → amber → green:

**Red = obviously Claude. Green = doesn't read as Claude.**

| band | claudism label | claudism score | em_dash/1k |
|---|---|---|---|
| red | `strong`, `saturated` | >= 3.5 | >= 10 |
| amber | `moderate` | >= 2.5 | >= 3 |
| green | `faint`, `absent` | < 2.5 | < 3 |

High claudism density is the flagged end of the scale, so it reads like a
warning scale. The evaluator is set to **`--direction MINIMIZE`** (v2) so AX's
own column colouring agrees with the terminal instead of contradicting it — if
you ever flip the colours in `ax_report.py`, flip the evaluator direction in
the same change or the UI and the report will disagree.

Note the code evaluator has no `--direction` flag; only template evaluators do.

The brief baseline's em-dash figure is printed dimmed with a `*` because it is
list punctuation rather than prose style, so it is deliberately never coloured
as if it were comparable.

Colour is on for a TTY, off when piped or when `NO_COLOR` is set, and forced
with `--color`.
