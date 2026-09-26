![Claude Compare! - an operatic tenor in a blue tuxedo beside a dark green panel reading "CLAUDE COMPARE!"](docs/banner.jpg)

# Claude Compare!

Anthropic says Opus 5.5 fixed Claude's writing. This repository tests that
claim with the standard evaluation loop, run in **Arize AX**:

1. build a dataset
2. run an experiment for each model
3. annotate the output by hand
4. build an evaluator from the annotations
5. run it, and iterate on it against the annotations

People call Claude's recognisable habits *claudisms*: em-dash asides, "it's not
X, it's Y", "load-bearing", announcing an insight instead of delivering it.

**The em-dash really is gone.** Opus 5 uses 12.9 per 1,000 words. Opus 5.5
used two in its entire 57,000 words of output. **The other claudisms halved,**
from 4.79 to 2.38 per 1,000 words. Better, but not fixed.

---

## The results

Everything below comes from 80 posts: 20 topics, 2 models, 2 repeats. That is
53,225 words from Opus 5 and 57,408 from Opus 5.5.

### The em-dash

| | em-dashes per 1,000 words |
|---|---|
| Opus 5 | **12.9** |
| Opus 5.5 | **0.05** |

A code evaluator counts the character directly, so no judge is involved. Opus
5.5 used two em-dashes in all 40 posts. A "was this written by Claude?" check
built on the em-dash worked on Opus 5 and does not work on Opus 5.5.

### The other claudisms

The span judge returns every claudism it finds as a quote, sorted into one of
six categories. Running in AX over all four experiments, it found:

| category | example | Opus 5 | Opus 5.5 | change |
|---|---|---|---|---|
| salience flag | "This matters." | 1.67 | 0.93 | −44% |
| verdict intensifier | "The honest answer is…" | 1.10 | 0.38 | −65% |
| signpost | "Here's the part that…" | 0.79 | 0.53 | −33% |
| contrast reframe | "It's a topology, not a genre." | 0.63 | 0.27 | −56% |
| stock metaphor | "load-bearing", "earns its keep" | 0.43 | 0.13 | −70% |
| gotcha framing | "The trap is…" | 0.16 | 0.13 | −19% |
| **all claudisms** | | **4.79** | **2.38** | **−50%** |

Claudisms per 1,000 words, from the span judge running in Arize AX
(`results/full-v1-ax-experiments.json`).

Every category went down. Salience flags, prose that says something matters
instead of showing why, are still the most common claudism in both models.
Gotcha framing is too rare to read much into, at 8 uses against 7.

Opus 5.5 still wrote that a stand mixer "earns its counter space" and that a
searing technique "earns its place".

### The gap holds everywhere

