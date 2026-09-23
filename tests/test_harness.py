"""Tests for the pure logic -- no network, no model calls, no AX.

Deliberately scoped to the parts where a silent bug would corrupt a result:
model resolution, brief integrity, length normalisation, and the report's
integrity filter. The model calls themselves are covered by the verification
steps in the README, not by mocks.
"""

from __future__ import annotations

import pytest

from blogwriter.ax_report import EXPECTED_MODEL, aggregate, crosstab, integrity_problem
from blogwriter.claudisms import score_text, strip_front_matter
from blogwriter.models import ModelError, resolve_effort, resolve_model
from blogwriter.prompts import build_writer_prompt, normalize_brief
from blogwriter.topics import load_topics

# --- model resolution -------------------------------------------------------


def test_aliases_resolve_to_full_ids():
    assert resolve_model("opus-5") == ("opus-5", "claude-opus-5")
    assert resolve_model("opus-5.5") == ("opus-5.5", "claude-opus-5-5")


def test_raw_id_reuses_known_alias():
    assert resolve_model("claude-opus-5-5") == ("opus-5.5", "claude-opus-5-5")


def test_unregistered_claude_id_is_allowed_so_a_third_model_needs_no_code_change():
    assert resolve_model("claude-sonnet-5") == ("claude-sonnet-5", "claude-sonnet-5")


@pytest.mark.parametrize("bad", ["opus6", "gpt-5", "", "   "])
def test_bad_model_fails_before_any_api_call(bad):
    with pytest.raises(ModelError):
        resolve_model(bad)


def test_effort_is_case_insensitive_but_bounded():
    assert resolve_effort("MEDIUM") == "medium"
    with pytest.raises(ModelError):
        resolve_effort("turbo")


# --- prompt stability -------------------------------------------------------


def test_rendered_prompt_is_byte_stable():
    """The prompt hash is what proves two runs saw identical input."""
    a = build_writer_prompt(topic="T", brief="B", word_target=1200)
    b = build_writer_prompt(topic="T", brief="B", word_target=1200)
    assert a == b


def test_word_target_changes_the_prompt():
    a = build_writer_prompt(topic="T", brief="B", word_target=1200)
    b = build_writer_prompt(topic="T", brief="B", word_target=900)
    assert a != b


def test_normalize_brief_strips_conversational_preamble():
    """The research model sometimes prefixes prose, which would contaminate
    the writer's input with the research model's own voice."""
    raw = "I'll gather primary sources on X.## Key facts\n- a fact"
    assert normalize_brief(raw) == "## Key facts\n- a fact"


def test_normalize_brief_leaves_clean_input_alone():
    assert normalize_brief("## Key facts\n- a fact") == "## Key facts\n- a fact"


def test_normalize_brief_tolerates_no_headings():
    assert normalize_brief("no headings here") == "no headings here"


# --- deterministic scoring --------------------------------------------------


def test_front_matter_is_never_scored():
    text = "---\nmodel_id: claude-opus-5\n---\n\nPlain prose here."
    assert "claude-opus-5" not in strip_front_matter(text)


def test_density_is_length_normalised():
    """Opus 5.5 writes longer at the same target, so raw counts would report
    more style from more words."""
    short = score_text("It is load-bearing. " + "word " * 96)
    long = score_text("It is load-bearing. " + "word " * 996)
    assert short.claude_leaning_total == long.claude_leaning_total == 1
    assert short.densities()["claude_leaning_per_1k"] > (
        long.densities()["claude_leaning_per_1k"]
    )


def test_code_blocks_do_not_contribute_style():
    scored = score_text("Prose.\n\n```\nload-bearing delve seamless\n```\n")
    assert scored.claude_leaning_total == 0
    assert scored.generic_llm_total == 0


def test_structural_patterns_are_detected():
    text = (
        "- **Mechanics** - the call itself\n"
        "- **Modes** - pairwise, single-answer, and reference-guided\n\n"
        "It is a model. Judge it.\n"
    )
    scored = score_text(text)
    assert scored.structural["bold_leadin_bullet"] == 2
    assert scored.structural["rule_of_three"] == 1
    assert scored.structural["punchy_closer"] == 1


def test_claude_and_generic_buckets_stay_separate():
    """Lumping them together measures LLM-ness, and both models score high."""
    scored = score_text("It is load-bearing. We should delve into this.")
    assert scored.claude_leaning_total == 1
    assert scored.generic_llm_total == 1


# --- AX report integrity ----------------------------------------------------


def _span(alias, served, score=3, name="write_post[x]", **metadata):
    attributes = {"metadata": {"model_alias": alias, **metadata}}
    if served is not None:
        attributes["llm.model_name"] = served
    return {
        "name": name,
        "attributes": attributes,
        "evaluations": [{"name": "claudism_density", "score": score, "label": "x"}],
    }


def test_sound_span_has_no_integrity_problem():
    assert integrity_problem(_span("opus-5", "claude-opus-5")) is None


def test_aborted_run_is_flagged():
    """The gate aborts before writing a post, but the span still exists and
    would otherwise be scored as a real datapoint."""
    problem = integrity_problem(_span("opus-5.5", None))
    assert problem and "aborted" in problem


def test_substituted_model_is_flagged():
    problem = integrity_problem(_span("opus-5.5", "claude-opus-5"))
    assert problem and "served by" in problem


def test_expected_model_map_covers_both_aliases():
    assert set(EXPECTED_MODEL) == {"opus-5", "opus-5.5"}


