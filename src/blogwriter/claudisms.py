"""Deterministic "claudism" scoring: fixed phrases and structural patterns.

This half of the evaluator is pure regex and counting -- no model, no variance,
no cost. It handles what can be matched literally, so the LLM judge only has to
cover the constructions regex cannot see.

Two rules govern the design:

1. **Everything is normalised per 1000 words.** Opus 5.5 writes longer at the
   same word target, so raw counts would report "more claudisms" from length
   alone.
2. **Phrases are split into Claude-leaning and generic-LLM.** A scorer that
   lumps them together measures "LLM-ness" and both models score high. The
   split is a judgement call, stated explicitly so it can be argued with.

Bump PATTERN_VERSION on any edit to the lists below; it is recorded with every
score so results stay attributable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PATTERN_VERSION = "v2"

# v2 changelog (from 153 hand-flagged claudisms in output/full-v1/opus-5, see
# annotations/): load_bearing widened to catch "bears the load" / "carries the
# weight" (same name, so counts stay comparable with v1); added salience_flag,
# the_whole_x, the_honest_x, doing_work and gotcha_framing. Pattern names match
# the v2 judge categories in judge_spec.py where the two overlap.

# Constructions strongly associated with Claude's register specifically.
CLAUDE_LEANING: dict[str, str] = {
    # A must-catch: the best-known Claude tell. validate.py fails the run if
    # any known instance is missed.
    "load_bearing": (
        r"\bload[- ]bearing\b"
        r"|\b(?:bears?|carr(?:y|ies)) (?:the|most of the|real) (?:load|weight)\b"
    ),
    "take_a_moment": r"take a (?:moment|second|beat)",
    "heres_the_thing": r"here'?s (?:the thing|what'?s|why|the part)",
    "the_real_question": r"the (?:real|actual|interesting) question (?:is|here)",
    "sharp_edges": r"sharp edges",
    "falls_over": r"(?:where|when) it falls over",
    "heavy_lifting": r"doing the heavy lifting",
    "worth_noting": r"(?:it'?s |is )?worth noting",
    "to_be_clear": r"to be clear",
    "the_short_version": r"the short version",
    "that_said": r"that said",
    "isnt_just": r"is(?:n'?t| not) just\b",
    "not_because_but": r"not because .{1,60}? but because",
    "which_is_to_say": r"which is to say",
    "put_another_way": r"to put (?:it|that) another way",
    "the_part_that_matters": r"the (?:part|bit) that (?:actually )?matters",
    # --- added in v2 ---
    # "worth noting" is already counted above, so it is not repeated here.
    "salience_flag": (
        r"\bworth (?:internali[sz]ing|knowing|naming|taking seriously|explaining)\b"
        r"|\bdeserves a (?:moment|closer look)\b"
        r"|\bthe (?:real|critical|important) (?:lesson|detail|point)\b"
    ),
    "the_whole_x": (
        r"\bthe whole (?:point|story|pitch|argument|thing|description|game)\b"
    ),
    "the_honest_x": r"\bthe honest (?:answer|version|framing|summary|take)\b",
    # "doing the heavy lifting" stays under heavy_lifting; this excludes it so
    # one phrase is never counted twice.
    "doing_work": (
        r"\bdoing (?:a lot of|real|most of the) (?:heavy )?(?:work|lifting)\b"
        r"|\bdoing the work\b"
    ),
    "gotcha_framing": (
        r"\bthe (?:\w+ )?(?:trap|catch|gotcha) is\b|\bbites (?:everyone|people|you)\b"
    ),
}

# Common to most current LLMs. Tracked separately: if both models score high
# here, that is a fact about LLM prose, not about Claude.
GENERIC_LLM: dict[str, str] = {
    "delve": r"\bdelv(?:e|ing|es)\b",
    "tapestry": r"\btapestry\b",
    "navigate_the": r"navigat(?:e|ing) the (?:complex|landscape|world)",
    "fast_paced": r"fast[- ]paced",
    "in_todays": r"in today'?s \w+ (?:world|landscape)",
    "crucially": r"\bcrucially\b",
    "it_is_important": r"it(?:'?s| is) important to (?:note|remember|understand)",
    "unlock": r"unlock(?:ing)? the (?:power|potential)",
    "game_changer": r"game[- ]chang(?:er|ing)",
    "robust_solution": r"robust (?:solution|framework|approach)",
    "seamless": r"\bseamless(?:ly)?\b",
    "leverage": r"\bleverag(?:e|ing|es)\b",
}


@dataclass
class DeterministicScore:
    word_count: int
    # category -> number of matches
    claude_leaning: dict[str, int] = field(default_factory=dict)
    generic_llm: dict[str, int] = field(default_factory=dict)
    structural: dict[str, int] = field(default_factory=dict)
    # Verbatim matches, so any count can be audited back to the text.
    matches: list[dict[str, str]] = field(default_factory=list)

    @property
    def claude_leaning_total(self) -> int:
        return sum(self.claude_leaning.values())

    @property
    def generic_llm_total(self) -> int:
        return sum(self.generic_llm.values())

    def per_1k(self, count: int) -> float:
        if self.word_count == 0:
            return 0.0
        return round(count * 1000 / self.word_count, 2)

    def densities(self) -> dict[str, float]:
        return {
            "claude_leaning_per_1k": self.per_1k(self.claude_leaning_total),
            "generic_llm_per_1k": self.per_1k(self.generic_llm_total),
            "em_dash_per_1k": self.per_1k(self.structural.get("em_dash", 0)),
            "bold_leadin_bullet_per_1k": self.per_1k(
                self.structural.get("bold_leadin_bullet", 0)
            ),
            "rule_of_three_per_1k": self.per_1k(
                self.structural.get("rule_of_three", 0)
            ),
            "short_sentence_per_1k": self.per_1k(
                self.structural.get("short_sentence", 0)
            ),
        }


def strip_front_matter(text: str) -> str:
    """Remove the YAML front-matter the harness writes, so it is never scored."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def _sentences(prose: str) -> list[str]:
    # Good enough for counting: split on sentence-final punctuation.
    parts = re.split(r"(?<=[.!?])\s+", prose)
    return [p.strip() for p in parts if p.strip()]


