"""Versioned prompts for both stages.

Bump PROMPT_VERSION on any edit below. The version *and* a hash of the fully
rendered prompt are recorded per run, so a prompt tweak can never be mistaken
for a model difference.

Two rules govern everything here:

1. The writer prompt carries **no style guidance**. We are measuring each
   model's native voice; telling it how to write would destroy the experiment.
2. The research prompt forbids prose. A brief written in flowing sentences puts
   the research model's own stylistic tics into the writer's input, and the
   evaluator would then be scoring the brief instead of the writer.

Keep both free of dates and timestamps so the rendered text stays byte-stable
and therefore hashable across days.
"""

from __future__ import annotations

# Versioned per stage: a research-prompt tweak must not invalidate writer
# comparisons, and vice versa.
RESEARCH_PROMPT_VERSION = "v2"
WRITER_PROMPT_VERSION = "v1"

# Back-compat alias for the stage whose output is actually compared.
PROMPT_VERSION = WRITER_PROMPT_VERSION

# --- Stage A: research ------------------------------------------------------

RESEARCH_SYSTEM = """\
You are a research assistant who prepares source material for other writers.

You produce notes, never prose. Your output is raw material: facts, figures, \
quotes and structure. Someone else does the writing.
"""

RESEARCH_USER_TEMPLATE = """\
Research the topic below and produce a brief in exactly the format specified.

Topic: {topic}

Use web search to gather current, accurate material. Prefer primary sources.

Begin your output with the line "## Key facts". Do not write anything before
it -- no acknowledgement, no statement of what you are about to do.

Output format — use these five headings, in this order, and nothing else:

## Key facts
- 8-14 bullets. Each bullet is a single verifiable claim followed by its source
  URL in parentheses.

## Figures
- Numbers, dates, benchmarks, prices, percentages. One per bullet, each with a
  source URL. Omit the section if the topic genuinely has no figures.

## Quotes
- Direct quotations worth reusing, each with speaker, affiliation and source
  URL. Omit the section if there are none worth including.

## Suggested sections
- 4-7 bullets naming sections a post on this topic should cover. Each bullet is
  a short label plus a few words on what belongs there. Labels, not prose.

## Terms to define
- Jargon a general technical reader would not know, each with a one-line gloss.

Hard constraints on your output:
- Write in sentence fragments and note form. Not paragraphs.
- No introduction, no conclusion, no framing, no transitions, no commentary on
  the topic's importance.
- Do not address the reader or the writer.
- Do not suggest a title, an angle, a hook, or an opening line.
- Every factual bullet carries a source URL.
- Your first line is "## Key facts". Nothing precedes it.
"""


def normalize_brief(text: str) -> str:
    """Strip anything before the first heading.

    The model sometimes prefixes a conversational line ("I'll gather primary
    sources on...") which both contaminates the writer's input with prose and
    runs into the first heading. Normalising is deterministic, so it is a
    better guarantee than prompt wording alone.

    Only briefs are normalised. Generated posts are never touched -- they are
    the specimen.
    """
    marker = text.find("## ")
    if marker == -1:
        return text.strip()
    return text[marker:].strip()


def build_research_prompt(topic: str) -> str:
    return RESEARCH_USER_TEMPLATE.format(topic=topic)


# --- Stage B: writing (the measured step) -----------------------------------

WRITER_SYSTEM = """\
You are a technical blog writer. You are given a topic and a research brief, \
and you write the finished post.
"""

WRITER_USER_TEMPLATE = """\
Write a blog post on the topic below, using the research brief provided.

Topic: {topic}

Target length: approximately {word_target} words.

Research brief:

---
{brief}
---

Output the post as Markdown, starting with a level-1 heading for the title. \
Output only the post itself, with no preamble and no closing commentary.
"""


def build_writer_prompt(topic: str, brief: str, word_target: int) -> str:
    return WRITER_USER_TEMPLATE.format(
        topic=topic, brief=brief.strip(), word_target=word_target
    )
