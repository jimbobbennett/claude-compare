![Claude Compare! - an operatic tenor in a blue tuxedo beside a dark green panel reading "CLAUDE COMPARE!"](docs/banner.jpg)

# Claude Compare!

## What this is

Claude has a recognisable writing voice. Common features include em-dash
asides, the "it's not X, it's Y" pivot, the "load-bearing" metaphor, short
punchy closers, and announcing an insight just before delivering it. People call
these *claudisms*.

When Claude Opus 5.5 arrived, the obvious question was whether that voice came
with it. This repository measures that voice.

A local harness writes blog posts under a configurable model and traces every
run to **Arize AX**. Two evaluators hosted **inside AX** score the posts. An
LLM-as-judge rates how heavily the prose leans on Claude's signature
constructions, and a deterministic code evaluator counts em-dashes. A small
reporting command reads the scores back out of AX and ranks the models.

A second-generation judge sits alongside them. I read all 40 Opus 5 posts and
flagged 153 claudisms by hand, and the v2 judge was built from those flags. It
quotes every instance it finds, so its output can be checked against a human
reader line by line.

**Opus 5 writes more like Claude than Opus 5.5 does, and the clearest single
tell is the em-dash.** Opus 5.5 almost stopped using the em-dash, and it uses
the rhetorical moves underneath about half as often.

---

## The results

The experiment ran 20 topics across 2 models with 2 repeats each, for 80 posts,
balanced at 40 per model, no failures.

```
  group                    n  claudism     sd   modal label  em_dash/1k
  ---------------------------------------------------------------------
  opus-5                  40      3.45   0.50      moderate       12.90
  opus-5.5                40      2.77   0.53      moderate        0.05
  BRIEFS (baseline)        8      1.62      -        faint            -
```

Opus 5 scores **3.45** on the judge's 1–5 claudism scale against Opus 5.5's
**2.77**, a gap of 0.68. The third row is the control. The research briefs the
writers worked from are deliberately terse bullet notes, and they score 1.62
("faint"). That distance between the briefs and the posts is what tells you the
evaluator is measuring the writing rather than the subject matter.

### The em-dash is the clearest single signal

A regular expression counts the character directly:

| | em-dashes per 1000 words |
|---|---|
| Opus 5 | **12.90** |
| Opus 5.5 | **0.05** |

Across 40 posts and roughly 55,000 words, Opus 5.5 used **two em-dashes in
total.** Opus 5 used them frequently. The em-dash heuristic for identifying
Claude writing worked well on Opus 5 and does not work on 5.5.

### The difference holds everywhere

Eight of the twenty topics are about AI and observability. The other twelve are
about travel, cooking, video games and books, and that split exists for a
reason: if claudisms were really an artefact of writing densely about technical
material, the gap would vanish once the topics got lighter. It does not.

| domain | opus-5 | opus-5.5 | gap |
|---|---|---|---|
| cooking | 3.83 | 2.67 | **1.16** |
| ai | 3.38 | 2.69 | 0.69 |
| travel | 3.33 | 2.67 | 0.66 |
| books | 3.33 | 2.83 | 0.50 |
| games | 3.50 | 3.17 | 0.33 |

The same holds across the five writing registers in the topic set:

| genre | opus-5 | opus-5.5 | gap |
|---|---|---|---|
| opinion | 3.92 | 3.08 | 0.84 |
| technical-explainer | 3.20 | 2.40 | 0.80 |
| news-analysis | 3.50 | 3.00 | 0.50 |
| product-announcement | 3.50 | 3.00 | 0.50 |
| tutorial-intro | 3.10 | 2.60 | 0.50 |

Ten out of ten breakdowns point in the same direction. Opinion writing is the
most claudism-dense register for both models. These constructions are
argumentative devices, and an opinion piece is an argument.

### Opus 5.5 did not get plainer, it swapped its tics

The deterministic scan counts structures as well as punctuation. Opus 5.5
scores lower on some measures and sharply **higher** on others:

