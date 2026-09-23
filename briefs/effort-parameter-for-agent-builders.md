## Key facts
- Anthropic's `effort` parameter controls how many tokens Claude spends on a response, trading response thoroughness against token efficiency (https://platform.claude.com/docs/en/build-with-claude/effort)
- Effort was introduced with Claude Opus 4.5 as a developer-facing dial on the Claude API (https://www.anthropic.com/news/claude-opus-4-5)
- Effort applies to *all* output tokens, not just thinking tokens, so it works whether or not thinking is enabled (https://platform.claude.com/docs/en/build-with-claude/effort)
- Effort is a behavioural signal, not a hard token budget — at low effort Claude still thinks on hard problems, just less (https://platform.claude.com/docs/en/build-with-claude/effort)
- Lower effort changes agent behaviour specifically: fewer tool calls, multiple operations combined into one call, less preamble, terser confirmations (https://platform.claude.com/docs/en/build-with-claude/effort)
- Higher effort produces more tool calls, plan-before-action explanations, detailed change summaries, more code comments (https://platform.claude.com/docs/en/build-with-claude/effort)
- Setting effort to the model default produces behaviour identical to omitting the parameter (https://platform.claude.com/docs/en/build-with-claude/effort)
- `max_tokens` remains the hard ceiling on total output (thinking + response text); docs recommend a large `max_tokens` at high/xhigh/max effort, ~64k as a starting default (https://platform.claude.com/docs/en/build-with-claude/effort)
- On Claude 4.7 and later, `budget_tokens` returns a 400 error; lowering effort or setting `max_tokens` is the replacement control (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- Per-message `output_config` allows changing effort mid-conversation while preserving the prompt cache (https://platform.claude.com/docs/en/build-with-claude/effort)
- OpenAI's equivalent is `reasoning.effort` (Responses) / `reasoning_effort` (Chat Completions); supported values are model-dependent and can include none, minimal, low, medium, high, xhigh, max (https://developers.openai.com/api/docs/guides/reasoning)
- Defaults differ across OpenAI models — GPT-5.1 defaults to `none`, meaning upgrading code may silently stop reasoning unless effort is passed explicitly (https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning)
- Google's equivalent is `thinking_level` (minimal/low/medium/high), which replaces the older numeric `thinking_budget`; `max_output_tokens` acts as an infrastructure-enforced hard cutoff that does not change allocation (https://ai.google.dev/gemini-api/docs/thinking, https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5)
- Effort defaults are a product decision with real user impact: Anthropic dropped Claude Code's default from high to medium on 4 March, called it the wrong tradeoff, and reverted on 7 April (https://www.anthropic.com/engineering/april-23-postmortem)
- In Claude Code, effort is set via `/effort` or `--effort`; low/medium/high persist across sessions, max resets at session end (https://kentgigger.com/posts/claude-code-effort-parameter)
- Subagent effort control lags the main loop — Claude Code exposes effort as static frontmatter on agent definitions but not as a per-invocation Agent/Task tool parameter (https://github.com/anthropics/claude-code/issues/72596)

## Figures
- Opus 4.5 at medium effort matches Sonnet 4.5's best SWE-bench Verified score using 76% fewer output tokens (https://www.anthropic.com/news/claude-opus-4-5)
- At highest effort, Opus 4.5 exceeds Sonnet 4.5 by 4.3 percentage points while using 48% fewer tokens (https://www.anthropic.com/news/claude-opus-4-5)
- Opus 4.5 SWE-bench Verified: 80.9%, vs GPT-5.1-Codex-Max 77.9%, Sonnet 4.5 77.2%, Gemini 3 Pro 76.2% (https://trilogyai.substack.com/p/news-brief-anthropic-releases-claude)
- Opus 4.5 pricing: $5 / $25 per million input/output tokens (https://www.anthropic.com/news/claude-opus-4-5)
- Prior-generation Opus pricing was $15 / $75 per million tokens (https://www.eesel.ai/blog/claude-opus-45-pricing)
- Claude Opus 5.5 is the first Anthropic model defaulting to medium effort; matched Opus 5 at high effort while using 20–25% fewer output tokens in testing (https://www.anthropic.com/claude/opus)
- Opus 5.5 pricing: $4 / $20 per million tokens; cache reads $0.20 per million, 60% below Opus 5 (https://www.anthropic.com/claude/opus)
- Anthropic effort enum: five levels, low through max, API default high (https://platform.claude.com/docs/en/build-with-claude/effort)
- Full accepted value list observed on Anthropic-compatible endpoints: none, minimal, low, medium, high, xhigh, max — anything else returns HTTP 400 (https://github.com/router-for-me/CLIProxyAPI/issues/4796)
- Claude Code default-effort downgrade window: 4 March to 7 April, affecting Sonnet 4.6 and Opus 4.6 (https://www.anthropic.com/engineering/april-23-postmortem)
- Opus 4.5: 200k context window, 64k max output, May 2025 knowledge cutoff (https://trilogyai.substack.com/p/news-brief-anthropic-releases-claude)
- Claude Opus 4.8 defaults to high effort across all surfaces including Claude Code and the Messages API (https://platform.claude.com/docs/en/release-notes/overview)
- Per-invocation subagent effort documented as unavailable as of Claude Code v2.1.197; frontmatter `effort` available since ~v2.1.196 (https://github.com/anthropics/claude-code/issues/72596)

## Quotes
- Anthropic, on the effort dial: "With our new effort parameter on the Claude API, you can decide to minimize time and spend or maximize capability." (https://www.anthropic.com/news/claude-opus-4-5)
- Anthropic engineering, on the Claude Code default change: "This was the wrong tradeoff. We reverted this change on April 7 after users told us they'd prefer to default to higher intelligence and opt into lower effort for simple tasks." (https://www.anthropic.com/engineering/april-23-postmortem)
- Anthropic engineering, on the underlying relationship: "In general, the longer the model thinks, the better the output." (https://www.anthropic.com/engineering/april-23-postmortem)
- Anthropic engineering, on why the regression was hard to catch: "neither our internal usage nor evals initially reproduced the issues identified" (https://www.anthropic.com/engineering/april-23-postmortem)
- Anthropic docs, on the two parameters: the `thinking` parameter controls whether Claude thinks in thinking blocks before answering; the `effort` parameter controls how much work Claude puts into the whole response (https://platform.claude.com/docs/en/build-with-claude/effort)
- OpenAI, on top-tier effort, as quoted by a secondary source: use it "only... when your evals show a clear benefit that justifies the extra latency and cost." (https://syntackle.com/blog/why-some-ai-models-work-great-on-low-effort-and-others-don-t/)
- Mario Rodriguez, GitHub CPO, on Opus 4.5: it "surpasses internal coding benchmarks while cutting token usage in half." (https://www.implicator.ai/claude-opus-4-5-everything-you-need-to-know-about-anthropics-new-flagship/)
- JetBrains Junie team, via Anthropic: "The effort parameter is brilliant. Claude Opus 4.5 feels dynamic rather than overthinking, and at lower effort delivers the same quality we need while being dramatically more efficient." (https://www.anthropic.com/news/claude-opus-4-5)

## Suggested sections
- **What the knob actually does** — token spend across the whole response, not a budget cap; behavioural signal vs hard limit
- **Effort vs thinking vs max_tokens** — three separate controls, which one is the ceiling, deprecation of `budget_tokens`
- **Agent-loop consequences** — tool-call count, preamble, batching, summary verbosity; why this matters more in a loop than in one-shot chat
- **Cross-vendor mapping** — Anthropic `effort`, OpenAI `reasoning_effort`, Google `thinking_level`; different enums, different defaults, migration traps
- **Defaults are a product decision** — Claude Code March–April default downgrade and revert; evals missing user-perceived quality
- **Choosing a level** — task-class split (planning/debugging vs mechanical edits), per-message and per-subagent variation, prompt-cache preservation
- **Cost and latency modelling** — pricing deltas, cache reads in long-running agents, measuring on your own evals before stepping down

## Terms to define
- **Effort parameter** — discrete enum controlling how many output tokens a model spends per response
- **Reasoning / thinking tokens** — billed output tokens the model generates internally before its visible answer
- **Adaptive thinking** — mode where the model decides per turn whether and how deeply to think, rather than following a fixed budget
- **`budget_tokens`** — deprecated numeric cap on thinking length, now rejected on newer Claude models
- **`max_tokens` / `max_output_tokens`** — hard ceiling on total output including thinking; unlike effort, infrastructure-enforced
- **Test-time compute** — inference-time reasoning spend, as distinct from training compute
- **Prompt caching / cache reads** — reuse of prior input tokens at reduced price; a large share of long-running agent cost
- **Agent loop** — repeated model→tool→model cycle; multiplies any per-call effort setting
- **Subagent fan-out** — orchestrator spawning parallel child agents, each with its own model and effort settings
- **SWE-bench Verified** — human-validated subset of a software-engineering benchmark used as the standard coding-agent score
- **Thought signatures** — cryptographic markers required to carry reasoning across turns in some APIs