def test_aggregate_excludes_unsound_spans_by_default():
    spans = [
        _span("opus-5", "claude-opus-5", score=4),
        _span("opus-5.5", None, score=1),  # aborted run
    ]
    summary, excluded = aggregate(spans)
    assert len(excluded) == 1
    assert "opus-5.5" not in summary
    assert summary["opus-5"]["claudism_mean"] == 4


def test_aggregate_can_keep_unsound_spans_when_asked():
    spans = [_span("opus-5.5", None, score=1)]
    summary, excluded = aggregate(spans, include_unsound=True)
    assert excluded == []
    assert summary["opus-5.5"]["n"] == 1


def test_aggregate_honours_run_id_filter():
    spans = [
        _span("opus-5", "claude-opus-5", score=4, run_id="keep"),
        _span("opus-5", "claude-opus-5", score=2, run_id="drop"),
    ]
    summary, _ = aggregate(spans, run_ids={"keep"})
    assert summary["opus-5"]["claudism_mean"] == 4


def test_research_spans_group_as_the_baseline():
    spans = [_span(None, None, score=1, name="research[topic]")]
    summary, _ = aggregate(spans)
    assert "BRIEFS (baseline)" in summary


def test_crosstab_splits_by_domain():
    spans = [
        _span("opus-5", "claude-opus-5", score=4, domain="ai"),
        _span("opus-5", "claude-opus-5", score=2, domain="cooking"),
        _span("opus-5.5", "claude-opus-5-5", score=3, domain="ai"),
    ]
    table = crosstab(spans, "domain")
    assert table["ai"] == {"opus-5": 4, "opus-5.5": 3}
    assert table["cooking"] == {"opus-5": 2}


# --- topic set --------------------------------------------------------------


def test_topic_set_is_well_formed():
    topics = load_topics()
    slugs = [t.slug for t in topics]
    assert len(slugs) == len(set(slugs)), "duplicate slug"
    assert all(t.topic and t.genre and t.domain for t in topics)


def test_topic_set_spans_domains_and_genres():
    """An AI-only set cannot separate the model's voice from the effect of
    writing about dense technical material."""
    topics = load_topics()
    assert len({t.domain for t in topics}) >= 4
    assert len({t.genre for t in topics}) >= 4


# --- judge spec / template sync -------------------------------------------


def test_ax_template_matches_the_spec():
    """The deployed judge prompt is generated from judge_spec.py. If this
    fails, someone edited one without regenerating the other."""
    from blogwriter.judge_spec import TEMPLATE_PATH, render_template

    assert TEMPLATE_PATH.read_text() == render_template(), (
        "ax/claudism_template.txt is stale -- "
        "run: uv run python -m blogwriter.judge_spec --write"
    )


def test_template_has_exactly_one_variable():
    from blogwriter.judge_spec import render_template

    rendered = render_template()
    assert rendered.count("{output}") == 1
    assert "{{" not in rendered, "server rejects double braces"


def test_classification_choices_cover_the_scale():
    from blogwriter.judge_spec import RATING_SCALE, classification_choices

    choices = classification_choices()
    assert set(choices) == set(RATING_SCALE)
    assert sorted(choices.values()) == [1, 2, 3, 4, 5]


# --- destyle safety rails --------------------------------------------------


def test_code_and_tables_are_protected_from_the_model():
    from blogwriter.destyle import protect, restore

    doc = (
        "Prose.\n\n```bash\nuv run thing --flag 3.45\n```\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\nMore."
    )
    protected, blocks = protect(doc)
    assert "uv run thing" not in protected, "code reached the model"
    assert "| a | b |" not in protected, "table reached the model"
    assert len(blocks) == 2
    assert restore(protected, blocks) == doc


def test_rewrite_rejected_when_a_number_is_lost():
    from blogwriter.destyle import check

    before = "The score was 3.45 against 2.77."
    after = "The score was 3.4 against 2.77."
    assert "lost" in (check(before, after, 0) or "")


def test_rewrite_rejected_when_a_heading_changes():
    from blogwriter.destyle import check

    before = "## The results\n\nSome prose here that is long enough to pass."
    after = "## Results\n\nSome prose here that is long enough to pass."
    assert check(before, after, 0) == "headings changed"


def test_rewrite_rejected_when_a_sentinel_is_dropped():
    from blogwriter.destyle import check

    before = "Text ⟦BLOCK0⟧ more text here to keep the length up."
    after = "Text more text here to keep the length up and then some."
    assert "sentinel" in (check(before, after, 1) or "")


def test_rewrite_rejected_when_content_vanishes():
    from blogwriter.destyle import check

    before = "A long paragraph " * 20
    after = "Short."
    assert "shrank" in (check(before, after, 0) or "")


def test_clean_rewrite_is_accepted():
    from blogwriter.destyle import check

    before = "## H\n\nIt is not slow, it is fast, scoring 3.45 on the scale."
    after = "## H\n\nIt is fast. It scored 3.45 on the scale, which is good news."
    assert check(before, after, 0) is None


def test_section_split_and_rejoin_is_lossless():
    """Sections must rejoin byte-identically, or headings glue together."""
    from blogwriter.destyle import split_sections

    doc = "# Title\n\nIntro.\n\n## One\n\nBody one.\n\n## Two\n\nBody two.\n"
    parts = split_sections(doc)
    assert "".join(body for _, body in parts) == doc
    assert [h for h, _ in parts] == ["", "## One", "## Two"]