The topics span five genres and five domains, so that an effect of writing
about dense technical material can't pass for Claude's voice. The earlier
per-post judge (v1, one 1–5 score per post, see
[Scoring the traces](#scoring-the-traces-v1)) shows the gap in every one:

| domain | opus-5 | opus-5.5 | gap |
|---|---|---|---|
| cooking | 3.83 | 2.67 | 1.16 |
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

Opinion writing is the most claudism-dense genre for both models. These
constructions are argumentative devices, and an opinion piece is an argument.

### New habits

A deterministic scan counts structure as well as wording. Opus 5.5 dropped
some tics and picked up others:

| per 1,000 words | opus-5 | opus-5.5 | |
|---|---|---|---|
| bold lead-in bullets | 2.02 | **4.96** | about 2.5× |
| rule of three | 2.71 | **3.66** | +35% |
| mean prose words per post | 1,269 | 1,365 | 8% longer |

Some of the old tics were traded in rather than dropped.

---

## The loop

### Step 1: build a dataset

A dataset is the fixed set of inputs every experiment runs over, so when a
score moves, the change you made moved it, not the inputs.

The inputs here are 20 research briefs, each one the notes for a blog post on
one of 20 topics (listed under [The topic set](#the-topic-set)). The topics
cover five genres (opinion, technical explainer, tutorial intro, news analysis,
product announcement) and five domains (AI, travel, cooking, games, books).

Two things make the dataset trustworthy.

It is frozen. Opus 5 researched each topic once, with Anthropic's server-side
web search. The briefs are committed to `briefs/`, and their SHA-256 hashes are
recorded in `briefs/briefs.lock.json`. Every run checks them and stops if a
brief has changed. The writer gets no tools and no network, so the brief is all
it has.

The inputs don't carry the style under test. The briefs are bullet fragments
with source URLs, not prose, so Opus 5's own habits can't leak into what the
writers read. Scored by the v1 judge, the briefs rate 1.62 ("faint") against
3.45 and 2.77 for the posts, which is how you know the evaluator measures the
writing and not the subject.

In AX the dataset is `claude-compare-full-v1`: one example per topic, holding
the brief and the exact writer prompt, with hashes for both.

### Step 2: run an experiment for each model

An experiment is one run of the task over the whole dataset. Comparing two
experiments compares whatever differs between them, so only the model
changes:

- Both models get a byte-identical prompt, checked by hash.
- Effort is pinned to `medium` for both. Opus 5 defaults to `high` and Opus 5.5
  to `medium`, so leaving the defaults would have compared two settings, not two
  models. Thinking is adaptive for both.
- The served model is checked on every response, and the run aborts on a
  mismatch. This matters in practice: the Claude Agent SDK, which drives the
  Claude Code CLI, quietly served Opus 5 when asked for Opus 5.5. That is why
  the harness calls the Messages API directly.
- Refusal fallbacks are off, because a refusal answered by another model would
  mislabel the post.

Model output varies between runs, so each model ran over the dataset twice.
That is four experiments in AX (`full-v1 opus-5 r1`, `r2`, `full-v1 opus-5.5
r1`, `r2`) and 80 posts. Every post was also traced to AX as it was written,
with its YAML front-matter recording the model, effort, hashes, tokens and
cost.

### Step 3: annotate the output

Annotations are human labels on the output: the ground truth an evaluator is
checked against. They were made before the evaluator was settled, and at the
level the evaluator works at, individual phrases rather than whole posts.

All 40 Opus 5 posts went into one document and were read end to end, with a
"Claudism" comment on every phrase that made me wince: 153 flags across 38 of
the 40 posts. They are in `annotations/opus-5-full-v1.json`, each with its post,
section, line and sentence. In AX they are annotations on the Opus 5 runs.

The flags were not what I expected. A hand-written list of famous claudisms
("load-bearing", "delve", "crucially", "genuinely") matched 9 of the 153.
"Load-bearing" appears three times in Opus 5's 53,000 words, and never in
Opus 5.5.

What I had flagged were rhetorical moves. The biggest group, about 48 of the
153, was prose telling the reader something is important instead of showing
why: "The interaction matters", "a fact worth internalising", "deserves a
moment". Next came contrast reframes, verdict intensifiers ("the honest
answer", "the whole point"), and signposts that tease a point instead of making
it. None of those are fixed wording, so a phrase list can't catch them.

AX stores an annotation as plain text on the whole run, with no way to mark
part of the output. So each flag is stored as a line with its character
offsets into the post:

```
483-524 | That single announcement is a useful lens
```

The evaluator returns the same format with a category added, so the two can be
matched by position.

### Step 4: build an evaluator from the annotations

The first evaluator gave each post a single 1–5 score (v1, still in the repo).
A single number can't be checked against 153 human flags, so the evaluator in
use is a **span judge**. It returns every claudism as an exact quote, in the
same shape as the annotations, so its recall against the flags can be measured
directly.

The annotations shaped it in three ways:

- The six categories come from the flags: salience flag, contrast reframe,
  verdict intensifier, signpost, gotcha framing and stock metaphor. Three v1
  categories the flags didn't support (concessive pivot, meta writing, hedge
  then assert) were dropped.
- The flags are test cases. All three "load-bearing" sentences must be caught,
  or `blogwriter-validate` and `blogwriter-ax-experiments recall` fail.
- Tuning used the r1 posts, with r2 held out.

Some choices apply to almost any evaluator:

- Use code where you can. Counting em-dashes is a code evaluator, `Em Dash
  Density`.
- Don't let a model grade its own family. The judge is OpenAI's `gpt-6-luna`.
- Normalise for length. Opus 5.5 writes about 8% longer, so every count is per
  1,000 words.

Both evaluators run in AX against all four experiments. The span judge runs as
a **remote evaluator**: `blogwriter-eval-server` serves the judge over HTTP,
and AX calls it for each run and stores what it returns. An AX template
evaluator can't do this job, because it must return one label from a fixed
set, and AX's own "explain, then label" instruction overrides any request to
return a list of quotes. A remote evaluator returns whatever the endpoint
sends.

### Step 5: run it

The results are at the top of this page. Recall against the hand flags,
computed from the spans AX stored, is 65% on r1 and 59% on the held-out r2,
and all three "load-bearing" sentences are caught. A local run of the same
judge gave 69% and 63%. `gpt-6-luna` doesn't accept `temperature=0`, so two
passes over the same post differ a little.

### Iterating on the judge

The −50% came from the third version of the judge. The annotations are what
let it be tuned with numbers.

| version | in the code | judge model | Opus 5 | Opus 5.5 | change |
|---|---|---|---|---|---|
| first | v2 prompt | `gpt-5.6-luna` | 13.05 | 9.58 | −27% |
| second | v2 prompt | `gpt-6-luna` | 9.48 | 6.25 | −34% |
| third | v2.2 prompt (current) | `gpt-6-luna` | 4.79 | 2.43 | −49% locally, −50% in AX |

"v1" in the code is the earlier judge that gives one 1–5 score per post, which
came before these three.

The first two versions had high recall against the flags (75% on r1 and 74% on
r2 for the second). Recall says nothing about what else the judge tagged,
though. In a random sample of the spans the second version found in Opus 5.5
posts, only about 40% were real claudisms (about 68% for Opus 5). The rest was
ordinary writing: "First, a definition." tagged as a signpost, "strain the
context window" as a stock metaphor, "It applies to all output tokens, not only
thinking." as a contrast reframe.

Those false positives weren't random. Every writer uses plain transitions and
ordinary metaphors, so they formed a floor under both models' scores and made
them look closer than they are.

The third version gives the judge a test to run on every candidate before
tagging it: delete the phrase and reread the sentence. If a fact, a number, how
something works or what to do is lost, the phrase carries information and
isn't a claudism. If nothing is lost, it counts. "This matters." can go without
losing anything, so it's tagged. Deleting "not only thinking" from "It applies
to all output tokens, not only thinking." loses the point of the sentence, so
it isn't.

Each category also got examples of what not to tag, and stock metaphors were
limited to the well-worn ones. Precision on the Opus 5.5 sample rose to about
26 in 30. Held-out recall fell from 74% to 64% in that tuning run, and all
three "load-bearing" sentences were still caught.

The precision samples (30 to 40 spans each) were labelled by Claude, not by a
person, so treat those figures as rough. The recall figures come from the hand
flags. The first version's run is kept in
`results/full-v1-judge-v2-gpt5.6-summary.json`.

### How far to trust this

- The aggregate is sound: 40 posts per model, every post verified as written by
  the model it's labelled with, and byte-identical input to both models.
- Per-topic numbers are noisy at two samples per cell. Use the aggregate.
- The hand flags cover Opus 5 only, and they are one reader's judgement.
- Recall of about 60–65% means the judge misses some of what a person flags,
  while its unflagged spans pull the other way. The comparison between the
  models is sounder than either absolute number.
- The 1–5 density bands the span judge also returns were never calibrated. Use
  the per-1,000-word rate.
- Running it cost about $15 for the research briefs (a one-off, since they are
  committed), $7 for the 80 posts and a few dollars of judge calls.

---

## Setting it up

### 1. Prerequisites

- Python 3.12 or later, and [uv](https://docs.astral.sh/uv/)
- An Anthropic API key with access to Opus 5 and Opus 5.5
- An OpenAI API key with access to `gpt-6-luna` (the span judge) and
  `gpt-5.6-luna` (the v1 judge)
- An Arize AX account with remote evaluators enabled
- The `ax` CLI, authenticated (check with `ax profiles show`)
- `cloudflared`, to expose the remote evaluator to AX

### 2. Install

```bash
git clone git@github.com:jimbobbennett/claude-compare.git
cd claude-compare
uv sync --group server
```

That installs the runtime dependencies, the dev tools (pytest, ruff, httpx)
and the remote evaluator's server (FastAPI, uvicorn).

### 3. Configure credentials

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required. Used for research and writing. |
| `OPENAI_API_KEY` | Required for the span judge, locally and in the remote evaluator. |
| `ARIZE_API_KEY` | Required, for tracing. |
| `ARIZE_SPACE_ID` | Required, for tracing. |
| `ARIZE_SPACE` | Space name or ID, used by `blogwriter-ax-experiments` and `blogwriter-ax-report`. Find it with `ax spaces list`. |
| `BLOGWRITER_PROJECT_NAME` | Optional. Defaults to `claude-compare-blogwriter`. |
| `ARIZE_COLLECTOR_ENDPOINT` | Only if your Arize account is outside the US region. |

The project name is read from `BLOGWRITER_PROJECT_NAME` rather than the usual
`ARIZE_PROJECT_NAME`, because that one is often already set in a shell for
something else and would quietly send the traces elsewhere.

### 4. Note the Anthropic SDK pin

`pyproject.toml` pins `anthropic==1.7.0`. The OpenInference instrumentor that
produces the LLM spans imports a private module that later SDK versions
renamed, so raising the pin stops the spans. If you raise it, check that
`anthropic._utils._transform` still imports.

### 5. Check the install

```bash
uv run pytest          # 60 tests, no network calls
uv run ruff check src/ tests/
which -a ax            # the first ax should be the CLI you authenticated
```

An old `ax` installed into a Python interpreter shadows the real CLI for any
command Python starts, and fails on newer server responses ("additional fields
(not defined in Experiment) in the input: space_id"). The code skips
interpreter `bin` directories when it looks for `ax`, and `AX_BIN` overrides
the choice. Remove a stray copy with `pip uninstall arize-ax-cli` in that
interpreter.

---

## Running it

The steps follow the loop.

### 1. The research briefs (the dataset's inputs)

The 20 briefs are committed, so you only need this to add topics or start
again:

```bash
uv run blogwriter-research
```

It skips briefs that already exist and records each hash in the lockfile.
Replacing a brief needs `--refresh-briefs`. Expect a few minutes and $0.60–1.00
per topic. `--only <slug>` does one topic at a time.

### 2. Write the posts (the experiments' outputs)

Check the pipeline with one post, then run the matrix:

```bash
uv run blogwriter --topic-slug how-llm-as-judge-works --model opus-5.5
uv run blogwriter-batch --models opus-5,opus-5.5 --repeats 2 --run-id full-v1
```

That is 80 posts, about 50 minutes and $7, written to
`output/full-v1/<model>/<slug>.r<N>.md` with a `manifest.json`. Every brief
hash is checked before the first post is written.

To confirm both models got identical input, diff the front-matter of one
topic. It should differ only in model, word count, tokens and cost:

```bash
diff <(sed -n '/^---$/,/^---$/p' output/full-v1/opus-5/how-llm-as-judge-works.r1.md) \
     <(sed -n '/^---$/,/^---$/p' output/full-v1/opus-5.5/how-llm-as-judge-works.r1.md)
```

### 3. Create the dataset and experiments in AX

```bash
uv run blogwriter-ax-experiments upload
```

This creates the dataset `claude-compare-<run>` and one experiment per model
and repeat, whose runs are the posts already written. Nothing is regenerated.
Before creating anything it renders each prompt again and checks its hash
against the manifest, and checks every post's served model. It can be re-run
safely: it reuses the dataset and any complete experiment. IDs are kept in
`output/<run>/ax/state.json`.

### 4. Add the annotations

```bash
uv run blogwriter-ax-experiments annotate
```

This writes the 153 flags onto the Opus 5 runs as `claudisms` (the
`start-end | quote` lines) and `claudism_count`, creating the annotation
configs if they don't exist. AX limits annotation text to 1,500 characters and
rejects the whole batch if one value is over, so lengths are checked first.
The densest post's flags come to 578 characters.

### 5. Create the evaluators and run them

The em-dash code evaluator. Its two halves are in `ax/`:

```bash
ax evaluators create-evaluator code \
  --name "Em Dash Density" --space "$ARIZE_SPACE" \
  --commit-message "v1" --code-type custom --code-name "em_dash_density" \
  --variables '["output"]' --data-granularity span \
  --imports "$(cat ax/emdash_imports.py)" --code "$(cat ax/emdash_code.py)"

uv run blogwriter-ax-experiments tasks --evaluator "Em Dash Density"
```

`tasks` creates and runs **one task per experiment**. Afterwards it recomputes
every em-dash score locally and compares.

The span judge, as a remote evaluator. Start the server and a tunnel, and leave
them running:

```bash
PORT=8765 ./scripts/serve-evaluator.sh
```

The script starts `blogwriter-eval-server`, puts a Cloudflare quick tunnel in
front of it, and prints the public URL. The first time, it generates a bearer
token into `.eval-token` (gitignored), which AX must send. It never prints the
token. Stopping either process stops both. To restart only the server, run the
tunnel on its own with `cloudflared tunnel --url http://127.0.0.1:8765`.

Register it in AX:

```bash
~/.local/share/uv/tools/arize-ax-cli/bin/python \
  scripts/register_remote_evaluator.py https://<tunnel>.trycloudflare.com \
  --space "$ARIZE_SPACE"
```

This creates the `EVALUATOR` integration (endpoint, bearer header and input
schema) and the `claudism_spans` remote evaluator through the AX REST API. It
runs on the `ax` CLI's own Python so that it can use the SDK bundled with it,
which authenticates with your `ax` profile; no key is read or passed. The `ax`
CLI can't create the integration itself. A quick tunnel gets a new URL each
time it starts; re-run the script and it updates the endpoint.

Then, in the AX UI, create one evaluation task per experiment on the
dataset, with the `claudism_spans` evaluator and `output` mapped to the run's
`output`, and run all four. The task has to be made in the UI: a task created
through the API accepts the remote evaluator but is cancelled without calling
the endpoint.

### 6. Check the evaluator and read the results

```bash
uv run blogwriter-ax-experiments recall
uv run blogwriter-ax-experiments report --json results/full-v1-ax-experiments.json
```

`recall` matches the evaluator's spans to the flags, by position and then by
text, writes `claudism_recall` onto each annotated run, and fails if a
"load-bearing" sentence was missed. `report` prints each evaluator and
annotation per experiment and per model, and the per-category rates. Both stop
if any stored span isn't a passage of its own run's post.

### 7. Iterate on the judge locally

Tuning is faster locally. The same prompt and parsing run through
`blogwriter-judge`:

```bash
uv run blogwriter-judge --run-id full-v1
uv run blogwriter-validate --split r1 \
  --judge-spans output/full-v1/judge-v2/opus-5.json \
  --unflagged-out /tmp/unflagged.json
```

`blogwriter-validate` prints recall for the judge and for the regex patterns,
the spans per category, and the "load-bearing" check. `--unflagged-out`
writes the spans nobody flagged, for a person to mark real or not. Tune on
`r1`, and run `--split r2` once, for the number you report.

The deterministic scan behind the "new habits" table makes no model calls:

```bash
uv run blogwriter-scan --run-id full-v1 --briefs
```

---

## Things to know about AX

These were found with ax CLI 0.35.0 in September 2026. Each one shaped the
code.

- **Run one task per experiment.** An evaluation task over several experiments
  stored each experiment's results on a different experiment's runs, shifted by
  one. It happened with the code evaluator (task made through the API) and the
  remote evaluator (task made in the UI), and reproduced with two experiments.
  A task over one experiment attaches every result correctly. That is why
  `tasks` makes one task per experiment and checks the em-dash scores, and why
  `recall` and `report` check that each span is a passage of its own post.
- **Remote evaluators: the API can create them, only the UI can run them.** The
  REST API creates the `EVALUATOR` integration (headers are encrypted and never
  returned) and the `REMOTE` evaluator. API task types don't include one that
  runs it. Tasks created in the UI work, but don't appear in `ax tasks list`.
- **The input schema nests the fields under `input`.** The schema describes the
  whole request body, and the UI only maps variables from fields under
  `input`. AX sends `{"metadata": {...}, "input": {"output": "<post>"}}`.
- **`record_id` is the dataset example ID**, shared by every experiment's post
  on the same topic. It can't identify a run. The server shares judge calls by
  the output's hash instead, so AX's retries don't pay twice.
- **Exports carry evaluations as flat keys** (`eval.<name>.score`, `.label`,
  `.explanation`) under `additional_properties`, and annotations as an
  `annotations` list.
- **An annotation is keyed by run and name.** A second value with the same name
  replaces the first, so all of a post's flags live in one `claudisms` value.
- **Re-triggering a task on runs that already have results is cancelled** at
  0/0/0. To re-score, rebuild the experiments with `upload`, then `annotate` and
  `tasks`.

---

## The remote evaluator

The endpoint receives:

```json
{"metadata": {"evaluator": "...", "record_id": "...", "request_id": "..."},
 "input": {"output": "<the post>"}}
```

and returns:

```json
{"score": 4.29, "label": "strong",
 "explanation": "511-524 | stock_metaphor | a useful lens\n1178-1200 | verdict_intensifier | That's not accidental."}
```

The score is claudisms per 1,000 words of prose. The label is the density band.
The explanation lists each span as `start-end | category | quote`, where
`-1--1` means the quote couldn't be located in the post. The judge often drops
markdown from its quotes ("cold open" for `**cold open**`), so quotes are
located with a match that tolerates dropped `*`, `_` and backticks.

The server returns 401 without the bearer token and 502 if the judge fails, so
that AX retries. It logs each request's field names (never the content) and
each result's score, span count and time. One call through the tunnel took
about 16 seconds; with AX sending in parallel, about 80.

---

## The evaluator prompts

### The span judge (v2.2)

The prompt is in `ax/claudism_spans_template.txt`. It opens by telling the
judge to rate form, never subject or quality, then applies one test to every
candidate:

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

The judge replies with JSON: a list of instances, each with a quote and a
category. The format is described in words rather than shown, so the template
contains no literal braces for AX to read as variables. Both templates are
generated from `judge_spec.py`, which holds the one definition of a claudism,
and a test fails if a file drifts from it.

### v1: one score per post

The earlier judge, in full, as stored in `ax/claudism_template.txt`. It runs on
`gpt-5.6-luna`, and `{output}` is its only variable:

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

An earlier draft also asked about formatting and punctuation, and formatting
dominated so much that the terse briefs scored as high as the finished posts.
Leaving format to the code evaluator gave the score its separation.

---

## Scoring the traces (v1)

Before the experiments existed, the v1 judge and the em-dash counter scored the
posts' traces in the AX project `claude-compare-blogwriter`, and
`blogwriter-ax-report` read the scores back. That is where the genre, domain and
brief-baseline figures above come from.

```
  group                    n  claudism     sd   modal label  em_dash/1k
  ---------------------------------------------------------------------
  opus-5                  40      3.45   0.50      moderate       12.90
  opus-5.5                40      2.77   0.53      moderate        0.05
  BRIEFS (baseline)        8      1.62      -        faint            -
```

To reproduce it, create the v1 evaluator and a task on the project for each
evaluator, filtered to CHAIN spans (which covers posts and briefs), and
trigger them over the run's time window:

```bash
ax evaluators create-evaluator template \
  --name "Claudism Density" --space "$ARIZE_SPACE" \
  --commit-message "v1" --template-name "claudism_density" \
  --ai-integration-id "<openai-integration-id>" --model-name "gpt-5.6-luna" \
  --include-explanations --use-function-calling \
  --direction MINIMIZE --data-granularity span \
  --classification-choices '{"saturated":5,"strong":4,"moderate":3,"faint":2,"absent":1}' \
  --template "$(cat ax/claudism_template.txt)"

ax tasks create-evaluation --name "Claudism Scoring (LLM judge)" \
  --task-type TEMPLATE_EVALUATION --project claude-compare-blogwriter \
  --space "$ARIZE_SPACE" --query-filter "attributes.openinference.span.kind = 'CHAIN'" \
  --evaluators '[{"evaluator_id":"<EVAL_ID>","column_mappings":{"output":"attributes.output.value"}}]' \
  --no-continuous

ax tasks trigger-run <TASK_ID> \
  --data-start-time "2026-09-23T01:00:00" --data-end-time "2026-09-23T02:10:00" \
  --max-spans 200 --wait

uv run blogwriter-ax-report --run-id full-v1 --by domain
```

AX's evaluation index runs an hour or two behind ingestion, so end the window
well before the present.

---

## The topic set

`topics.yaml` holds the 20 topics, tagged by genre and domain.

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

Adding a topic doesn't disturb the existing briefs, because the writer's prompt
is built from the topic string alone.

---

## De-styling a document

The evaluator's definitions double as an editing brief:

```bash
# rewrite with a model, one section at a time
uv run blogwriter-destyle README.md --out /tmp/a.md --model claude-opus-5-5

# merge several rewrites, keeping the cleanest version of each section
uv run blogwriter-merge README.md \
  --variant opus55=/tmp/a.md --variant codex=/tmp/b.md --out /tmp/merged.md
```

The rewriter never shows code blocks or tables to the model; they are swapped
for placeholders and restored byte for byte. Every number must survive,
headings must match, and a section that shrinks below 55% of its length is
rejected and kept as it was. The merge scores each section of each rewrite with
the deterministic scorer and keeps the cleanest one that hasn't lost content or
changed structure.

An earlier version of this README went through it. Opus 5.5 and codex each
rewrote it, and the merge took the better section from each:

| variant | style penalty | em-dash/1k | rule-of-three/1k | integrity |
|---|---|---|---|---|
| original | 8.302 | 6.27 | 1.11 | - |
| opus-5.5 | 2.178 | 0.36 | 0.73 | fails: added 2 horizontal rules |
| codex | 2.751 | 0.00 | 1.56 | passes |
| merged | 2.186 | 0.00 | 1.16 | passes |

---

## Project layout

```
claude-compare/
├── topics.yaml              # the 20 topics, tagged by genre and domain
├── briefs/                  # the dataset's inputs, hash-locked
├── annotations/             # the 153 hand flags on the Opus 5 posts
├── ax/                      # evaluator prompts and the code evaluator
├── results/                 # committed run summaries
├── scripts/                 # tunnel launcher, remote evaluator registration
├── docs/banner.jpg
├── src/blogwriter/
│   ├── research.py          # write the briefs
│   ├── agent.py             # the model call
│   ├── cli.py, batch.py     # write one post, or the whole matrix
│   ├── prompts.py           # versioned research and writer prompts
│   ├── models.py            # model aliases, effort, pricing
│   ├── determinism.py       # hashing and the brief lockfile
│   ├── topics.py            # the topic set
│   ├── tracing.py           # Arize registration
│   ├── ax_experiments.py    # dataset, experiments, annotations, tasks, recall, report
│   ├── eval_server.py       # the span judge as an AX remote evaluator
│   ├── positions.py         # the `start-end | quote` line format
│   ├── judge_spec.py        # the one definition of a claudism
│   ├── judge.py             # the span judge, run locally
│   ├── validate.py          # recall against the hand flags
│   ├── claudisms.py         # deterministic pattern scoring
│   ├── scan.py              # the local scan
│   ├── ax_report.py         # v1 scores read back from the traces
│   ├── destyle.py           # rewrite markdown without claudisms
│   └── merge_rewrites.py    # merge rewrites section by section
└── tests/                   # no network calls
```

Generated posts and per-post judge output in `output/` aren't committed,
because they can be regenerated from the briefs. The run summaries in
`results/` are:

| file | contents |
|---|---|
| `full-v1-ax-experiments.json` | the AX experiment results, including per-category rates |
| `full-v1-judge-v2-summary.json` | the current judge, run locally |
| `full-v1-judge-v2-gpt5.6-summary.json` | the first version of the judge (−27%) |
| `full-v1-ax-summary.json` | v1 scores from the traces |
| `full-v1-scan-summary.json` | the deterministic scan |
| `full-v1-manifest.json` | every post's model, tokens and cost |

---

## Development

```bash
uv run pytest
uv run ruff check src/ tests/
```

The tests cover the places where a silent bug would corrupt a result: model
resolution, prompt stability, brief integrity, length normalisation, judge
output parsing, the "load-bearing" check, the position format and annotation
limits, matching spans to flags, spotting results on the wrong run, and the
remote evaluator's auth and request handling.

`ax/` is excluded from linting because the code evaluator's two halves must be
separate files, and neither is valid Python on its own.

---

## Where to take it next

- Flag some Opus 5.5 posts. Every hand flag is on Opus 5, and the held-out
  split has been used, so this gives a fresh test set and a human check on the
  model that scores lower.
- Mark the spans the judge found that nobody flagged, to replace the rough
  precision figure with a real one.
- Calibrate the density bands before using them.
- Host the remote evaluator somewhere permanent, so it can also score new traces
  continuously.
- Raise the repeat count, so per-topic numbers mean something.
- Move the structural counts (bold lead-in bullets, rule of three) into AX, since
  that is where Opus 5.5's style increased.
