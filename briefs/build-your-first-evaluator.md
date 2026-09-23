## Key facts
- LLM-as-a-judge uses one language model to score another model's outputs against criteria written in plain language, returning structured scores from a written rubric (https://arize.com/guides/llm-as-a-judge/)
- Strong LLM judges such as GPT-4 can match both controlled and crowdsourced human preferences, reaching the same level of agreement that humans reach with each other (https://arxiv.org/abs/2306.05685)
- The MT-Bench paper released 80 questions, 3K expert votes and 30K conversations with human preferences publicly (https://arxiv.org/abs/2306.05685)
- Few-shot judging measurably increases GPT-4's consistency on the position-bias benchmark, but higher consistency may not imply higher accuracy and the longer prompts make API calls roughly 4x more expensive (https://arxiv.org/html/2306.05685v4)
- Known judge failure modes named in primary docs: position bias (order of responses) and verbosity bias (preference for longer answers) (https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Reference-guided grading — giving the judge a gold-standard answer as benchmark — is a documented technique for improving judge reliability (https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Vendor guidance: use the most capable available model as grader, control for response length, and add chain-of-thought reasoning before scoring (https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Scaling rule from OpenAI docs: promote the LLM judge to full scale only once it is faster, cheaper, and consistently agrees with human annotations (https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Grader types available out of the box include string check (eq / ne / like / ilike), text similarity against a reference, and model graders (https://developers.openai.com/api/docs/guides/graders)
- Grader construction advice: run multiple candidate responses and ground truths through the judge to check stability, and supply few-shot examples of great, fair and poor answers (https://developers.openai.com/api/docs/guides/graders)
- Anthropic's docs frame the workflow as define measurable success criteria first, then design evals against them, spanning exact-match checks through LLM-based grading (https://docs.anthropic.com/en/docs/build-with-claude/develop-tests)
- Success criteria should be specific and measurable — "accurate sentiment classification" rather than "good performance" (https://docs.anthropic.com/en/docs/build-with-claude/develop-tests)
- Hamel Husain's "critique shadowing" method: a single domain expert answers a binary "did the AI achieve the desired outcome?" plus a written critique, rather than scoring on a 1–5 scale (https://hamel.dev/blog/posts/llm-judge/)
- Common team mistakes: too many metrics, arbitrary uncalibrated scoring scales, and not involving domain experts (https://hamelhusain.substack.com/p/llm-judge)
- Annotation guidance: if you are not an expert on the dataset contents, have a subject matter expert perform the annotation (https://developers.openai.com/api/docs/guides/evaluation-getting-started)
- Pairwise comparison by the evaluator aligns better with human judgement than direct scoring, per research surveyed by Eugene Yan (https://eugeneyan.com/writing/llm-evaluators/)

## Figures
- Over 80% agreement between GPT-4 judges and human preferences, matching human–human agreement (https://arxiv.org/abs/2306.05685)
- Few-shot judging raised GPT-4 consistency from 65.0% to 77.5% (https://arxiv.org/html/2306.05685v4)
- Fine-tuned Vicuna-13B position-bias consistency improved from 16.2% to 65.0% (https://arxiv.org/html/2306.05685v4)
- Fine-tuned Vicuna-13B classification accuracy: 56.8% over three labels, 85.5% excluding ties, against GPT-4's 66% and 87% (https://arxiv.org/html/2306.05685v4)
- Random-guess baselines for the same task: 33% (three labels) and 50% (two labels) (https://arxiv.org/html/2306.05685v4)
- Few-shot judge prompts cost roughly 4x more per API call (https://arxiv.org/html/2306.05685v4)
- MT-Bench release: 80 questions, 3K expert votes, 30K human-preference conversations (https://arxiv.org/abs/2306.05685)
- Anthropic worked example eval set size: 1,000 human-labeled tweets for a sentiment task (https://docs.anthropic.com/en/docs/build-with-claude/develop-tests)
- LLM-evaluator correlation with human ratings on SummEval and FRANK was low-to-moderate, Spearman's ρ of 0.27–0.46 (https://eugeneyan.com/writing/llm-evaluators/)
- HaluEval built 30k hallucinated samples via two-stage sampling and filtering (https://eugeneyan.com/writing/llm-evaluators/)
- Hamel Husain's guide draws on setting up evaluation systems at 30+ companies (https://hamelhusain.substack.com/p/llm-judge)
- OpenAI Evals platform deprecation: read-only for existing users October 31, 2026; shutdown November 30, 2026 (https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Human reviewers cap out at a few hundred responses per day, per Arize (https://arize.com/guides/llm-as-a-judge/)

## Quotes
- "Ever spend weeks building an AI system, only to realize you have no idea if it's actually working?" — Hamel Husain, independent ML consultant (https://hamelhusain.substack.com/p/llm-judge)
- "What makes something a 3 versus a 4? Nobody knows, and different evaluators often interpret these scales differently." — Hamel Husain (https://hamelhusain.substack.com/p/llm-judge)
- "the critique should be detailed enough so that you can use it in a few-shot prompt for a LLM judge" — Hamel Husain (https://hamelhusain.substack.com/p/llm-judge)
- "creating a LLM judge is a nice 'hack' I use to trick people into carefully looking at their data" — Hamel Husain (https://hamel.dev/blog/posts/llm-judge/)
- "Models sometimes produce different output from the same input, which makes traditional software testing methods insufficient" — OpenAI evaluation best practices docs (https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- "Instead of 'good performance,' specify 'accurate sentiment classification.'" — Anthropic Claude platform docs (https://docs.anthropic.com/en/docs/build-with-claude/develop-tests)

## Suggested sections
- Success criteria — defining specific, measurable pass conditions before writing any judge
- Dataset assembly — collecting traces, edge cases, expert annotation, growing the set over time
- Grader selection — deterministic graders (string check, similarity) vs model graders; when each is enough
- Writing the judge prompt — binary pass/fail, rubric, reference answers, chain-of-thought, few-shot critiques
- Validating the judge against humans — agreement metrics, disagreement review, iteration loop
- Bias mitigation — position, verbosity, self-enhancement; order swapping, length control
- Operationalising — CI runs, regression detection, production monitoring, judge cost and latency

## Terms to define
- LLM-as-a-judge — using a language model to score another model's output against a written rubric
- Grader / scorer — the component that turns an output into a score; can be code-based or model-based
- Critique shadowing — expert produces binary verdict plus written critique; critiques seed the judge prompt
- Position bias — judge preferring whichever candidate appears first (or second) in the prompt
- Verbosity bias — judge rewarding longer answers independent of quality
- Self-enhancement bias — judge favouring outputs from its own model family
- Reference-guided grading — supplying a gold-standard answer for the judge to compare against
- Pairwise comparison vs direct scoring — ranking two outputs against each other vs assigning an absolute score
- Trace — recorded record of a single system run, including inputs, intermediate steps and output
- Agreement / alignment — how often the judge's verdict matches the human label
- Cohen's kappa — chance-corrected agreement statistic between two raters
- Spearman's ρ — rank correlation used to compare judge scores with human ratings
- Eval-driven development — writing evals early and running them continuously, like tests
- Regression — a change that makes previously passing cases fail