| per 1000 words | opus-5 | opus-5.5 | |
|---|---|---|---|
| em-dashes | 13.30 | 0.05 | nearly eliminated |
| bold lead-in bullets | 2.02 | **4.96** | up 2.5× |
| rule-of-three | 2.71 | **3.66** | up 35% |
| mean word count | 1269 | 1365 | 8% longer |

Opus 5.5 writes longer, uses bolded bullet scaffolding and three-part lists
more often, and has almost stopped using the em-dash. Its writing register
changed.

A "was this written by Claude?" detector built on the Opus 5 signature,
including em-dashes, stock phrases and antithesis pivots, will **under-read
Opus 5.5** because the structures 5.5 favours increased. A useful metric set
needs both halves.

### The span judge: the moves halved, the em-dash vanished

The v2 judge quotes each claudism it finds and tags it with one of six
categories taken from the hand-flagged set. Counted per 1,000 words of prose:

| per 1000 words | opus-5 | opus-5.5 | change |
|---|---|---|---|
| salience flag | 1.75 | 0.90 | −49% |
| verdict intensifier | 1.06 | 0.44 | −58% |
| signpost | 0.79 | 0.55 | −30% |
| contrast reframe | 0.57 | 0.27 | −53% |
| stock metaphor | 0.43 | 0.16 | −63% |
| gotcha framing | 0.20 | 0.11 | −45% |
| **all spans** | **4.79** | **2.43** | **−49%** |

