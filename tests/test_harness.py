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


# --- evaluator v2 ------------------------------------------------------------


def test_v2_template_matches_the_spec():
    from blogwriter.judge_spec import TEMPLATE_V2_PATH, render_template_v2

    assert TEMPLATE_V2_PATH.read_text() == render_template_v2(), (
        "ax/claudism_spans_template.txt is stale -- "
        "run: uv run python -m blogwriter.judge_spec --write"
    )


def test_v2_template_has_exactly_one_variable_and_no_other_braces():
    """Literal braces in an AX template can be read as variables, so the JSON
    shape is described in words and {output} is the only brace pair."""
    from blogwriter.judge_spec import CLAUDISM_CATEGORIES_V2, render_template_v2

    rendered = render_template_v2()
    assert rendered.count("{output}") == 1
    assert rendered.replace("{output}", "").count("{") == 0
    assert rendered.replace("{output}", "").count("}") == 0
    for name in CLAUDISM_CATEGORIES_V2:
        assert name in rendered


@pytest.mark.parametrize(
    "text",
    [
        "That's not backstory. It cannot be moved. It is load-bearing.",
        "This is the load bearing argument for stand mixers.",
        "The second clause bears the load of the whole paragraph.",
        "Retrieval carries most of the weight here.",
    ],
)
def test_load_bearing_is_always_caught(text):
    """Load-bearing is a must-catch in both halves; the regex half is here."""
    assert score_text(text).claude_leaning.get("load_bearing") == 1


def test_v2_regex_patterns_fire_on_flagged_wording():
    score = score_text(
        "Two things worth internalising. That's the whole point. "
        "The honest answer is no. The prompt is doing a lot of work. "
        "The trap is defaults."
    )
    for name in (
        "salience_flag",
        "the_whole_x",
        "the_honest_x",
        "doing_work",
        "gotcha_framing",
    ):
        assert score.claude_leaning.get(name) == 1, name


def test_heavy_lifting_is_not_double_counted():
    score = score_text("The retriever is doing the heavy lifting.")
    assert score.claude_leaning == {"heavy_lifting": 1}


def test_judge_output_parses_through_fences_and_drops_bad_items():
    from blogwriter.judge_spec import parse_judge_output

    raw = (
        "```json\n"
        '{"instances": [{"quote": "It is load-bearing.", "category": '
        '"stock_metaphor"}, {"quote": "x", "category": "made_up"}, '
        '{"quote": "", "category": "signpost"}]}\n```'
    )
    assert parse_judge_output(raw) == [
        {"quote": "It is load-bearing.", "category": "stock_metaphor"}
    ]
    with pytest.raises(ValueError):
        parse_judge_output("no json here")


def test_v2_score_is_length_normalised_onto_the_shared_scale():
    from blogwriter.judge_spec import score_instances

    three = [{"quote": "q", "category": "signpost"}] * 3
    assert score_instances([], 1000)["label"] == "absent"
    assert score_instances(three, 1000)["label"] == "strong"
    assert score_instances(three, 3000)["label"] == "moderate"
    assert score_instances(three, 1000)["by_category"] == {"signpost": 3}


def test_validate_counts_overlap_and_enforces_load_bearing():
    from blogwriter.validate import KNOWN_LOAD_BEARING, validate

    flags = [
        {
            "doc_id": "why-novels-open-with-prologues.r2.md",
            "repeat": 2,
            "quote": "It is load-bearing",
            "sentence": "It is load-bearing.",
        },
        {
            "doc_id": "why-novels-open-with-prologues.r2.md",
            "repeat": 2,
            "quote": "The interaction matters",
            "sentence": "The interaction matters.",
        },
    ]
    judge = {
        doc: [{"quote": snippet, "category": "stock_metaphor"}]
        for doc, snippet in KNOWN_LOAD_BEARING
    }
    judge["why-novels-open-with-prologues.r2.md"].append(
        {"quote": "an unflagged span", "category": "signpost"}
    )
    result = validate(flags, judge=judge)
    assert result.regex_found == 1
    assert result.judge_found == 1
    assert len(result.unflagged) == 1
    assert result.load_bearing_misses == []

    judge["against-the-stand-mixer.r1.md"] = []
    missed = validate(flags, judge=judge)
    assert missed.load_bearing_misses == ["judge missed against-the-stand-mixer.r1.md"]


def test_judge_prompt_fills_the_template_without_front_matter():
    from blogwriter.judge import build_prompt

    prompt = build_prompt("---\nmodel_id: x\n---\nThe interaction matters.")
    assert "The interaction matters." in prompt
    assert "model_id" not in prompt
    assert "{output}" not in prompt


def test_judge_post_scores_the_reply(tmp_path, monkeypatch):
    import blogwriter.judge as judge

    post = tmp_path / "p.r1.md"
    post.write_text("---\nslug: p\n---\n" + " ".join(["word"] * 1000))
    reply = '{"instances": [{"quote": "a", "category": "signpost"}]}'
    monkeypatch.setattr(judge, "call_judge", lambda *a, **k: reply)
    result = judge.judge_post(post, model="m", api_key="k")
    assert result["instances"] == [{"quote": "a", "category": "signpost"}]
    assert result["instances_per_1k"] == 1.0
    assert result["score"] == 3


# --- AX experiments: positions, annotations, remote evaluator ---------------


