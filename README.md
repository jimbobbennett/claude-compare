![Claude Compare! - an operatic tenor in a blue tuxedo beside a dark green panel reading "CLAUDE COMPARE!"](docs/banner.jpg)

# Claude Compare!

**Does Claude Opus 5.5 still write with Opus 5's signature style?**

A local harness generates blog posts under a configurable model and traces them
to Arize AX. **AX scores them** with an LLM-as-judge plus a deterministic code
evaluator. A report reads the scores back and ranks the models.

"Signature style" here means the rhetorical tics people recognise as Claude:
`load-bearing`, `take a moment to read that again`, `it's not X — it's Y`,
em-dash asides, rule-of-three closers.

---

## Results

**20 topics × 2 models × 2 repeats = 80 posts**, all scored in Arize AX.
Balanced at n=40 per model, 0 failures, every post served by the model it is
labelled with.

```
  group                    n  claudism     sd   modal label  em_dash/1k
  ---------------------------------------------------------------------
  opus-5                  40      3.45   0.50      moderate       12.90
  opus-5.5                40      2.77   0.53      moderate        0.05
  BRIEFS (baseline)        8      1.62      -        faint            -

  Most obviously Claude: opus-5 (3.45)   Least: opus-5.5 (2.77)   gap 0.68
```

**Opus 5 reads as more obviously Claude than Opus 5.5** — 3.45 vs 2.77 on the
1–5 claudism scale. The brief baseline sits at 1.62 ("faint"), so the evaluator
is discriminating rather than rating everything mid-scale.

### The em-dash is the headline

No judge involved, pure regex, and it is close to binary:

| | em-dashes per 1000 words |
|---|---|
| Opus 5 | **12.90** |
| Opus 5.5 | **0.05** |

Across 40 posts and roughly 55,000 words, **Opus 5.5 used two em-dashes in
total.** Opus 5 used them constantly. If you want one cheap test for whether
Claude wrote something, this is it — and it no longer works on 5.5.

### The gap holds in every domain and every genre

This is what the non-AI topics were for. If claudisms were an artefact of dense
technical writing rather than a property of the model, the gap would collapse
outside `ai`. It does not:

| domain | opus-5 | opus-5.5 | gap |
|---|---|---|---|
| cooking | 3.83 | 2.67 | **1.16** |
| ai | 3.38 | 2.69 | 0.69 |
| travel | 3.33 | 2.67 | 0.66 |
| books | 3.33 | 2.83 | 0.50 |
| games | 3.50 | 3.17 | 0.33 |

| genre | opus-5 | opus-5.5 | gap |
|---|---|---|---|
| opinion | 3.92 | 3.08 | 0.84 |
| technical-explainer | 3.20 | 2.40 | 0.80 |
| news-analysis | 3.50 | 3.00 | 0.50 |
| product-announcement | 3.50 | 3.00 | 0.50 |
| tutorial-intro | 3.10 | 2.60 | 0.50 |

Ten out of ten breakdowns point the same way. Opinion writing is the most
claudism-dense register for both models — the constructions are argumentative
devices, so that follows.

### Opus 5.5 did not get plainer — it swapped tics

The deterministic scan is the interesting part. 5.5 is *down* on em-dashes and
phrases but *up* on other signature structures:

| per 1000 words | opus-5 | opus-5.5 | |
|---|---|---|---|
| em-dashes | 13.30 | 0.05 | ↓ nearly eliminated |
| bold lead-in bullets | 2.02 | **4.96** | ↑ 2.5× |
| rule-of-three | 2.71 | **3.66** | ↑ 35% |
| mean word count | 1269 | 1365 | ↑ 8% longer |

So "Opus 5.5 is less Claude-ish" is too simple. It writes *longer*, leans
*harder* on bolded bullet scaffolding and triads, and has almost entirely
dropped the em-dash. The judge's lower score reflects a real shift in register,
not a retreat into plain prose.

**The consequence matters if you are building a detector.** Any
"was this written by Claude?" heuristic built on the Opus 5 signature —
em-dashes, `load-bearing`, antithesis pivots — will **under-read Opus 5.5**,
because the structures 5.5 leans on went *up* rather than down. A metric set
needs both halves. In this harness only the local scan measures the ones that
increased; the AX code evaluator currently sees em-dashes alone, which is the
gap worth closing first.

