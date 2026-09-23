# claude-compare

Does Claude Opus 5.5 still write with Opus 5's signature style?

This is the measurement harness: a two-stage blog writer with a configurable
model, traced into Arize AX. A "claudism" evaluator is the next phase.

## The one design requirement

**The model ID must be the only thing that differs between two runs.** A style
comparison is worthless if the models were also handed different research, ran
at different effort levels, or picked up different config off disk.

| Drift source | How it's pinned |
|---|---|
| Research / tool variance | Briefs are committed fixtures; the writer gets no tools |
| A brief changing silently | SHA-256 per brief in `briefs/briefs.lock.json`, verified every run |
| Effort default mismatch | `effort="medium"` explicit for both models (see below) |
| Thinking config | Adaptive only — Opus 5.5 returns 400 for `disabled` or `budget_tokens` |
| Local config leakage | Impossible by construction — no subprocess, no filesystem settings |
| Prompt text drift | `WRITER_PROMPT_VERSION` + SHA-256 of the rendered prompt, per run |
| Model silently substituted | Run aborts unless `response.model` equals the requested ID |
| A refusal answered by another model | Server-side `fallbacks` deliberately **not** enabled; refusal is fatal |
| Harness version drift | Anthropic SDK version in every manifest (pinned `==1.7.0`) |
| Post length skewing density | Same word target; score per 1000 words, raw counts kept |
| Sampling stochasticity | `--repeats N` |

### Why effort is pinned

Opus 5 defaults to `effort: high`. **Opus 5.5 defaults to `medium`.** Leave it
unset and you are not comparing Opus 5 to Opus 5.5 — you are comparing *Opus 5
at high* to *Opus 5.5 at medium*. 5.5 also thinks more per turn at any given
effort level, which is visible in the recorded `thinking_tokens` (26 vs 108 on
the same prompt at `medium`, in one observed pair).

### Why briefs are fixtures

Generated once, committed, never regenerated during a comparison.
`--refresh-briefs` is required to replace one, which rewrites the lockfile and
so marks earlier results as a different input generation.

Briefs are deliberately **telegraphic** — fact bullets with source URLs, no
prose. If a research model wrote flowing paragraphs, its own stylistic tics
would sit in the writer's input and both models would echo them; the evaluator
would then be scoring the brief. The evaluator phase scores the briefs too, as
the contamination baseline.

## Why the Messages API, not the Claude Agent SDK

Writing a post from a fixed brief is one LLM call: no tools, no loop, no
filesystem. An agent harness supplies an agent loop, tool execution, context
management and permissions — none of which this uses. Two concrete reasons
beyond simplicity:

1. **The Agent SDK cannot drive Opus 5.5.** It spawns the Claude Code CLI as its
   only transport, and CLI 2.1.280 accepts `claude-opus-5-5` then silently
   serves `claude-opus-5`. The raw Messages API serves it correctly.
2. **It removes confounds.** No subprocess means no inherited `CLAUDE_*` session
   state and no `CLAUDE.md` / `settings.json` leakage — nothing to suppress,
   because there is nothing to inherit.

Research needs the web but not an agent loop either: the **server-side**
`web_search_20260209` tool runs on Anthropic's infrastructure. So both stages
are plain Anthropic SDK calls. (That tool does dynamic filtering via code
execution internally — do **not** declare `code_execution` alongside it.)

The Anthropic instrumentor emits the LLM span, so model, messages, token counts
and invocation parameters are captured natively. Each post also gets a CHAIN
span carrying the run's identity and the computed cost.

**`anthropic` is pinned to `==1.7.0`.** Instrumentor 2.1.5 imports
`anthropic._utils._transform`, which exists in 1.7.0 but was renamed by 1.8.0 —
on 1.8.0 `.instrument()` raises `ModuleNotFoundError` and you get no LLM spans
at all. Before raising the pin, check that import still resolves.

## Setup

```bash
uv sync
cp .env.example .env    # then fill in ANTHROPIC_API_KEY
```

Traces go to the `claude-compare-blogwriter` Arize project, not to
`ARIZE_PROJECT_NAME` — that var is usually already set in the shell for
something else, and `load_dotenv()` won't override a shell var. Override with
`BLOGWRITER_PROJECT_NAME`.

## Use

```bash
# Stage A -- generate the frozen briefs (once; then commit briefs/)
uv run blogwriter-research
uv run blogwriter-research --only how-llm-as-judge-works --refresh-briefs

# Stage B -- one post
uv run blogwriter --topic-slug how-llm-as-judge-works --model opus-5.5

# Stage B -- the matrix
uv run blogwriter-batch --models opus-5,opus-5.5 --repeats 3
```

Output lands in `output/<run_id>/<model_alias>/<slug>.r<repeat>.md` with
front-matter recording the full pinned surface, plus a `manifest.json` per
batch. The repeat index is in the filename so repeated samples of a cell never
overwrite each other.

Exit codes: `2` bad arguments, `3` brief integrity failure, `4` model
substitution, `5` refusal.

### The validity check

Run the same topic under both models and diff the front-matter. It should
differ **only** in model identity, word count, tokens and cost —
`prompt_sha256`, `brief_sha256` and `effort` must be identical.

```bash
diff <(sed -n '/^---$/,/^---$/p' output/RUN/opus-5/SLUG.r1.md) \
     <(sed -n '/^---$/,/^---$/p' output/RUN/opus-5.5/SLUG.r1.md)
```

## Notes on cost

