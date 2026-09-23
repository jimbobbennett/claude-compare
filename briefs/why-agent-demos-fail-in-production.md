## Key facts
- WebArena's best GPT-4-based agent completed only 14.41% of realistic web tasks end-to-end, versus 78.24% for humans (https://arxiv.org/abs/2307.13854)
- τ-bench (Sierra) shows state-of-the-art function-calling agents such as gpt-4o succeed on fewer than 50% of tasks and are highly inconsistent across repeated trials of the *same* task (https://huggingface.co/papers/2406.12045)
- τ-bench introduced pass^k, a metric for reliability across k trials; consistency drops sharply as k increases even for agents with >60% single-run success (https://arxiv.org/pdf/2406.12045)
- TheAgentCompany (CMU + collaborators) simulates a software company with 175 long-horizon professional tasks; the best agent evaluated completed 30.3% autonomously, with failures concentrated in complex UI navigation and social/interactive work (https://www.alphaxiv.org/overview/2412.14161v2)
- Gartner predicts over 40% of agentic AI projects will be canceled by end of 2027, citing escalating costs, unclear business value and inadequate risk controls (https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)
- MIT Project NANDA's "The GenAI Divide: State of AI in Business 2025" found 95% of generative AI pilots produced no measurable P&L impact (https://virtualizationreview.com/articles/2025/08/19/mit-report-finds-most-ai-business-investments-fail-reveals-genai-divide.aspx)
- The MIT NANDA finding rests on 300+ deployment reviews, 52 executive interviews and 153 survey responses — a methodology worth flagging when citing the 95% number (https://www.legal.io/blog/5719519/MIT-Report-Finds-95-of-AI-Pilots-Fail-to-Deliver-ROI-Exposing-GenAI-Divide)
- The MAST paper (Berkeley) built the first Multi-Agent System Failure Taxonomy from 1,600+ annotated execution traces across 7 popular multi-agent frameworks, finding that MAS performance gains over single agents on popular benchmarks are often minimal (https://arxiv.org/abs/2503.13657)
- MAST taxonomy grounded in close reading of 150+ traces averaging over 15,000 lines each — failure modes include disobeying task specification, poor state management and flawed inter-agent coordination, not just model error (https://arxiv.org/pdf/2503.13657)
- "AI Agents That Matter" (Princeton) shows simple baseline agents match or beat complex SOTA agent architectures on benchmarks like HumanEval at a fraction of the cost — complexity in demos is often unearned (https://arxiv.org/pdf/2407.01502)
- Same paper: agent evaluations must be cost-controlled, because repeatedly calling a stochastic model raises benchmark accuracy without improving real capability (https://www.infoworld.com/article/2514447/researchers-reveal-flaws-in-ai-agent-benchmarking.html)
- Prompt injection ranks #1 on the OWASP Top 10 for LLM Applications 2025 and exploits models' inability to separate trusted instructions from untrusted data — a failure mode that only appears once agents touch real, adversarial inputs (https://www.vectra.ai/topics/prompt-injection)
- METR measures a model's "50% time horizon" — the human-task-length it can complete autonomously half the time — on a suite spanning tasks from 1 second to 16 hours; the metric exists precisely because short-horizon benchmarks saturate and hide long-horizon failure (https://metr.org/blog/2025-07-14-how-does-time-horizon-vary-across-domains/)
- Klarna, having announced in Feb 2024 that its OpenAI-built agent did the work of 700 agents and handled 2.3M conversations, reversed course roughly 18 months later and began rehiring human support staff over quality concerns (https://www.entrepreneur.com/business-news/klarna-ceo-reverses-course-by-hiring-more-humans-not-ai/491396)
- Anthropic frames context as a "critical but finite resource" that must be actively curated; system prompts, tools, examples, message history and retrieved data all compete for the same attention budget — a constraint demos rarely stress (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## Figures
- 14.41% — best GPT-4 agent success on WebArena vs 78.24% human (https://arxiv.org/abs/2307.13854)
- <50% — task success for SOTA function-calling agents on τ-bench (https://huggingface.co/papers/2406.12045)
- 175 — consequential, long-horizon tasks in TheAgentCompany (https://www.alphaxiv.org/overview/2412.14161v2)
- 30.3% — best agent's autonomous completion rate on TheAgentCompany (https://www.alphaxiv.org/overview/2412.14161v2)
- 6.9% — Llama 3.3 70B success rate on TheAgentCompany (https://arxiv.org/pdf/2412.14161v1)
- 40%+ — share of agentic AI projects Gartner expects to be canceled by end of 2027 (https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)
- 3,400+ — organizations polled for the Gartner agentic AI prediction (https://martech.org/gartner-40-of-agentic-ai-projects-will-fail-making-humans-indispensable/)
- 95% — GenAI pilots with no measurable P&L impact, MIT NANDA, July 2025 (https://virtualizationreview.com/articles/2025/08/19/mit-report-finds-most-ai-business-investments-fail-reveals-genai-divide.aspx)
- $30–40B — enterprise GenAI spend against that 95% figure (https://virtualizationreview.com/articles/2025/08/19/mit-report-finds-most-ai-business-investments-fail-reveals-genai-divide.aspx)
- 1,600+ — annotated multi-agent failure traces in MAST-Data, across 7 frameworks (https://arxiv.org/abs/2503.13657)
- ~15,000 lines — average length of a single MAS execution trace analysed for MAST (https://arxiv.org/pdf/2503.13657)
- 11.8% — share of MAST failures classed as "Disobey Task Specification" (https://www.alphaxiv.org/abs/2503.13657)
- $4 — per-run cost cap SWE-Agent authors applied, equal to hundreds of thousands of tokens (https://arxiv.org/pdf/2407.01502)
- ~7 months — doubling time of METR's 50%-task-completion time horizon over the past 6 years, possibly ~4 months in 2024 (https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/, https://metr.org/blog/2025-07-14-how-does-time-horizon-vary-across-domains/)
- 2.3M conversations / 11 min → under 2 min resolution time / ~$40M projected 2024 saving — Klarna's original agent claims, prior to reversal (https://asisteclick.com/en/blog/klarna-error-ia-customer-service-leccion/)
- 70%–95% — reported range for agent failure rates in real-world settings; secondary aggregation, verify before use (https://www.fiddler.ai/blog/ai-agent-failure-rate)

## Quotes
- Anushree Verma, Senior Director Analyst, Gartner: "Most agentic AI projects right now are early stage experiments or proof of concepts that are mostly driven by hype and are often misapplied" (https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)
- MIT Project NANDA report authors: "The outcomes are so starkly divided across both buyers... and builders... that we call it the GenAI Divide" (https://virtualizationreview.com/articles/2025/08/19/mit-report-finds-most-ai-business-investments-fail-reveals-genai-divide.aspx)
- Clare Nordstrom, Klarna spokesperson: "AI gives us speed. Talent gives us empathy." (https://news.outsourceaccelerator.com/klarna-reintroduces-human-support/)
- MAST authors, UC Berkeley: "Despite enthusiasm for Multi-Agent LLM Systems (MAS), their performance gains on popular benchmarks are often minimal." (https://arxiv.org/abs/2503.13657)
- Anthropic engineering: context is "a critical but finite resource for AI agents" (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Princeton "AI Agents That Matter" authors, via InfoWorld: the field's "North Star" is assistants that "actually work" on complex tasks (https://www.infoworld.com/article/2514447/researchers-reveal-flaws-in-ai-agent-benchmarking.html)

## Suggested sections
- Demo vs. distribution — single happy-path run vs. repeated runs, pass^k, variance as the real metric
- Benchmark inflation — cost-uncontrolled evals, overfitting to held-in tasks, simple baselines beating complex scaffolds
- Compounding error over long horizons — multi-step chains, multiplied per-step success rates, METR time-horizon framing
- Multi-agent coordination failures — MAST taxonomy categories: spec violation, inter-agent misalignment, verification gaps
- The environment problem — real APIs, stale state, partial failures, side effects, duplicate writes, no undo
- Adversarial and security surface — prompt injection, tool permissions, untrusted data in context, OWASP ranking
- Organisational failure modes — unclear ROI, missing evals and tracing, no human-in-loop tier, project cancellation data (Gartner, MIT NANDA, Klarna)

## Terms to define
- Agentic AI — model given tools, memory and a loop, acting over multiple steps toward a goal rather than returning one response
- pass^k — probability an agent solves the same task successfully in all k independent trials; a consistency metric, not an average
- Scaffold / harness — the code around the model (loop, tool routing, retries, context assembly) that turns a model into an agent
- Context engineering — deliberate curation of what tokens occupy the finite context window: prompts, tool defs, history, retrieved data
- Context rot — degradation of agent behaviour as the window fills with stale or irrelevant history
- Long-horizon task — task requiring many dependent steps, where per-step error compounds multiplicatively
- 50% time horizon (METR) — human-task duration an agent completes autonomously with 50% probability
- Prompt injection — malicious instructions smuggled into data the agent reads, causing it to override its original instructions
- Indirect prompt injection — injection delivered via third-party content (web page, email, file) rather than direct user input
- Span-level tracing — per-step logging of agent actions and tool calls, used to diagnose retry loops, runaway cost, hallucinated steps
- Cost-controlled evaluation — benchmarking that reports accuracy against dollar/token spend, preventing brute-force retry wins
- Tool calling / function calling — model emitting structured calls to external APIs as its action mechanism
- MAS — multi-agent system; several LLM agents with distinct roles passing work between each other
- Human-in-the-loop / co-pilot design — architecture requiring human approval before high-stakes or irreversible actions