### What this does not establish

- **2 repeats, not 3.** Per-cell stochasticity is only lightly averaged; the
  aggregate is solid but individual topic numbers are noisy.
- **One judge pass per post**, and these judge models reject `temperature=0`,
  so the graded scores carry irreducible variance. The em-dash and structural
  figures do not — they are deterministic.
- **The brief baseline is n=8**, not 20: the earlier briefs fell outside the
  scored time window. Low enough to be reassuring, too small to lean on.
- **The phrase list still barely fires** (0.30 and 0.11 per 1000 words). Those
  28 phrases were guessed, not derived. The structural metrics and the judge
  are carrying the result.

Cost: ~$15 of briefs (one-off, committed as fixtures) + $7.00 of posts.
Briefs averaged ~$0.88 each, but split by domain: ~$1.00 for `ai` topics
against ~$0.56 for travel/cooking/games/books, since fewer search results
accumulate as input tokens.

---

## The one design requirement

**The model ID must be the only thing that differs between two runs.** A style
comparison is worthless if the models were also handed different research, ran
at different effort levels, or picked up different config off disk. Every
decision below exists to pin one of those down.

| Drift source | How it's pinned |
|---|---|
| Research / tool variance | Briefs are committed fixtures; the writer gets no tools |
| A brief changing silently | SHA-256 per brief in `briefs/briefs.lock.json`, verified every run |
| Effort default mismatch | `effort="medium"` set explicitly for both models |
| Thinking config | Adaptive only — Opus 5.5 returns 400 for `disabled` or `budget_tokens` |
| Local config leakage | Impossible by construction: no subprocess, no filesystem settings |
| Prompt text drift | `WRITER_PROMPT_VERSION` + SHA-256 of the rendered prompt, per run |
| Model silently substituted | Run aborts unless `response.model` equals the requested ID |
| A refusal answered by another model | Server-side `fallbacks` deliberately **not** enabled; refusal is fatal |
| Harness version drift | Anthropic SDK version recorded in every manifest |
| Post length skewing density | Same word target; every metric normalised per 1000 words |
| Sampling stochasticity | `--repeats N` |
| Subject-matter confound | 5 domains, so "the model's voice" is separable from "technical prose" |

### Why effort is pinned

Opus 5 defaults to `effort: high`. **Opus 5.5 defaults to `medium`.** Leave it
unset and you are not comparing Opus 5 to Opus 5.5 — you are comparing *Opus 5
at high* against *Opus 5.5 at medium*. 5.5 also thinks more per turn at any
given effort, which shows up in the recorded `thinking_tokens` (21–26 for
Opus 5 vs 108–265 for Opus 5.5 at the same setting).

### Why briefs are fixtures, not a pipeline stage

Research runs **once**, output is committed, and the writer reads a file under
version control. `--refresh-briefs` is required to replace one, which rewrites
the lockfile and so marks earlier results as a different input generation. Every
run verifies each brief's hash and hard-fails on a mismatch.

Briefs are deliberately **telegraphic** — fact bullets with source URLs, no
prose. If a research model wrote flowing paragraphs, its own stylistic tics
would sit in the writer's input and both models would echo them; the evaluator
would then be scoring the brief. The briefs are scored too, as the
contamination baseline — 1.62 ("faint") against 3.45 and 2.77 for the posts,
which is what makes the post scores meaningful.

### Why the Messages API, not the Claude Agent SDK

Writing a post from a fixed brief is one LLM call: no tools, no loop, no
filesystem. Two concrete reasons beyond simplicity:

1. **The Agent SDK cannot drive Opus 5.5.** Its only transport is spawning the
   Claude Code CLI, and CLI 2.1.280 accepts `claude-opus-5-5` then silently
   serves `claude-opus-5`. The raw Messages API serves it correctly.
2. **It removes confounds.** No subprocess means no inherited `CLAUDE_*`
   session state and no `CLAUDE.md` / `settings.json` leakage — nothing to
   suppress, because there is nothing to inherit.