def test_locate_is_exact_first_then_tolerates_dropped_markdown():
    from blogwriter.positions import locate

    text = "The `effort` parameter is the replacement. It is *very* load-bearing."
    assert locate("It is", text) == (43, 48)
    start, end = locate("The effort parameter is the replacement", text)
    assert text[start:end] == "The `effort` parameter is the replacement"
    start, end = locate("It is very  load-bearing", text)
    assert text[start:end] == "It is *very* load-bearing"
    assert locate("not in the post", text) is None
    assert locate("   ", text) is None


def test_position_lines_round_trip_with_and_without_category():
    from blogwriter.positions import Located, format_lines, parse_lines

    items = [
        Located(40, 52, "That's it | really", "verdict_intensifier"),
        Located(3, 10, "a quote"),
        Located(-1, -1, "unlocated", "signpost"),
    ]
    text = format_lines(items)
    assert text.splitlines()[0] == "-1--1 | signpost | unlocated"
    assert sorted(parse_lines(text), key=lambda x: x.start) == sorted(
        items, key=lambda x: x.start
    )
    assert parse_lines("garbage\n\n") == []


def test_flag_lines_use_the_text_as_it_appears_and_enforce_the_limit():
    import pytest

    from blogwriter.ax_experiments import flag_lines

    output = "Intro. The word *approximate* is doing a lot of work. End."
    flags = [{"id": 1, "quote": "The word approximate is doing a lot of work"}]
    assert flag_lines(flags, output) == (
        "7-52 | The word *approximate* is doing a lot of work"
    )
    with pytest.raises(SystemExit, match="cannot locate"):
        flag_lines([{"id": 2, "quote": "missing"}], output)
    long_output = "x " * 2000
    many = [{"id": i, "quote": "x " * 100} for i in range(10)]
    with pytest.raises(SystemExit, match="exceeds"):
        flag_lines(many, long_output)


def test_recall_matches_evaluator_spans_to_flags_by_position():
    from blogwriter.ax_experiments import recall_for_run

    run = {
        "evaluations": {
            "claudism_spans": {
                "score": 2.0,
                "explanation": "0-10 | signpost | Here's why\n"
                "50-60 | stock_metaphor | load-bearing",
            }
        },
        "annotations": [
            {"name": "claudisms", "text": "2-8 | Here's\n100-120 | something else"}
        ],
    }
    result = recall_for_run(run, "not-a-load-bearing-post.r1.md")
    assert result == {"flags": 2, "found": 1, "spans": 2, "load_bearing_missed": []}
    assert recall_for_run({"evaluations": {}}, "x.r1.md") is None


def test_recall_flags_a_missed_load_bearing_sentence():
    from blogwriter.ax_experiments import recall_for_run
    from blogwriter.validate import KNOWN_LOAD_BEARING

    doc_id, snippet = KNOWN_LOAD_BEARING[0]
    run = {"evaluations": {"claudism_spans": {"explanation": ""}}}
    assert recall_for_run(run, doc_id)["load_bearing_missed"] == [snippet]


def test_eval_server_requires_the_token_and_returns_positions(monkeypatch):
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import blogwriter.eval_server as server

    calls = []

    def fake_judge(text, *, model, api_key):
        calls.append(text)
        return {
            "instances": [{"quote": "It matters", "category": "salience_flag"}],
            "instances_per_1k": 4.2,
            "instance_count": 1,
            "label": "strong",
        }

    monkeypatch.setenv("CLAUDISM_EVAL_TOKEN", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(server, "judge_text", fake_judge)
    client = TestClient(server.create_app())
    body = {"metadata": {"record_id": "r1"}, "input": {"output": "Hi. It matters."}}

    assert client.post("/v1/evaluate", json=body).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.post("/v1/evaluate", json=body, headers=wrong).status_code == 401

    auth = {"Authorization": "Bearer secret"}
    reply = client.post("/v1/evaluate", json=body, headers=auth)
    assert reply.status_code == 200
    assert reply.json() == {
        "score": 4.2,
        "label": "strong",
        "explanation": "4-14 | salience_flag | It matters",
    }
    # A retry of the same record reuses the first judge call.
    client.post("/v1/evaluate", json=body, headers=auth)
    assert len(calls) == 1

    flat = {"arize_metadata": {"record_id": "r2"}, "output": "Hi. It matters."}
    assert client.post("/v1/evaluate", json=flat, headers=auth).json()["score"] == 4.2

    bad = {"input": {"output": ""}}
    assert client.post("/v1/evaluate", json=bad, headers=auth).status_code == 400


def test_evaluation_reads_the_flat_export_shape():
    from blogwriter.ax_experiments import evaluation

    run = {"additional_properties": {
        "eval.em_dash_density.score": 12.5,
        "eval.em_dash_density.label": "heavy",
        "eval.claudism_spans.explanation": "1-2 | signpost | x",
        "model_id": "claude-opus-5",
    }}
    assert evaluation(run, "em_dash_density") == {"score": 12.5, "label": "heavy"}
    assert evaluation(run, "claudism_spans") == {"explanation": "1-2 | signpost | x"}
    assert evaluation(run, "missing") is None
    assert evaluation({"evaluations": {"x": {"score": 1}}}, "x") == {"score": 1}


def test_spans_fit_own_output_detects_results_on_the_wrong_run():
    from blogwriter.ax_experiments import spans_fit_own_output

    def run(output, explanation):
        key = "eval.claudism_spans.explanation"
        return {"output": output, "additional_properties": {key: explanation}}

    span = "4-14 | salience_flag | It matters"
    assert spans_fit_own_output(run("Hi. It matters.", span))
    assert spans_fit_own_output(run("Other post here.", span)) is False
    assert spans_fit_own_output(run("x", "-1--1 | signpost | nowhere")) is None
    assert spans_fit_own_output({"output": "x"}) is None
