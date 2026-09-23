## Key facts
- LLM-as-a-judge = using a strong LLM, prompted with a rubric, to score or compare outputs of other models in place of human raters (https://arxiv.org/abs/2306.05685)
- Three canonical judging modes: pairwise comparison (pick A/B/tie), single-answer grading (absolute score), and reference-guided grading (score against a gold answer) (https://arxiv.org/pdf/2306.05685)
- GPT-4 as judge reached over 80% agreement with human expert preferences on MT-Bench, roughly equal to human–human agreement (https://arxiv.org/abs/2306.05685)
- Documented failure modes: position bias, verbosity bias, self-enhancement bias, and weak math/reasoning grading ability (https://arxiv.org/abs/2306.05685)
- Position bias in judges is not random noise: repetition stability is high (most judges >0.85), so inconsistency comes from ordering itself, not sampling variance (https://arxiv.org/abs/2406.07791)
- Position bias is weakly related to prompt length but strongly driven by the quality gap between the two candidate responses — closer pairs flip more (https://arxiv.org/abs/2406.07791)
- G-Eval implements judging as a two-stage pattern: LLM generates chain-of-thought evaluation steps from the criteria, then fills a scoring form; final score is a probability-weighted sum of output scores (https://arxiv.org/abs/2303.16634)
- A panel of three small, cheap judges from different providers (command-r, gpt-3.5-turbo, Claude Haiku) correlated better with humans than a single GPT-4 judge (https://arxiv.org/abs/2404.18796)
- Purpose-built open judge models exist: Prometheus (13B) trained on GPT-4-generated feedback, scored on customized rubrics; Prometheus 2 adds pairwise/relative grading (https://arxiv.org/abs/2310.08491, https://arxiv.org/pdf/2405.01535)
- JudgeBench shows judge agreement collapses on objectively-checkable hard tasks: many strong models land near 50% random guessing (https://arxiv.org/abs/2410.12784)
- Reasoning-heavy judges do better on hard benchmarks — test-time-compute models topped JudgeBench at up to ~80.9% accuracy (https://arxiv.org/pdf/2410.12784)
- Vendor guidance is to constrain the judge's output space: binary correct/incorrect or a 1–5 Likert score, not free-form qualitative text (https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)
- Vendor guidance is also to use a different model as judge than the model that generated the output (https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)
- Production graders return continuous grades in a 0–1 range, with partial credit preferred over binary in some cases; string-check, similarity, model-scoring and code graders are separate grader types (https://developers.openai.com/api/docs/guides/graders)
- Judge validation practice: measure agreement with human labels using chance-adjusted statistics (Cohen's kappa for two categorical raters, weighted kappa for ordered labels, Fleiss' kappa / Krippendorff's alpha for more raters) alongside raw percent agreement (https://arize.com/blog/measuring-human-llm-judge-alignment/)

## Figures
- MT-Bench: 80 multi-turn open-ended questions across 8 categories (writing, roleplay, extraction, reasoning, math, coding, STEM, humanities/social science) (https://www.emergentmind.com/papers/2306.05685)
- 3,000 expert votes collected for MT-Bench; ~30,000 conversations with preference annotations from Chatbot Arena (https://arxiv.org/abs/2306.05685)
- >80% GPT-4/human agreement, matching inter-human agreement level (https://arxiv.org/abs/2306.05685)
- G-Eval with GPT-4 backbone: Spearman correlation 0.514 with humans on summarization (SummEval), above all prior methods (https://arxiv.org/abs/2303.16634)
- Prometheus (13B): Pearson 0.897 with human evaluators across 45 customized rubrics, vs 0.88 for GPT-4 (https://arxiv.org/abs/2310.08491)
- Prometheus training data (Feedback Collection): 1K fine-grained rubrics, 20K instructions, 100K responses + feedback (https://arxiv.org/abs/2310.08491)
- Prometheus 2: Pearson 0.6–0.7 with GPT-4-1106 on 5-point Likert direct assessment across VicunaBench, MT-Bench, FLASK (https://arxiv.org/pdf/2405.01535)
- PoLL panel of 3 models: 7–8x cheaper than a single GPT-4 judge, depending on input:output token ratio (https://arxiv.org/abs/2404.18796)
- GPT-4o with a vanilla AlpacaFarm-style judge prompt on JudgeBench: 44.2% knowledge, 48.0% reasoning, 66.1% math, 61.9% coding, 50.9% overall (https://arxiv.org/pdf/2410.12784)
- Position bias study scale: 15 LLM judges, MTBench + DevBench, 22 tasks, ~40 solution-generating models, >150,000 evaluation instances (https://arxiv.org/abs/2406.07791)
- "Justice or Prejudice?" catalogues 12 key potential biases in LLM judges via the CALM quantification framework (https://arxiv.org/abs/2410.02736)
- Alignment sample sizes: ~100 examples ≈ ±10pp margin of error at 95% confidence; ~400 examples ≈ ±5pp; 30–50 examples adequate for rubric iteration (https://arize.com/blog/measuring-human-llm-judge-alignment/)
- Kappa CI sizing: kappa ≈0.6 needs ~200 paired labels for a 95% CI no wider than 0.10; kappa ≈0.4 needs ~400 (https://oneuptime.com/blog/post/2026-08-31-calibrate-llm-judge-cohens-kappa/view)

## Quotes
- "LLM-as-a-judge is a scalable and explainable way to approximate human preferences, which are otherwise very expensive to obtain." — Zheng et al., LMSYS / UC Berkeley (https://arxiv.org/abs/2306.05685)
- "Strong LLM judges like GPT-4 can match both controlled and crowdsourced human preferences well, achieving over 80% agreement, the same level of agreement between humans." — Zheng et al., LMSYS / UC Berkeley (https://arxiv.org/abs/2306.05685)
- "Generally best practice to use a different model to evaluate than the model used to generate the evaluated output" — Anthropic, Claude platform documentation (https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)
- "Structure questions to allow for automated grading (for example, multiple-choice, string match, code-graded, LLM-graded)." — Anthropic, Claude platform documentation (https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)
- "No single metric proves an LLM judge is trustworthy... each of those is a separate question, and each calls for a different kind of measurement." — Arize AI (https://arize.com/blog/measuring-human-llm-judge-alignment/)
- "There remains room for improvement in the reliability of LLM-as-a-Judge." — Ye et al., "Justice or Prejudice?" (https://arxiv.org/abs/2410.02736)
- "Many strong models, including GPT-4o, performing near random guessing" on JudgeBench — Tan et al., ICLR 2025 (https://arxiv.org/pdf/2410.12784)

## Suggested sections
- **Mechanics** — the judge call itself: prompt template, rubric, criteria, output format, score parsing, logprob weighting
- **Judging modes** — pairwise vs single-answer grading vs reference-guided; when each is appropriate; tie handling
- **Bias catalogue** — position, verbosity, self-enhancement, self-preference; how each is measured (position consistency, preference fairness, repetition stability)
- **Mitigations** — order swapping/averaging, chain-of-thought before verdict, few-shot anchoring, reference answers, judge panels/juries, identity masking
- **Validation against humans** — labeled gold set, percent agreement plus Cohen's/Fleiss' kappa and Krippendorff's alpha, per-class counts, sample sizing, confusion matrices
- **Where judges break** — objectively-checkable reasoning/math/code tasks, close-quality pairs, JudgeBench-style near-random results
- **Cost and model choice** — frontier judge vs small-model panel vs fine-tuned open judge (Prometheus); price/latency vs agreement tradeoff
- **Operating in production** — drift, rubric versioning, canary eval sets, periodic recalibration cycles

## Terms to define
- **LLM-as-a-judge** — using an LLM, prompted with criteria, to score or rank another model's output
- **Pairwise comparison** — judge sees two candidate responses to the same prompt and picks a winner or a tie
- **Single-answer grading / direct assessment** — judge assigns an absolute score to one response with no comparison target
- **Reference-guided grading** — judge scores a response against a supplied gold/reference answer
- **Rubric** — explicit written scoring criteria and score-level descriptions handed to the judge
- **Position bias** — judge verdict changes when the order of the two candidate responses is swapped
- **Verbosity bias** — judge systematically prefers longer responses irrespective of content quality
- **Self-enhancement / self-preference bias** — judge rates outputs from itself or its own model family more favourably
- **Position consistency** — fraction of pairs where the judge gives the same verdict under both orderings
- **Repetition stability** — fraction of pairs where the judge gives the same verdict on repeated identical calls
- **Preference fairness** — metric for the direction and magnitude of a judge's positional skew
- **Form-filling paradigm** — judge is asked to emit a score into a fixed structured template rather than free prose
- **Probability-weighted score** — final score computed as expectation over token probabilities of each score value, giving finer granularity than a discrete integer
- **Panel of LLM evaluators (PoLL) / jury** — aggregating verdicts from several judge models from different families
- **Cohen's kappa** — agreement statistic between two raters, corrected for agreement expected by chance
- **Weighted kappa** — kappa variant that penalises large label distance more than adjacent-label disagreement, for ordinal scales
- **Fleiss' kappa / Krippendorff's alpha** — chance-corrected agreement for three or more raters (alpha also handles missing/unequal annotations)
- **Grader** — provider-API abstraction for an eval scoring function; may be string-check, similarity, model-scored, or code
- **Elo / Bradley–Terry rating** — method for converting pairwise win/loss records into a single model ranking, as in Chatbot Arena
- **SummEval / QAGS** — human-annotated summarization benchmarks used to test correlation of automatic evaluators
- **MT-Bench** — 80-question multi-turn benchmark scored by an LLM judge
- **JudgeBench** — benchmark that tests judges on pairs where one response is verifiably correct and the other verifiably wrong

Sources: [MT-Bench/Chatbot Arena](https://arxiv.org/abs/2306.05685), [G-Eval](https://arxiv.org/abs/2303.16634), [Prometheus](https://arxiv.org/abs/2310.08491), [Prometheus 2](https://arxiv.org/pdf/2405.01535), [PoLL](https://arxiv.org/abs/2404.18796), [JudgeBench](https://arxiv.org/abs/2410.12784), [Position bias study](https://arxiv.org/abs/2406.07791), [Justice or Prejudice?](https://arxiv.org/abs/2410.02736), [Anthropic docs](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests), [OpenAI graders](https://developers.openai.com/api/docs/guides/graders), [Arize on judge alignment](https://arize.com/blog/measuring-human-llm-judge-alignment/), [Cohen's kappa calibration](https://oneuptime.com/blog/post/2026-08-31-calibrate-llm-judge-cohens-kappa/view)