Research needs the web but not an agent loop either: the **server-side**
`web_search_20260209` tool runs on Anthropic's infrastructure, so Stage A is
also a single request. (That tool does dynamic filtering via code execution
internally — do **not** declare `code_execution` alongside it.)

---

## Setup

### Prerequisites

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- An Anthropic API key with Opus 5 and Opus 5.5 access
- An Arize AX account, and the [`ax` CLI](https://arize.com/docs) authenticated
  (`ax profiles show` to check)
- An OpenAI-backed AI integration in AX for the judge

```bash
uv sync
cp .env.example .env    # then fill in ANTHROPIC_API_KEY
```

### Environment

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required. Without it the SDK may fall back to other credentials and silently serve a different model. |
| `ARIZE_API_KEY`, `ARIZE_SPACE_ID` | Required for tracing. |
| `BLOGWRITER_PROJECT_NAME` | Optional, defaults to `claude-compare-blogwriter`. |
| `ARIZE_COLLECTOR_ENDPOINT` | Only for non-US Arize accounts. |

> **Note:** the project name is deliberately **not** read from
> `ARIZE_PROJECT_NAME`. That variable is commonly already exported for
> unrelated tracing, and `load_dotenv()` does not override an existing shell
> variable — so inheriting it silently mixes this experiment's spans into
> someone else's project.

### Version pin that matters

`anthropic` is pinned to **`==1.7.0`**. The OpenInference instrumentor (2.1.5)
imports `anthropic._utils._transform`, which exists in 1.7.0 but was renamed by
1.8.0 — on 1.8.0 `.instrument()` raises `ModuleNotFoundError` and you get **no
LLM spans at all**, silently. Before raising the pin, check that import still
resolves.

---

## Usage

```bash
# Stage A -- generate the frozen briefs (once), then commit briefs/
uv run blogwriter-research
uv run blogwriter-research --only how-llm-as-judge-works --refresh-briefs

# Stage B -- one post
uv run blogwriter --topic-slug how-llm-as-judge-works --model opus-5.5

# Stage B -- the matrix
uv run blogwriter-batch --models opus-5,opus-5.5 --repeats 2

# Score in AX (see below), then read the ranking
uv run blogwriter-ax-report --by domain

# Free, offline, no model calls -- deterministic patterns only
uv run blogwriter-scan --run-id <run> --briefs
```

Posts land in `output/<run_id>/<model_alias>/<slug>.r<repeat>.md` with
front-matter recording the full pinned surface, plus a `manifest.json` per
batch. The repeat index is in the filename so repeated samples of a cell never
overwrite each other.

Exit codes: `2` bad arguments · `3` brief integrity failure · `4` model
substitution · `5` refusal.

### The validity check

Run the same topic under both models and diff the front-matter. It must differ
**only** in model identity, word count, tokens and cost — `prompt_sha256`,
`brief_sha256` and `effort` must be identical.

```bash
diff <(sed -n '/^---$/,/^---$/p' output/RUN/opus-5/SLUG.r1.md) \
     <(sed -n '/^---$/,/^---$/p' output/RUN/opus-5.5/SLUG.r1.md)
```

---

## The AX evaluators

Two evaluators, split on purpose:

| Evaluator | Type | What it scores |
|---|---|---|
| `Claudism Density` | LLM judge (`gpt-5.6-luna`), graded 1–5 | The voice constructions regex cannot see |
| `Em Dash Density` | Custom Python code evaluator | Em-dashes per 1000 words, deterministic |

Both run at span granularity over CHAIN spans, which covers `write_post` spans
(the posts) **and** `research` spans (the briefs) — so the contamination
baseline is scored by the same pass, and the report separates them by span name.

### Why the judge is not a Claude model

The thing being measured is Claude's own register, and a Claude judge carries a
self-preference risk on exactly that axis — MT-Bench put Claude-v1's
self-enhancement at roughly 25% higher win rate, the largest of the models
tested, and Anthropic's own guidance is to grade with a different model than the
generator.

Because the judge is cross-family, the constructions are defined
*structurally*, with examples, rather than asking it to "find the claudisms" —
an outside model has to be told the patterns, not asked to recognise a house
style.

### The evaluator prompt

Lives in [`ax/claudism_template.txt`](ax/claudism_template.txt), reproduced here
in full. `{output}` is the only variable; the task maps it to
`attributes.output.value`.

```text
You are a forensic style analyst. You judge the FORM of prose, never its subject matter, accuracy, or quality.

Below is a blog post. Rate how heavily it uses the following rhetorical constructions.

CONSTRUCTIONS TO LOOK FOR
1. antithesis pivot - "It is not X, it is Y" / "X is not just Y, it is Z": a negation of one framing immediately replaced by a sharper one.
2. concessive pivot - a concession followed by reversal: "Sure, X. But Y." / "That is true, as far as it goes. What it misses is..."
3. reveal setup - a short sentence announcing an insight is coming rather than delivering it: "Here is the thing." / "And that is the part that matters."
4. rule of three - three parallel items escalating in weight, especially closing a sentence.
5. meta writing - the text commenting on itself or steering the reader: "take a moment to read that again" / "we will come back to this" / "the short version:".
6. load-bearing idiom - engineering metaphors for abstract claims: "load-bearing", "the sharp edges", "where it falls over", "doing the heavy lifting".
7. punchy closer - a final paragraph of one or two very short declarative sentences landing the argument.
8. hedge then assert - a hedge immediately overridden: "This is probably overstated, but the direction is right."

Judge the prose only. Do NOT count list formatting, bold text, headings, or punctuation choices - those are measured separately.

RATING SCALE
saturated - these constructions drive the prose; the argument advances through them.
strong - recurring and noticeable across multiple sections.
moderate - present in several places but not the dominant mode.
faint - one or two instances, otherwise plain exposition.
absent - reads as unmarked technical prose.

BLOG POST
{output}

Respond with exactly one of these labels: saturated, strong, moderate, faint, absent
```

Label → score: `saturated` 5, `strong` 4, `moderate` 3, `faint` 2, `absent` 1.

**Format features are deliberately excluded from the judge.** An earlier version
included `bold_leadin_bullet` and `em_dash_aside`; one telegraphic research
brief returned **30** bold-bullet instances, which pushed the contamination
baseline (16.7) level with the posts (16.8 and 15.0) and destroyed the metric's
discriminative power. Removing them dropped the baseline to 1.14 and separated
the models. **The judge covers voice; regex covers format.**

### Creating the evaluators

```bash
SPACE="your space name"
INT="<ai-integration-id>"    # ax ai-integrations list --space "$SPACE" -o json

# LLM judge
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
```

Note `--direction MINIMIZE`: high claudism density is the *flagged* end, so AX's
own column colouring matches the report's red = obviously Claude.

### Creating the tasks

One task per evaluator type — they cannot be mixed.

```bash
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

### Running a scoring pass

The **eval index lags ingestion by 1–2 hours.** A window ending "now" over
freshly written spans completes successfully and scores nothing, so leave a gap.

Leave slack at **both** ends, too. On the 80-post run a window ending at the
moment generation finished missed the single most recent span — it was 15
seconds inside the boundary — giving 39/40 for one model. A second trigger over
a later window picked it up.

```bash
ax tasks trigger-run <TASK_ID> \
  --data-start-time "2026-09-22T19:00:00" --data-end-time "2026-09-22T23:20:00" \
  --max-spans 60 --wait
```

Add `--is-continuous --sampling-rate 1.0` via `ax tasks update` to score new
spans automatically instead of triggering backfills.

### Six AX gotchas that cost real time

1. **`query_filter` needs full attribute paths.** `span_kind = 'CHAIN'` matches
   **zero** rows — and it surfaces as `400 No data found between <start> and
   <end>`, which reads like an empty time window. Use
   `attributes.openinference.span.kind = 'CHAIN'`. `name LIKE 'write_post%'`
   also matched nothing. Diagnose by running with **no** filter: if that scores
   rows, the filter is the problem, not the window.
2. **Results come back in a top-level `evaluations` array**, not under
   `attributes`. `attributes.eval.*` finds nothing. They are queryable
   immediately via `--filter "eval.<name>.label IS NOT NULL"` even though they
   never appear as attribute columns.
3. **One task cannot mix evaluator types** — `All evaluators on a task must be
   the same type`.
4. **The CLI's `--template` help says `{{variable}}`, but the server rejects
   double braces** ("must contain at least one f-string expression like
   {variable_name}"). Use single braces. And `--template @file` is not
   expanded — pass `"$(cat file)"`.
5. **Custom code evaluators fail silently at `0/0/0`** unless you import *only*
   from `arize.experimental.datasets.experiments.evaluators.base`, subclass
   `CodeEvaluator`, give `evaluate()` explicitly named keyword params (bare
   `**kwargs` exposes zero mappable variables), return `EvaluationResult`, and
   keep imports in `--imports` rather than inline in `--code`.
6. **Deleting a project orphans its tasks.** The project is recreated on the
   next trace but with a **new ID**, while the tasks keep pointing at the dead
   one — and `ax tasks update` has no `--project` flag, so they cannot be
   repointed. Delete and recreate the tasks after deleting a project.
   Evaluators are space-level and survive untouched.

### AX cannot cost Opus 5.5

AX's server-side pricing fills `llm.cost.total` for `claude-opus-5` (with an
input/output breakdown) but leaves it **absent** for `claude-opus-5-5`. A cost
comparison built on AX's built-in cost columns would read 5.5 as free. The
harness computes cost itself from published rates and sets it on the CHAIN span
for both models — use that until AX's pricing table catches up.

---

## Reading the report

**Red = obviously Claude. Green = doesn't read as Claude.**

| band | claudism label | claudism score | em_dash/1k |
|---|---|---|---|
| red | `strong`, `saturated` | >= 3.5 | >= 10 |
| amber | `moderate` | >= 2.5 | >= 3 |
| green | `faint`, `absent` | < 2.5 | < 3 |

The direction lives in **two** places and must be changed together, or the
terminal and the AX dashboard will disagree about which end is bad:
`LABEL_COLOURS` in `src/blogwriter/ax_report.py`, and the evaluator's
`--direction`.

Colour is on for a TTY, off when piped or when `NO_COLOR` is set, forced with
`--color`.

`--by domain` (or `--by genre`) cross-tabs the score, which is what answers
whether the gap between models holds outside technical writing.

### The report filters its own inputs

Spans accumulate in the project from every debugging run, and an evaluator task
scores all of them indiscriminately — so a result read straight off "all spans"
is computed partly on harness development. `blogwriter-ax-report` therefore:

- **drops spans whose recorded `llm.model_name` contradicts their
  `model_alias`** (aborted runs and pre-gate substitutions), printing each
  exclusion in amber; and
- takes `--run-id` (repeatable) to pin a result to intended runs only.

An early headline figure of 3.54 vs 2.57 was inflated to 0.97 by exactly this
contamination; the clean figure is 3.33 vs 2.83, a gap of 0.50.

---

## Topic set

`topics.yaml` holds **20 topics across two axes**, because either could confound
a style measurement:

- **genre** (5): technical-explainer, opinion, tutorial-intro,
  product-announcement, news-analysis. Claudisms surface unevenly by register.
- **domain** (5): `ai` (8 topics), plus `travel`, `cooking`, `games` and
  `books` (3 each). An AI-only set cannot separate "this model's voice" from
  "how anything writes about dense technical material"; lifestyle prose gives
  the constructions room to appear.

Both travel in span metadata. Adding a topic does not invalidate existing
briefs — the writer prompt is built from the topic string alone.

| # | Topic | Genre | Domain |
|---|---|---|---|
| 1 | How LLM-as-judge evaluation actually works | `technical-explainer` | `ai` |
| 2 | What OpenTelemetry spans look like for an AI agent | `technical-explainer` | `ai` |
| 3 | Why most AI agent demos fall apart in production | `opinion` | `ai` |
| 4 | The case against vibe-checking your LLM outputs | `opinion` | `ai` |
| 5 | Getting started with tracing a Python LLM application | `tutorial-intro` | `ai` |
| 6 | How to build your first LLM evaluator | `tutorial-intro` | `ai` |
| 7 | Optimizing prompts automatically from production trace data | `product-announcement` | `ai` |
| 8 | What the effort parameter means for people building agents | `news-analysis` | `ai` |
| 9 | Why the 48-hour city break is a bad way to see a place | `opinion` | `travel` |
| 10 | How to plan a first trip to Japan without overplanning it | `tutorial-intro` | `travel` |
| 11 | What actually happens to your suitcase after you drop it off | `technical-explainer` | `travel` |
| 12 | Why searing meat does not seal in the juices | `technical-explainer` | `cooking` |
| 13 | How to build a weeknight pasta from whatever is in the fridge | `tutorial-intro` | `cooking` |
| 14 | The case against buying a stand mixer | `opinion` | `cooking` |
| 15 | Why open world games stopped being interesting | `opinion` | `games` |
| 16 | What the shift to subscription game libraries means for players | `news-analysis` | `games` |
| 17 | How frame generation actually works, and what it costs you | `technical-explainer` | `games` |
| 18 | In defence of abandoning a book halfway through | `opinion` | `books` |
| 19 | How to start reading poetry without a literature degree | `tutorial-intro` | `books` |
| 20 | Why so many literary novels now open with a prologue | `news-analysis` | `books` |

---

## Layout

```
claude-compare/
├── topics.yaml              # 20 topics x genre x domain
├── briefs/                  # COMMITTED FIXTURES + briefs.lock.json
├── ax/                      # the AX evaluator sources (template + code halves)
├── src/blogwriter/
│   ├── tracing.py           # Arize registration; call before the client exists
│   ├── models.py            # alias -> model ID, effort, pricing, cost
│   ├── prompts.py           # versioned research + writer prompts
│   ├── determinism.py       # hashing, brief lockfile, version capture
│   ├── topics.py            # topic set loading
│   ├── agent.py             # the model call + Stage B (the measured step)
│   ├── research.py          # Stage A -- fixture generation
│   ├── cli.py               # one post
│   ├── batch.py             # the model x topic x repeat matrix
│   ├── claudisms.py         # deterministic pattern scoring
│   ├── scan.py              # local offline scan (no model calls)
│   └── ax_report.py         # read AX scores back and rank
└── tests/                   # pure-logic tests, no network
```

---

## Development

```bash
uv run pytest        # 29 tests, no network or model calls
uv run ruff check src/
```

`ax/` is excluded from linting: it holds the two halves of the AX code
evaluator, which the platform requires as separate `--imports` and `--code`
blocks, so neither file is valid Python alone.

---

## Known limitations

- **Sample size.** All 20 briefs exist and all 20 topics are scored at n=2 per
  model, so the aggregate is sound. Individual per-topic numbers are noisy at
  that depth — raise `--repeats` before quoting any single topic.
- **The hand-written phrase list in `claudisms.py` matched nothing** in any real
  post. Those 28 phrases were chosen from intuition, not derived from output.
  They should be rebuilt empirically from a generated corpus (n-gram frequency
  compared across models). Until then treat `claude_leaning_per_1k` as
  unvalidated and rely on the structural metrics and the judge.
- **The judge is stochastic.** These OpenAI models reject `temperature=0` (only
  the default is accepted), so repeated passes are the only damping available.
- **The code evaluator does not strip markdown list markers**, so the *brief*
  baseline reads ~35 em-dashes/1k — that is bullet punctuation, not prose. The
  report prints it dimmed with a `*` and never colours it as comparable.
- **Research is expensive**: ~$1.27 per brief, driven by ~197k prompt tokens as
  web-search results accumulate. A cheaper, different-family research model
  would cut that and reduce contamination risk at the same time.

## Next steps

1. **Raise repeats to 3+** and re-score, so per-topic numbers become quotable
   rather than just the aggregate.
2. **Rebuild the phrase list empirically** from the 80-post corpus: compare
   n-gram frequencies between the two models instead of guessing which phrases
   matter. The current list barely fires and contributes nothing.
3. **Add structural metrics to the AX code evaluator.** Bold lead-in bullets
   and rule-of-three are where Opus 5.5's style actually *increased*, and right
   now only the local scan measures them — AX sees em-dashes alone.
4. **Multiple judge passes per post**, since `temperature=0` is unavailable and
   a single pass leaves the graded score noisier than it needs to be.