Opus 5.5 cut its em-dashes by more than 99%. It cut these constructions by
about half. Every category went down. Stock metaphors ("load-bearing", "doing
a lot of work") fell furthest, and signposts ("Here's the part that...") held
on best, at −30%. Salience flags, which assert that something matters without
showing why, are the most common move in both models.

An earlier version of this judge reported a much smaller gap: 13.05 against
9.58, or −27%. Its prompt tagged ordinary prose as well as tics ("First, a
definition.", "strain the context window", "It applies to all output tokens,
not only thinking."), and that floor of false positives is present in any
writing, so it shrank the difference between the models. The current prompt
applies one test to every candidate span: delete it, and if a fact, number,
mechanism or instruction is lost, it is not a tic. Each category also lists
examples of what not to tag. That run is kept in
`results/full-v1-judge-v2-gpt5.6-summary.json`.

The hand-written phrase list tells the same story at a smaller scale. With the
v2 patterns, a local rescan finds 1.32 stock phrases per 1,000 words in Opus 5
and 0.27 in Opus 5.5. Fixed wording is easy for a model to drop. The shape of
the argument underneath it changes more slowly.

### How far to trust this

The aggregate is solid. Forty posts per model, balanced, with every post
verified as having been written by the model it is labelled with, and every
topic handed byte-identical input to both models.

Each model × topic cell was sampled twice rather than three or more times, so
per-topic numbers are noisier than the aggregate. Raise the repeat count before
quoting any individual topic. The judge model does not accept `temperature=0`,
so the graded scores carry some irreducible variance. The em-dash and structural
counts are deterministic.

The span judge has three limits of its own:

- **Recall is measured, precision only roughly.** On the r1 posts it finds 57
  of the 83 hand-flagged claudisms (69%), where the regex finds 24 (29%). On
  the held-out r2 posts it finds 44 of 70 (63%). The r1 figure is flattered,
  because the prompt quotes some r1 flags as examples. It also tags about 60
  spans per split that nobody flagged. A spot check of those put precision at
  roughly 26 in 30 on Opus 5.5, but Claude did that labelling, on Claude's
  prose, and no human has checked it.
- **The held-out split is spent.** r2 has now been used to judge the prompt, so
  any further tuning needs fresh flags, ideally on Opus 5.5 posts, since all
  153 current flags are on Opus 5.
- **The 1–5 band is uncalibrated.** The density cut-offs were guessed before
  the judge ran, from the rate of hand flags (about 3 per 1,000 words). The v2
  score (4.15 against 3.15) separates the models, but the bands have not been
  fitted to anything. Use spans per 1,000 words until they are recalibrated.

Running the whole thing cost about $15 in research briefs, which is a one-off
because they are committed to the repository, plus $7.00 in generated posts.

---

## How it works

The design requires **the model ID to be the only thing that differs between
two runs.** A style comparison is invalid if the two models receive different
research, run at different reasoning depths, or use different configuration
from the machine. This requirement informs nearly every decision below.

### Stage A — research, once

Before any post is written, a research agent gathers source material for each
topic and writes it to `briefs/<slug>.md`. These briefs are **committed
fixtures**, not something regenerated per run. Each brief's SHA-256 is recorded
in `briefs/briefs.lock.json` and verified before any post is written; if a
brief has changed, the run stops rather than quietly producing an incomparable
result.

The briefs are deliberately terse bullet notes with source URLs rather than
flowing prose. If the research model wrote in paragraphs, its own stylistic
habits would sit in the writer's input, both models would echo them, and the
evaluator would end up scoring the brief. Keeping them telegraphic is why the
brief baseline scores so low.

Research needs the web, so this stage uses Anthropic's **server-side** web
search tool, which runs on Anthropic's infrastructure. That keeps the stage a
single API request rather than a tool-calling loop.

### Stage B — writing, the part being measured

Writing a post from a fixed brief is one model call: no tools, no loop, no
filesystem access. The harness therefore talks to the Messages API directly instead of wrapping
an agent framework around a single request. With no subprocess involved,
ambient environment variables and local `CLAUDE.md` files cannot influence the
prose.

Two settings require particular attention.

Reasoning effort is pinned to `medium` for both models.
Opus 5 defaults to `high` and Opus 5.5 defaults to `medium`, so leaving it
unset would compare *Opus 5 at high effort* against *Opus 5.5 at medium*, which would be a
confound rather than a model comparison.

The model is verified rather than assumed. Every response's `model` field is
checked against what was requested, and the run aborts on a mismatch. If a model other than the requested one wrote a post, the harness would fail
loudly. Server-side refusal fallbacks are left off because a refusal answered
by a different model would silently mislabel the output.

Each post is written with YAML front-matter recording everything that was
pinned: the model, the effort, the prompt hash, the brief hash, token counts
and cost. Any result can be traced back to the exact inputs that produced it.

### Stage C — scoring

Every run is traced to Arize AX. The v1 judge and the em-dash counter run **in
AX** and score the spans the harness produced, and `blogwriter-ax-report` reads
those scores back and aggregates them by model, domain and genre.

The v2 span judge runs locally, through `blogwriter-judge`. It was built to run
in AX too, but an AX template evaluator has to return one label from a fixed
set: a freeform evaluator is rejected when you create it, and AX adds its own
"explain, then label" instruction to the prompt, which overrides any request to
put a list of quotes in the explanation field. So the local command sends the
same prompt to `gpt-6-luna` through OpenAI, and writes
the quotes to a JSON file per model. The judge is still not a Claude model.

### Checking the evaluator against a human reader

v1 gives each post one label, and there is no way to check one label against a
human reader. So I read the 40 Opus 5 posts in a shared document and flagged
every claudism I saw. The 153 flags are in `annotations/opus-5-full-v1.json`,
with the post, section, line and full sentence for each one.

The flags showed three problems with v1:

- The regex phrase list matched 9 of the 153 flagged sentences.
- The thing I flagged most, prose saying something is important without
  showing why, had no category in the judge. That was 48 of the 153.
- Three judge categories (concessive pivot, meta writing, hedge then assert)
  matched almost none of the flags.

v2 changes both halves of the evaluator. The regex half, `PATTERN_VERSION =
"v2"` in `claudisms.py`, adds patterns for the fixed wording in the flags:
"worth internalising", "the whole point", "the honest answer", "doing a lot of
work", "the trap is". It widens `load_bearing` to catch "bears the load" and
"carries the weight", and keeps the name, so load-bearing counts compare
directly with v1. With these patterns the regex finds 45 of the 153 flags, up
from 9. The patterns were written from those same flags, so that is an
in-sample figure.

The judge half returns every instance it finds as an exact quote with one of six
categories: salience flag, contrast reframe, verdict intensifier, signpost,
gotcha framing and stock metaphor. Code turns the quotes into instances per
1,000 words. Rule of three and punchy closers are left out of the judge because
`claudisms.py` already counts both.

`blogwriter-validate` measures both halves against the flags. A flag counts as
found if a detected span overlaps the flagged sentence. The prompt is tuned on
the r1 posts and measured once on r2, so the reported number is not fitted to
its own test set.

"Load-bearing" is a must-catch. There are 3 uses in the Opus 5 posts and 0 in
Opus 5.5. If either half misses any of the 3, `blogwriter-validate` exits
non-zero, whatever the recall figure. Both halves currently catch all 3.

The v1 judge and its template are unchanged, so every existing score can
still be reproduced.

---

## Setting it up

### 1. Prerequisites

- Python 3.12 or later, and [uv](https://docs.astral.sh/uv/)
- An Anthropic API key with access to Opus 5 and Opus 5.5
- An OpenAI API key with access to `gpt-5.6-luna` (the v1 judge in AX) and
  `gpt-6-luna` (the v2 span judge)
- An Arize AX account
- The `ax` CLI, authenticated (check with `ax profiles show`)
- An OpenAI-backed AI integration configured in AX, for the v1 judge

### 2. Install

```bash
git clone git@github.com:jimbobbennett/claude-compare.git
cd claude-compare
uv sync
```

That installs the runtime dependencies plus the dev tools, pytest and ruff.

### 3. Configure credentials

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required. Used for both research and writing. |
| `OPENAI_API_KEY` | Required for `blogwriter-judge`, the v2 span judge. |
| `ARIZE_API_KEY` | Required, for tracing. |
| `ARIZE_SPACE_ID` | Required, for tracing. |
| `ARIZE_SPACE` | Space name or ID, used by `blogwriter-ax-report`. Find it with `ax spaces list`. |
| `BLOGWRITER_PROJECT_NAME` | Optional. Defaults to `claude-compare-blogwriter`. |
| `ARIZE_COLLECTOR_ENDPOINT` | Only if your Arize account is outside the US region. |

The project name is read from `BLOGWRITER_PROJECT_NAME` rather than the more
usual `ARIZE_PROJECT_NAME`, because that second variable is often already set
in a shell for unrelated tracing and would quietly send this experiment's
traces somewhere else.

### 4. Note the Anthropic SDK pin

`pyproject.toml` pins `anthropic==1.7.0`. The OpenInference instrumentor that
produces the LLM spans imports a private module which later SDK versions
renamed, so raising this pin stops spans being produced. If you do raise it,
confirm `anthropic._utils._transform` still imports first.

### 5. Verify the install

```bash
uv run pytest          # 52 tests, no network calls
uv run ruff check src/
uv run blogwriter --help
```

### 6. Create the two evaluators in AX

First find the AI integration for the judge:

```bash
ax ai-integrations list --space "your space name" -o json
```

Note the `id` of an OpenAI integration, then create the LLM judge. Its prompt
body lives in `ax/claudism_template.txt`:

```bash
SPACE="your space name"
INT="<ai-integration-id>"

ax evaluators create-evaluator template \
  --name "Claudism Density" --space "$SPACE" \
  --commit-message "v1" --template-name "claudism_density" \
  --ai-integration-id "$INT" --model-name "gpt-5.6-luna" \
  --include-explanations --use-function-calling \
  --direction MINIMIZE --data-granularity span \
  --classification-choices '{"saturated":5,"strong":4,"moderate":3,"faint":2,"absent":1}' \
  --template "$(cat ax/claudism_template.txt)"
```

Then the deterministic evaluator, whose two halves live in `ax/`:

```bash
ax evaluators create-evaluator code \
  --name "Em Dash Density" --space "$SPACE" \
  --commit-message "v1" --code-type custom --code-name "em_dash_density" \
  --variables '["output"]' --data-granularity span \
  --imports "$(cat ax/emdash_imports.py)" --code "$(cat ax/emdash_code.py)"
```

Both commands print the new evaluator's ID, and you should keep both IDs.

The v2 span judge needs nothing in AX. Its prompt is in
`ax/claudism_spans_template.txt` alongside the others, but it runs locally (see
[Stage C](#stage-c--scoring) for why).

### 7. Create the scoring tasks

An evaluator defines *how* to score, and a task defines *what* to score. You need
one task per evaluator:

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

The filter selects CHAIN spans, which covers both the posts and the research
briefs. This is intentional, because it means the brief baseline is scored in the
same pass. The report separates the two by span name.

Both commands print a task ID, which you will need to trigger scoring.

---

## Running it

### 1. Generate the research briefs

```bash
uv run blogwriter-research
```

This writes one brief per topic and records each hash in the lockfile. It skips
briefs that already exist, so it is safe to re-run. Replacing one requires
`--refresh-briefs` explicitly.

Expect a few minutes and roughly $0.60–$1.00 per topic. You can work through
them in batches:

```bash
uv run blogwriter-research --only searing-does-not-seal-juices --only first-trip-to-japan
```

Once you are happy with them, commit `briefs/`. From then on they are treated as
fixtures.

### 2. Write a single post to check the pipeline

```bash
uv run blogwriter --topic-slug how-llm-as-judge-works --model opus-5.5
```

The post lands in `output/<run_id>/<model_alias>/<slug>.r1.md`. Read the
front-matter and confirm `served_model` matches `model_id`.

### 3. Run the full matrix

```bash
uv run blogwriter-batch --models opus-5,opus-5.5 --repeats 2 --run-id full-v1
```

That is 20 topics × 2 models × 2 repeats = 80 posts, around 50 minutes and
about $7. Every brief hash is checked before the first post is written, so a
problem surfaces before any money is spent. A `manifest.json` is written
alongside the posts recording the pinned settings and every cell's result.

### 4. Confirm the run is valid

To confirm the run is valid, check that both models received identical input.
Pick a topic and diff the front-matter:

```bash
diff <(sed -n '/^---$/,/^---$/p' output/full-v1/opus-5/how-llm-as-judge-works.r1.md) \
     <(sed -n '/^---$/,/^---$/p' output/full-v1/opus-5.5/how-llm-as-judge-works.r1.md)
```

It should differ only in model identity, word count, tokens and cost.
`prompt_sha256`, `brief_sha256` and `effort` must be identical.

### 5. Score the posts in AX

Arize builds its evaluation index asynchronously, an hour or two behind
ingestion, so wait before triggering and set the window to end comfortably
before the present moment:

```bash
ax tasks trigger-run <LLM_TASK_ID> \
  --data-start-time "2026-09-23T01:00:00" --data-end-time "2026-09-23T02:10:00" \
  --max-spans 200 --wait

ax tasks trigger-run <CODE_TASK_ID> \
  --data-start-time "2026-09-23T01:00:00" --data-end-time "2026-09-23T02:10:00" \
  --max-spans 200 --wait
```

Each prints how many spans it scored. Expect one per post, plus one per brief
that falls inside the window.

To score future runs automatically instead, make a task continuous:

```bash
ax tasks update <TASK_ID> --is-continuous --sampling-rate 1.0
```

### 6. Read the results

```bash
uv run blogwriter-ax-report --run-id full-v1 --by domain
uv run blogwriter-ax-report --run-id full-v1 --by genre
```

`--run-id` restricts the report to a single batch, which keeps exploratory runs
out of a headline number. `--by` adds a breakdown by domain or genre, and
`--json` writes the summary to a file.

Labels and scores are coloured as a warning scale (red means obviously Claude,
green means it does not read as Claude), matching the `MINIMIZE` direction set
on the evaluator, so the AX dashboard and the terminal agree. Colour switches
off automatically when output is piped.

### 7. Run the span judge

```bash
uv run blogwriter-judge --run-id full-v1
```

This sends each post in the batch to the v2 judge, eight at a time, and writes
`output/full-v1/judge-v2/<model>.json` with every quote, its category and the
post's density, plus a `summary.json`. The 80-post run takes a few minutes. Use
`--model opus-5` to judge one model only. A post whose reply cannot be parsed is
reported and left out, and the command exits non-zero so a partial run is
visible.

### 8. Check the evaluator against the flags

```bash
uv run blogwriter-validate --split r1                      # regex half only
uv run blogwriter-validate --split r1 \
  --judge-spans output/full-v1/judge-v2/opus-5.json \
  --unflagged-out /tmp/unflagged.json
```

This prints recall for each half, the spans found per category, and the
load-bearing check. `--unflagged-out` writes the judge spans nobody flagged, so a
human can mark which are real. Run `--split r2` once, when the prompt is
settled, for the number you report.

### 9. Optionally, scan locally

```bash
uv run blogwriter-scan --run-id full-v1 --briefs --json output/full-v1/scan.json
```

This runs only the deterministic patterns. It makes no model calls and costs
nothing. It returns instantly and reports the structural metrics (bold lead-in
bullets, rule-of-three and em-dashes) at a finer grain than the AX evaluators.
It is useful while iterating, and it is the source of the "swapped tics" table
above.

---

## The evaluator prompts

### v1: one label per post

This is the v1 judge prompt in full, as stored in `ax/claudism_template.txt`.
`{output}` is its only variable, mapped by the task to
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

Labels map to scores: `saturated` 5, `strong` 4, `moderate` 3, `faint` 2,
`absent` 1.

Two things about this prompt are deliberate.

The judge is not a Claude model. It runs on `gpt-5.6-luna` through OpenAI.
What is being measured is Claude's own register, and a Claude judge would be
rating its own house style, which is a self-preference risk on exactly the axis
under test. Anthropic's own evaluation guidance is to grade with a different
model than the one that generated the output.

Formatting is excluded from the judge. Bold bullets and punctuation are
counted precisely by the code evaluator instead. An earlier version of the
prompt asked the judge about those too, and formatting so dominated the result
that the terse research briefs scored as highly as the finished posts. Keeping
the judge on voice and the regex on format gives the metric its separation.

### v2: every instance, quoted

The v2 prompt is in `ax/claudism_spans_template.txt`. It runs on `gpt-6-luna`,
keeps v1's "form, not content" opening, and asks for JSON instead of a label.
Before the categories it states one test for every candidate:

```text
THE CORE TEST (apply to every candidate before tagging it)
A tic adds emphasis, drama or suspense WITHOUT adding information. Mentally delete the span or rewrite it in flat plain words. If a fact, number, mechanism, condition or instruction would be lost, it is ordinary writing: do NOT tag it. Most sentences in a good post are ordinary writing.
```

These are its categories:

```text
TICS
1. salience_flag - the prose asserts that something is important instead of showing why: "The interaction matters", "That disagreement matters", "a fact worth internalising", "worth knowing cold", "Crucially,", "deserves a moment", "the highest-leverage decision", "This is the one people feel". Not a flag: a sentence that states a concrete effect ("That omission changes how you read the map" is a claim about an effect, not an assertion of importance).
2. contrast_reframe - one framing is negated and replaced with a sharper label or verdict, usually as a punchy pair: "Access is not ownership", "It's not cowardice, it's arithmetic", "That's not failure. That's satiety", "Frame generation is smoothness amplification, not performance", "The cold open is not backstory; it is a tension deposit", "Demos are short. Real work is not." The replacement is typically a crisp noun phrase that recasts the thing. Not a reframe: a scope qualifier ("it applies to all output tokens, not only thinking"), a correction whose second half is a number or evidence ("Most bags aren't lost. Delays account for 74%"), or an ordinary "but" clause.
3. verdict_intensifier - a word or phrase that marks a claim as final, sincere or significant without adding information: "that's the whole point", "the honest answer", "the real business model", "that's not accidental", "That's it.", "which is exactly the point". Not an intensifier: an ordinary evaluation with content ("straightforward and holds up well", "a real reason to choose one", "The industry's direction is clear: higher prices, more bundling").
4. signpost - teases or defers an insight instead of delivering it: "Here's the part that bites people", "Here's why, and what to do instead", "The short answer is", "Think about what that means", "Two things worth internalising:", "Here's the structure", "Here's what actually happens", "Read that the other way round". Any "Here's the/what..." opener that sets up the next sentence counts. Not a signpost: a neutral structural transition ("First, a definition.", "More precisely:", "The following tools each offer...", "This post looks at why.", "In practice, that means a few habits:").
5. gotcha_framing - a detail framed with trap vocabulary: "The trap is", "The catch is", "bites everyone", "catches people out", "Here is the thing nobody mentions". Not gotcha framing: a plain warning or condition with no trap framing ("Stays after 1 March are charged the new rates").
6. stock_metaphor - a stock mechanical or economic metaphor from the well-worn set: "load-bearing", "doing a lot of work", "doing the heavy lifting", "earns its keep", "earns its counter space", "a useful lens", "the knob you aren't tuning", "sharp edges", "where it falls over", "where the real spending lives", "launder", "moving parts". Always tag any use of "load-bearing" (literal or figurative, hyphenated or not) and close variants like "bears the load" or "carries the weight". Not a stock metaphor: the ordinary dead metaphors of English and normal technical vocabulary ("breaks down", "strain the context window", "an asset", "the same machinery", "buys scale", "workhorse", "for free", "burned rollouts", "opportunity cost", "under the hood").
```

The JSON shape is described in words rather than shown as an example, so the
template can be pasted into AX, where literal braces would be read as extra
variables. Both templates are generated from `judge_spec.py`, which holds the
one definition of a claudism, and a test fails if either file drifts from it.

---

## The topic set

`topics.yaml` holds twenty topics, tagged along two axes so neither can be
mistaken for the model's influence. Five **genres** cover different registers,
because these constructions appear far more readily in argument than in
instruction. Five **domains** cover different subject matter, because an
AI-only topic set could not separate Claude's voice from the effect of writing
about dense technical material.

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

Adding a topic does not disturb the existing briefs, because the writer's
prompt is built from the topic string alone.

---

## Project layout

```
claude-compare/
├── topics.yaml              # the 20 topics, tagged by genre and domain
├── briefs/                  # committed fixtures + briefs.lock.json
├── ax/                      # evaluator prompts and the AX code evaluator
├── annotations/             # 153 hand-flagged claudisms in the Opus 5 posts
├── results/                 # committed run summaries
├── src/blogwriter/
│   ├── tracing.py           # Arize registration
│   ├── models.py            # model aliases, effort, pricing
│   ├── prompts.py           # versioned research and writer prompts
│   ├── determinism.py       # hashing, the brief lockfile, version capture
│   ├── topics.py            # loading the topic set
│   ├── agent.py             # the model call, and Stage B
│   ├── research.py          # Stage A
│   ├── cli.py               # write one post
│   ├── batch.py             # the full matrix
│   ├── claudisms.py         # deterministic pattern scoring
│   ├── scan.py              # local offline scan
│   ├── judge_spec.py        # the one definition of a claudism (v1 and v2)
│   ├── judge.py             # run the v2 span judge over a batch
│   ├── validate.py          # check v2 against the hand-flagged claudisms
│   ├── destyle.py           # rewrite markdown to remove claudisms
│   ├── merge_rewrites.py    # merge rewrites section by section
│   └── ax_report.py         # read AX scores back and rank
└── tests/                   # pure-logic tests, no network
```

Generated posts and per-post judge output under `output/` are not committed,
since they are reproducible from the briefs, but the run summaries in
`results/` are.

---

## Development

```bash
uv run pytest
uv run ruff check src/
```

The tests cover the places where a silent bug would corrupt a result: model
resolution, prompt stability, brief integrity, length normalisation, the
report's filtering of unsound spans, judge-output parsing and the load-bearing
check. They make no network calls.

`ax/` is excluded from linting because it holds the two halves of the AX code
evaluator, which the platform requires as separate files; neither is valid
Python on its own.

---

## De-styling a document

The evaluator's definitions are reusable as an editing brief, which lets the
project edit its own prose. `judge_spec.py` holds the single definition of what
counts as a claudism; the templates in `ax/` are generated from it, and a test
fails if they drift apart. The rewriter targets the six v2 categories plus rule
of three and punchy closers.

```bash
# rewrite with a model, one section at a time
uv run blogwriter-destyle README.md --out /tmp/a.md --model claude-opus-5-5

# merge several rewrites, keeping the cleanest version of each section
uv run blogwriter-merge README.md \
  --variant opus55=/tmp/a.md --variant codex=/tmp/b.md --out /tmp/merged.md
```

The rewriter never shows fenced code blocks or tables to the model. They are
replaced with sentinels and substituted back byte-identical afterwards. Every
number in a section must still be present in the output, headings must match
exactly, and a section that shrinks below 55% of its original length is
rejected. A rejected section keeps the original and is reported.

The merge scores each section of each variant with the deterministic scorer and
takes the lowest-penalty version that has not lost content, added or removed a
horizontal rule, or changed a table. Sections under 60 words keep the original,
because per-1000-word densities are meaningless at that length.

An earlier version of this README was produced that way. Opus 5.5 and codex
each rewrote it from the same brief, and the merge took the better section from
each:

| variant | style penalty | em-dash/1k | rule-of-three/1k | integrity |
|---|---|---|---|---|
| original | 8.302 | 6.27 | 1.11 | — |
| opus-5.5 | 2.178 | 0.36 | 0.73 | fails: added 2 horizontal rules |
| codex | 2.751 | 0.00 | 1.56 | passes |
| merged | 2.186 | 0.00 | 1.16 | passes |

Opus 5.5 scored lowest on style but restructured the document, so it was
disqualified at the whole-document level. The merge is the best result that
preserves the original structure.

---

## Where to take it next

**Mark the unflagged spans.** The span judge tags about 60 spans per split
that nobody flagged. A human marking each as real or not would replace the
rough precision figure, and any real ones extend the flag set.

**Flag some Opus 5.5 posts.** Every hand flag is on Opus 5, and the held-out
split has been used. Flags on 5.5 give a fresh test set and check the judge on
the model it scores lower.

**Recalibrate the v2 bands.** The density cut-offs need setting from the
judge's own distribution before the 1–5 score means anything.

**Send the v2 spans back to AX.** The span judge runs outside AX today, so its
results are not beside the v1 scores on the traces. Writing them back as span
annotations would put both judges in one place.

**Raise the repeat count.** At two samples per cell the aggregate is sound but
individual topics are noisy. Three or more would make per-topic numbers
quotable.

**Derive the phrase list from the corpus.** v2 adds patterns taken from the
hand-flagged claudisms, but those are one reader's flags on one model.
Comparing n-gram frequencies across the 80-post corpus would give a list that
can be tested on text it wasn't built from.

**Move the structural metrics into AX.** Bold lead-in bullets and rule-of-three
are where Opus 5.5's style *increased*, and only the local scan measures them
today. The AX code evaluator counts em-dashes alone, so the hosted scoring sees
half the picture.

**Average several judge passes.** The judge model will not accept
`temperature=0`, so a single pass leaves more variance in the graded score than
necessary.
