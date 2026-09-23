## Key facts
- GEPA (Genetic-Pareto) is a prompt optimizer that samples system-level trajectories — reasoning, tool calls, outputs — and reflects on them in natural language to propose prompt edits (https://arxiv.org/abs/2507.19457)
- GEPA authors span UC Berkeley, Stanford, Notre Dame, Databricks; lead author Lakshya A Agrawal, senior authors include Matei Zaharia, Ion Stoica, Christopher Potts, Omar Khattab (https://arxiv.org/abs/2507.19457)
- GEPA paper accepted at ICLR 2026 as an oral (https://arxiv.org/pdf/2507.19457)
- GEPA maintains a Pareto frontier of candidate prompts rather than a single best candidate, and can also serve as an inference-time search strategy for code optimization (https://arxiv.org/abs/2507.19457)
- MIPROv2 (DSPy) optimizes instructions and few-shot demonstrations jointly by bootstrapping example candidates, proposing grounded instructions, and searching combinations with Bayesian optimization (https://dspy.ai/api/optimizers/MIPROv2/)
- MIPROv2 requires the optuna package for its Bayesian optimization search (https://deepeval.com/docs/prompt-optimization-miprov2)
- GEPA's trace-level optimization requires the entire application — LLM calls, tools, retrieval, control flow — to be expressed inside DSPy abstractions, because it depends on DSPy-generated execution traces (https://arize.com/blog/gepa-vs-prompt-learning-benchmarking-different-prompt-optimization-approaches/)
- Arize's Prompt Learning was introduced 18 July 2025; DSPy released GEPA roughly a week later (https://arize.com/blog/gepa-vs-prompt-learning-benchmarking-different-prompt-optimization-approaches/)
- Prompt Learning extends meta-prompting (Suzgun & Kalai, 2024) by replacing scalar pass/fail feedback with textual feedback: annotations, rule reminders, explanations (https://github.com/Arize-ai/prompt-learning)
- ACE (Agentic Context Engineering) treats context as an evolving "playbook" updated by a generation / reflection / curation loop with incremental delta updates (https://arxiv.org/abs/2510.04618)
- ACE names two failure modes of naive iterative rewriting: brevity bias (domain insight dropped for concise summaries) and context collapse (detail eroded over successive rewrites) (https://arxiv.org/abs/2510.04618)
- ACE improves AppWorld accuracy using execution feedback alone, without ground-truth labels (https://arxiv.org/html/2510.04618)
- OpenAI shipped automated prompt optimization plus trace grading and datasets as part of AgentKit/Evals at DevDay on 6 October 2025 (https://x.com/OpenAI/status/1975328203058389153)
- Anthropic Console ships a prompt generator and a prompt improver, the latter applying chain-of-thought restructuring to an existing prompt template (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-tools)
- LangSmith's documented cold-start path is to capture production traces first, then sample interesting or problematic runs into an evaluation dataset (https://www.langchain.com/langsmith/evaluation)
- OpenTelemetry GenAI semantic conventions define spans, metrics and events for model calls, tool execution, retrieval, memory and full agent runs; prompt/completion capture is optional per instrumentation config (https://opentelemetry-semantic-conventions.hexdocs.pm/1.27.0/gen-ai-spans.html)

## Figures
- GEPA beats GRPO by 10% on average, up to 20%, while using up to 35× fewer rollouts (https://arxiv.org/html/2507.19457v1)
- GRPO baseline in the GEPA comparison used 24,000 rollouts (https://arxiv.org/html/2507.19457v1)
- GEPA exceeds MIPROv2 on all benchmarks and models for +13% aggregate gain, versus MIPROv2's +5.6% (https://arxiv.org/pdf/2507.19457)
- GEPA average gain of +6% across six tasks versus GRPO (https://arxiv.org/pdf/2507.19457)
- GEPA +12% accuracy over MIPROv2 on AIME-2025 (https://arxiv.org/abs/2507.19457)
- GEPA-produced prompts reported as up to 9.2× shorter than MIPROv2's (https://www.morphllm.com/gepa-prompt-optimization)
- All GEPA optimization runs used minibatch size 3 (https://arxiv.org/html/2507.19457v1)
- ACE: +10.6% average gain on agent tasks, +8.6% on domain-specific benchmarks (https://github.com/ace-agent/ace/blob/main/README.md)
- ACE: up to +17.1% accuracy on AppWorld (https://arxiv.org/html/2510.04618)
- ACE: 86.9% lower adaptation latency on average versus existing adaptive methods (https://arxiv.org/html/2510.04618v1)
- ACE with DeepSeek-V3.1 matches IBM CUGA (GPT-4.1) on the AppWorld leaderboard average and surpasses it on the test-challenge split (https://arxiv.org/html/2510.04618v1)
- OPRO-optimized prompts beat human-designed prompts by up to 8% on GSM8K and up to 50% on Big-Bench Hard (https://arxiv.org/abs/2309.03409)
- OPRO published as ICLR 2024 poster; arXiv 2309.03409 (https://iclr.cc/virtual/2024/poster/19209)
- Phoenix, the open-source observability/evals platform used as the trace source for Prompt Learning, cited at over 7k GitHub stars (https://arize.com/blog/gepa-vs-prompt-learning-benchmarking-different-prompt-optimization-approaches/)
- LangSmith hosted instances store data in GCP us-central-1 or europe-west4; self-hosting available on Kubernetes in AWS, GCP, Azure (https://www.langchain.com/langsmith/evaluation)
- OpenAI Evals positioned to run evaluations on 2 million weekly users directly from the platform (https://cybernews.com/ai-news/openai-dev-day-2025-altman-keynote-api-announcenents/)

## Quotes
- "Instead of manually refining prompts through intuition, can we optimize them automatically using feedback from real application traces?" — Arize AI blog (https://arize.com/blog/gepa-vs-prompt-learning-benchmarking-different-prompt-optimization-approaches/)
- "the interpretable nature of language often provides a much richer learning medium for LLMs, compared to policy gradients" — Agrawal et al., GEPA (https://arxiv.org/abs/2507.19457)
- "context collapse, where iterative rewriting erodes details over time" — Agentic Context Engineering authors (https://arxiv.org/abs/2510.04618)
- "Start by capturing production traces with LangSmith, then sample interesting or problematic runs into a dataset." — LangSmith docs, LangChain (https://www.langchain.com/langsmith/evaluation)
- "Useful production analysis depends on instrumenting the application and sending the relevant traces, attributes, and feedback." — Arize AI (https://arize.com/blog/best-prompt-testing-optimization-tools/)

## Suggested sections
- Trace capture and schema — what a usable trace contains; OpenTelemetry gen_ai spans; optional prompt/completion payload capture
- From traces to a training set — sampling problematic runs, annotation, feedback columns, label-free execution feedback
- Optimizer families — instruction search (OPRO), joint instruction + demo search (MIPROv2), reflective/evolutionary (GEPA), playbook accumulation (ACE)
- Feedback signal design — scalar reward vs textual feedback; LLM-as-judge; human annotation queues
- Failure modes — brevity bias, context collapse, overfitting to sampled traces, prompt bloat, judge miscalibration
- Deployment loop — prompt versioning, held-out eval before promotion, human-in-the-loop gating, rollback, continuous re-optimization
- Cost and constraints — rollout budgets vs RL, framework lock-in (DSPy requirement), trace storage volume, PII in stored prompts

## Terms to define
- Trace — recorded tree of spans for one application run: LLM calls, tool calls, retrieval steps
- Span — a single timed operation inside a trace, with attributes
- Rollout — one full execution of the system used to produce a score during optimization
- GRPO — Group Relative Policy Optimization; RL method that updates model weights from sparse scalar rewards
- Pareto frontier — set of candidates none of which is beaten on every evaluation instance
- Bootstrapped demonstrations — few-shot examples generated by running the program and keeping successful traces
- Meta-prompt — prompt given to the optimizer LLM instructing it how to rewrite the target prompt
- Reflection — optimizer step where an LLM reads a failing trace and writes a natural-language diagnosis
- Brevity bias — tendency of iterative summarization to discard domain-specific detail
- Context collapse — degradation of an accumulated context after repeated end-to-end LLM rewrites
- Teleprompter / optimizer (DSPy) — component that compiles a program by searching over prompts and demos
- LLM-as-judge — using a model to score outputs in place of human labels
- Trace grading — assigning scores to recorded production runs, used as the optimizer's objective
- Online vs offline adaptation — updating context from live traffic vs from a fixed collected dataset
