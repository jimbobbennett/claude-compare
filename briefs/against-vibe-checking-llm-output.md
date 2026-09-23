## Key facts
- "Vibe check" / "vibe eval" = manual, non-reproducible, subjective spot-checking of model outputs; described as failing because it is "probabilistically blind" — a single sampled output says nothing about the distribution of outputs (https://aishwaryasrinivasan.substack.com/p/ai-evals-explained-for-builders)
- Standard software practice (unit tests, integration tests, deterministic assertions) is abandoned for subjective human judgement when teams ship LLM features; cited as a primary reason enterprise AI projects fail to scale (https://towardsdatascience.com/stop-evaluating-llms-with-vibe-checks/)
- "Criteria drift": users need criteria to grade outputs, but grading outputs is what generates the criteria — a documented catch-22 making it impossible to fully specify evaluation criteria before looking at outputs (https://arxiv.org/pdf/2404.12272)
- Same study: participants who graded first still revised criteria as they went, and went back to change earlier grades — i.e. ad-hoc human judgement is not stable over a session (https://dl.acm.org/doi/fullHtml/10.1145/3654777.3676450)
- LLM-generated evaluators inherit the failure modes of the models they evaluate, so swapping vibes for an LLM judge does not remove the need for human validation (https://dl.acm.org/doi/fullHtml/10.1145/3654777.3676450)
- Position bias in LLM judges is systematic, not random; varies by judge and task, and is strongly affected by the quality gap between the two candidate solutions (https://aclanthology.org/2025.ijcnlp-long.18/)
- Verbosity bias: judges systematically prefer longer responses even when extra content is irrelevant or repetitive (https://arxiv.org/pdf/2606.19544)
- Self-preference bias: GPT-4 as judge rates its own outputs higher; root cause traced to perplexity — LLM judges over-reward text that is familiar/predictable to them, far more strongly than humans do (https://arxiv.org/pdf/2410.21819)
- Human preference data has the same problem: controlling Chatbot Arena for answer length and markdown (header, bold, list counts) visibly changed model rankings (https://www.lmsys.org/blog/2024-08-28-style-control/)
- Under style control, GPT-4o-mini and Grok-2-mini dropped below most frontier models while Claude 3.5 Sonnet, Opus and Llama-3.1-405B rose substantially — i.e. aggregate vibes were largely measuring formatting (https://oldblog.lmarena.ai/blog/2024/style-control/)
- Crowd-scale preference leaderboards are gameable: undisclosed private testing let selected providers test many variants and publish only the best checkpoint, biasing scores through selective disclosure (https://arxiv.org/abs/2504.20879)
- Arena data access asymmetry produces overfitting to arena-specific dynamics rather than general model quality (https://arxiv.org/html/2504.20879v2)
- Cheap deterministic checks exist as an alternative first line of defence: regex/string matching, JSON schema validation, code-compiles checks, embedding similarity to gold references (https://aishwaryasrinivasan.substack.com/p/ai-evals-explained-for-builders)
- Mitigations for judge bias are known and mechanical: swap augmentation (score both orders, count disagreement as tie), calibration prompting, ensemble judges, forced chain-of-thought before verdict (https://arxiv.org/pdf/2606.24937)

## Figures
- 150,000+ evaluation instances in the systematic position-bias study (https://aclanthology.org/2025.ijcnlp-long.18/)
- 15 LLM judges, 22 tasks, ~40 solution-generating models across MTBench and DevBench in that study (https://aclanthology.org/2025.ijcnlp-long.18/)
- Position flip rates across judge models: 25%–50% of items change verdict when response order is swapped (https://arxiv.org/pdf/2606.19544)
- Position-swap debiasing raises within-judge consistency from roughly 60% to 85% (https://arxiv.org/pdf/2606.19544)
- Position bias magnitude reported as large as 10–15 percentage points (https://arxiv.org/pdf/2606.24937)
- Leaderboard Illusion audit scope: 2M battles, 42 providers, 243 models, January 2024 – April 2025 (https://arxiv.org/html/2504.20879v2)
- 27 private LLM variants tested by one provider (Meta) before the Llama-4 release (https://arxiv.org/abs/2504.20879)
- Estimated share of all arena data: 20.4% to OpenAI, 19.2% to Google; 83 open-weight models combined received an estimated 29.7% (https://arxiv.org/abs/2504.20879)
- Proprietary models' share of battle volume ranged 54.3%–70.1%, Jan 2024–Mar 2025 (https://arxiv.org/html/2504.20879v2)
- Access to arena data yielded relative performance gains of up to 112% on ArenaHard, on conservative estimates (https://neurips.cc/virtual/2025/poster/121845)

## Quotes
- "it is impossible to completely determine evaluation criteria prior to human judging of LLM outputs" — Shankar et al., UC Berkeley, "Who Validates the Validators?" (https://arxiv.org/pdf/2404.12272)
- "to grade outputs, people need to externalize and define their evaluation criteria; however, the process of grading outputs helps them to define that very criteria" — Shankar et al., UC Berkeley (https://arxiv.org/pdf/2404.12272)
- "If you approve that deployment based on a 'vibe check,' you are flying blind." — Towards Data Science (https://towardsdatascience.com/stop-evaluating-llms-with-vibe-checks/)
- "It fails because it is probabilistically blind." — Aishwarya Srinivasan, on vibe-eval (https://aishwaryasrinivasan.substack.com/p/ai-evals-explained-for-builders)
- "these dynamics result in overfitting to Arena-specific dynamics rather than general model quality" — Singh et al., Cohere Labs et al., "The Leaderboard Illusion" (https://arxiv.org/abs/2504.20879)
- "it's not just what you say, but how you say it" — LMSYS/LM Arena, on style effects in human preference (https://www.lmsys.org/blog/2024-08-28-style-control/)

## Suggested sections
- What vibe-checking actually is — spot-checking a handful of outputs, no fixed dataset, no record, criteria in the reader's head
- Why single samples lie — output distributions, sampling variance, the gap between "one good answer" and "a reliable rate"
- Criteria drift — why the grader's standard moves while they grade; implication for before/after comparisons
- Vibes don't scale to a judge — biases you import when you promote your gut to an LLM judge: position, verbosity, self-preference/perplexity
- Aggregated vibes are still vibes — arena-style preference data, style vs substance, gaming and selective disclosure
- What to replace it with — tiered checks: deterministic assertions, error-analysis-derived labelled set, aligned judge, online A/B
- When vibe-checking is legitimately fine — earliest prototyping, prompt bring-up, generating the hypotheses that later become assertions

## Terms to define
- **Vibe check / vibe eval** — informal manual inspection of a few outputs, with no fixed test set or recorded criteria
- **LLM-as-a-judge** — using a strong model to score or rank another model's outputs against a rubric
- **Criteria drift** — evaluation criteria changing as a result of looking at the outputs being evaluated
- **Position bias** — judge preferring a candidate because of where it appears in the prompt
- **Position flip rate** — share of items whose verdict changes when candidate order is swapped
- **Swap augmentation** — scoring each pair in both orders and treating disagreement as a tie
- **Verbosity / length bias** — systematic preference for longer answers independent of content
- **Self-preference bias** — judge rating its own generations higher; correlates with low perplexity text
- **Perplexity** — measure of how predictable a text is to a given model
- **Style control** — regression adjustment removing length and markdown effects from preference rankings
- **Bradley-Terry model** — the pairwise-comparison statistical model behind Elo-style arena scores
- **Error analysis** — reading and open-coding failed traces to derive failure taxonomies and eval criteria
- **Assertion / code-based eval** — deterministic pass-fail check (regex, JSON schema, compile, execution)
- **Overfitting to the benchmark** — tuning to a leaderboard's distribution rather than to general capability
