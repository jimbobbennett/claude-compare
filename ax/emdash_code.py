class EmDashDensity(CodeEvaluator):
    """Em-dashes per 1000 words of prose.

    Deterministic counterpart to the LLM judge. Length-normalised because one
    model writes longer at the same word target, so raw counts would report
    more style from more words.
    """

    def evaluate(self, *, output=None, **kwargs) -> EvaluationResult:
        text = output or ""
        if not text.strip():
            return EvaluationResult(
                label="no_text", score=0.0, explanation="empty output"
            )
        body = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
        body = re.sub(r"`[^`]*`", " ", body)
        words = len(body.split())
        em = body.count("—")
        if words == 0:
            return EvaluationResult(
                label="no_text", score=0.0, explanation="no words after cleaning"
            )
        per_1k = round(em * 1000.0 / words, 2)
        if per_1k >= 10:
            label = "heavy"
        elif per_1k >= 3:
            label = "moderate"
        elif per_1k > 0:
            label = "light"
        else:
            label = "none"
        return EvaluationResult(
            label=label,
            score=per_1k,
            explanation=f"{em} em-dashes in {words} words = {per_1k} per 1000",
        )