The Messages API returns no cost, so it is computed from exact token counts
against the published list prices in `models.py` (checked 2026-09-22): Opus 5 at
$5/$25 per MTok with $0.50 cache reads, Opus 5.5 at $4/$20 with $0.20. Web
search is $10 per 1,000 searches. An unknown model reports `None` rather than a
fabricated number, and the field is named `cost_usd_estimated` throughout.

Token counts fold in the cache fields: `usage.input_tokens` counts only the
uncached portion, so the prompt total is `input + cache_read + cache_write`.

**Do not use Arize's built-in cost columns for this comparison.** Its
server-side pricing knows Opus 5 (it fills `llm.cost.total` with an
input/output breakdown on the LLM span) but has no rates for Opus 5.5, whose
LLM span comes back with cost absent. A comparison built on that field would
silently read one model as free. The `llm.cost.total` we set on the CHAIN span
is populated for both.

## The evaluator runs in AX

The scoring pipeline is Arize-native: **AX owns the evaluators**, the local
harness only generates and traces. See [AX_SETUP.md](AX_SETUP.md) for the
evaluator/task IDs, the exact `ax` commands, and the three gotchas that cost
real time (full attribute paths in filters, results in a top-level
`evaluations` array, one evaluator type per task).

```bash
uv run blogwriter-batch --models opus-5,opus-5.5 --repeats 3   # generate
ax tasks trigger-run <TASK_ID> --data-start-time ... --wait     # score in AX
uv run blogwriter-ax-report                                     # rank models
```

Two AX evaluators: **Claudism Density** (LLM judge, `gpt-5.6-luna`, graded
1–5) and **Em Dash Density** (deterministic code evaluator, em-dashes per 1000
words). Both score CHAIN spans, which covers posts *and* research briefs — so
the contamination baseline is scored by the same pass.

The report colours labels and scores as a warning scale: **red = obviously
Claude, green = doesn't read as Claude.** The AX evaluator is set to
`--direction MINIMIZE` to match, so its column colouring agrees with the
terminal. Colour is auto-detected — on for a TTY, off when piped or when
`NO_COLOR` is set, forced with `--color`.

### The local scorer (secondary)

`blogwriter-eval` predates the AX setup and reimplements scoring locally. It is
useful for fast iteration on pattern design without waiting on the eval index,
and its quote-verification is stricter than the AX judge's, but **AX is the
source of truth for results**.

```bash
uv run blogwriter-eval --run-id <run> --briefs      # both scorers
uv run blogwriter-eval --run-id <run> --no-judge    # free, regex only
uv run blogwriter-eval --run-id <run> --judge-passes 3
```

Two scorers, deliberately split:

- **Deterministic** (`claudisms.py`): fixed phrases plus structural counts
  (em-dashes, bold lead-in bullets, rule-of-three, short sentences). No model,
  no cost, no variance. `PATTERN_VERSION` is recorded with every score.
- **LLM judge** (`judge.py`): the voice constructions regex cannot see —
  antithesis pivots, concessive pivots, reveal setups, meta-writing,
  load-bearing idiom, punchy closers, hedge-then-assert.

Everything is normalised **per 1000 words**, because Opus 5.5 writes longer at
the same word target and raw counts would report "more claudisms" from length
alone.

### Why the judge runs on OpenAI

The thing being measured is Claude's own register, and a Claude judge carries a
self-preference risk on exactly that axis — MT-Bench put Claude-v1's
self-enhancement at ~25% higher win rate, the largest of the models tested, and
Anthropic's guidance is to grade with a different model than the generator.
Default judge: `gpt-5.6-luna`.

Because the judge is cross-family, the categories are defined *structurally*
with examples rather than asking it to "find the claudisms" — an outside model
must be told the patterns.

### Two properties that make the judge trustworthy

**Every instance carries a verbatim quote, and every quote is verified** by
string-matching it back into the source (whitespace and dash/quote variants
normalised). Unmatched instances are recorded as `unverified` rather than
silently dropped, so a rising count exposes a confabulating judge. In the first
real run this rejected **5 of 42** reported instances (~12%), all judge
paraphrases rather than quotes.

**The judge never counts or computes rates.** It returns instances; the harness
derives density from its own word count.

Note: these models **reject `temperature=0`** (only the default is accepted), so
the judge is irreducibly stochastic. That is why verified instance counts are
the primary signal, the 1–5 rating is secondary, and `--judge-passes` exists.

### Format vs voice — a calibration lesson

The judge originally included `bold_leadin_bullet` and `em_dash_aside`. Those
are formatting, they are counted exactly by the regex scorer, and asking the
judge for them **swamped the metric**: one telegraphic research brief returned
30 `bold_leadin_bullet` instances, pushing the contamination baseline
(16.7/1k) level with the posts (16.8 and 15.0) and destroying all
discriminative power. Removing them dropped the baseline to 1.14/1k and
separated the models. The judge covers voice; regex covers format.

### Known defect

The hand-written phrase list in `claudisms.py` matched **nothing** in any real
post — those 28 phrases were chosen from intuition, not derived from output.
They should be rebuilt empirically from a generated corpus (n-gram frequency
compared across models) once the full matrix exists. Until then, treat
`claude_leaning_per_1k` as unvalidated and rely on the structural metrics and
the judge.

## Topic set

`topics.yaml` holds **20 topics across two axes** — 5 genres, and 5 domains
(`ai` x8, plus `travel`, `cooking`, `games`, `books` x3 each). Both land in span
metadata, so `blogwriter-ax-report --by domain` shows whether the gap between
models holds across subject areas.