def _prose_only(text: str) -> str:
    """Drop code blocks and headings; we are scoring prose, not scaffolding."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"^#{1,6} .*$", " ", text, flags=re.MULTILINE)
    return text


def score_text(text: str) -> DeterministicScore:
    """Score one document. Input may include front-matter; it is stripped."""
    body = strip_front_matter(text)
    prose = _prose_only(body)
    words = prose.split()
    score = DeterministicScore(word_count=len(words))

    for bucket_name, patterns, target in (
        ("claude_leaning", CLAUDE_LEANING, score.claude_leaning),
        ("generic_llm", GENERIC_LLM, score.generic_llm),
    ):
        for name, pattern in patterns.items():
            found = list(re.finditer(pattern, prose, flags=re.IGNORECASE))
            if found:
                target[name] = len(found)
                for m in found:
                    score.matches.append(
                        {
                            "bucket": bucket_name,
                            "category": name,
                            "quote": m.group(0),
                        }
                    )

    # --- structural patterns ---

    # Em-dash used as a clause separator. Counted on the body so that
    # dashes inside list scaffolding still count as style.
    score.structural["em_dash"] = len(re.findall(r"—", prose))

    # List items opening with a bolded phrase acting as a pseudo-heading.
    score.structural["bold_leadin_bullet"] = len(
        re.findall(r"^\s*[-*+]\s+\*\*[^*]+\*\*", body, flags=re.MULTILINE)
    )

    # "A, B, and C" -- an approximation of the rule-of-three cadence. Counts
    # the comma-series form only, so it under-reports rather than over-reports.
    score.structural["rule_of_three"] = len(
        re.findall(
            r"\b[\w'-]+(?:\s+[\w'-]+){0,3},\s+[\w'-]+(?:\s+[\w'-]+){0,3},\s+and\s+",
            prose,
        )
    )

    sentences = _sentences(prose)
    score.structural["sentence_count"] = len(sentences)
    # Very short declaratives -- the punchy-closer cadence, wherever it appears.
    score.structural["short_sentence"] = sum(
        1 for s in sentences if 1 <= len(s.split()) <= 5
    )

    # A final paragraph of one or two very short sentences.
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    score.structural["punchy_closer"] = 0
    if paragraphs:
        last = _sentences(_prose_only(paragraphs[-1]))
        if last and len(last) <= 2 and sum(len(s.split()) for s in last) <= 20:
            score.structural["punchy_closer"] = 1

    return score
