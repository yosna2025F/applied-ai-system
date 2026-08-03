"""Tests for the PawPal+ question-answering pipeline.

Covers the retriever, the safety guardrail, the answer generator, and the
end-to-end assistant loop (answer / emergency / diagnosis / abstain / bad input),
plus logging and determinism.
"""

import json
import re

import pytest

import guardrail
from assistant import MIN_CONFIDENCE, MIN_COVERAGE, Assistant, format_response
from generator import generate
from retriever import Retriever


@pytest.fixture(scope="module")
def retriever():
    """A single retriever built from the real knowledge base, reused across tests."""
    return Retriever()


@pytest.fixture
def assistant(tmp_path, retriever):
    """A fresh assistant that logs to a throwaway file so tests don't touch logs/."""
    return Assistant(retriever=retriever, log_path=tmp_path / "log.jsonl")


def _normalize(text: str) -> str:
    """Collapse all whitespace to single spaces for substring comparisons."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

# The retriever loads and chunks the knowledge base on construction.
def test_retriever_indexes_knowledge_base(retriever):
    assert len(retriever.chunks) > 0


# A feeding question retrieves the feeding document as its top match.
def test_retriever_returns_relevant_source(retriever):
    results = retriever.retrieve("how often should I feed my puppy?", k=3)

    assert results  # at least one match
    assert results[0].chunk.source == "feeding.md"


# An off-topic question shares no meaningful terms, so nothing is retrieved.
def test_retriever_offtopic_returns_empty(retriever):
    assert retriever.retrieve("what is the capital of France?") == []


# Retrieval is deterministic: the same query gives the same ranked results.
def test_retriever_is_deterministic(retriever):
    first = retriever.retrieve("grooming and nail trimming", k=3)
    second = retriever.retrieve("grooming and nail trimming", k=3)

    assert [r.chunk.text for r in first] == [r.chunk.text for r in second]
    assert [r.score for r in first] == [r.score for r in second]


# ---------------------------------------------------------------------------
# Topic coverage (the fail-safe signal)
# ---------------------------------------------------------------------------

# A passage that covers the query's distinctive words scores high coverage.
def test_query_coverage_high_for_on_topic(retriever):
    top = retriever.retrieve("what foods are toxic to dogs?", k=1)[0].chunk.text

    assert retriever.query_coverage("what foods are toxic to dogs?", top) > MIN_COVERAGE


# A query whose topic word is absent from the corpus scores low coverage, even
# when generic words ("puppy") still match.
def test_query_coverage_low_when_topic_absent(retriever):
    top = retriever.retrieve("how do I stop my puppy from biting", k=1)[0].chunk.text

    assert retriever.query_coverage("how do I stop my puppy from biting", top) < MIN_COVERAGE


# An empty query has no terms to miss, so coverage is defined as full.
def test_query_coverage_empty_query_is_full(retriever):
    assert retriever.query_coverage("", "any text at all") == 1.0


# ---------------------------------------------------------------------------
# Guardrail
# ---------------------------------------------------------------------------

# Emergency wording trips the guardrail and is tagged as an emergency.
def test_guardrail_flags_emergency():
    result = guardrail.check("my dog is choking and collapsed")

    assert result.triggered is True
    assert result.category == "emergency"
    assert result.message  # a message to show the user


# A request to name a disease trips the guardrail as a diagnosis request.
def test_guardrail_flags_diagnosis():
    result = guardrail.check("does my dog have cancer?")

    assert result.triggered is True
    assert result.category == "diagnosis"


# A normal care question passes the guardrail untouched.
def test_guardrail_allows_normal_question():
    result = guardrail.check("how often should I brush my cat?")

    assert result.triggered is False
    assert result.category == ""


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

# The generated answer is built from a real source and reports that citation.
def test_generator_answer_cites_a_real_source(retriever):
    retrieved = retriever.retrieve("is chocolate dangerous for dogs?", k=3)

    answer = generate("is chocolate dangerous for dogs?", retrieved)

    assert answer.text
    assert answer.citations
    assert all(c.endswith(".md") is False for c in answer.citations)  # "file.md > heading"
    assert any(src.endswith(".md") for src in answer.used_sources)


# With nothing retrieved, the generator returns an empty answer instead of guessing.
def test_generator_empty_when_no_chunks():
    answer = generate("anything at all", [])

    assert answer.text == ""
    assert answer.confidence == 0.0


# ---------------------------------------------------------------------------
# Assistant (end to end)
# ---------------------------------------------------------------------------

# A known question is answered, with a citation and above-threshold confidence.
def test_assistant_answers_known_question(assistant):
    response = assistant.ask("how often should I feed my puppy?")

    assert response.status == "answered"
    assert response.answer
    assert response.citations
    assert response.confidence >= MIN_CONFIDENCE


# The answer text actually comes from the knowledge base, not invented.
def test_assistant_answer_is_grounded_in_sources(assistant, retriever):
    response = assistant.ask("what foods are toxic to dogs?")
    corpus = _normalize(
        " ".join(chunk.text for chunk in retriever.chunks)
    )

    # The first sentence of the answer is lifted verbatim from a source document.
    first_sentence = _normalize(response.answer).split(". ")[0]
    assert first_sentence in corpus


# An emergency question is refused and never reaches retrieval.
def test_assistant_refuses_emergency(assistant):
    response = assistant.ask("my dog is choking, what do I do?")

    assert response.status == "emergency"
    assert response.citations == []


# A diagnosis request is refused and pointed to a vet.
def test_assistant_refuses_diagnosis(assistant):
    response = assistant.ask("does my cat have cancer?")

    assert response.status == "diagnosis"
    assert "veterinarian" in response.answer.lower()


# An off-topic question is declined rather than answered with a guess.
def test_assistant_abstains_when_off_topic(assistant):
    response = assistant.ask("what is the capital of France?")

    assert response.status == "abstained"
    assert response.answer == ""


# A question whose topic is absent from the knowledge base is declined by the
# coverage fail-safe, even though generic words like "puppy" still match a passage.
def test_assistant_abstains_when_topic_not_covered(assistant):
    response = assistant.ask("how do I stop my puppy from biting")

    assert response.status == "abstained"
    assert response.coverage < MIN_COVERAGE


# A question the knowledge base does cover clears the coverage bar and is answered.
def test_assistant_answers_when_topic_is_covered(assistant):
    response = assistant.ask("how long should I walk my dog?")

    assert response.status == "answered"
    assert response.coverage >= MIN_COVERAGE


# Empty and whitespace-only input is handled without crashing.
@pytest.mark.parametrize("bad_input", ["", "   ", "\n\t"])
def test_assistant_handles_empty_input(assistant, bad_input):
    response = assistant.ask(bad_input)

    assert response.status == "invalid_input"


# Every interaction appends one parseable JSON line to the log file.
def test_assistant_logs_each_interaction(assistant):
    assistant.ask("how often should I feed my puppy?")
    assistant.ask("my dog is choking")

    lines = assistant.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]  # must all parse as JSON
    assert records[0]["status"] == "answered"
    assert records[1]["status"] == "emergency"


# The same question produces the same answer every time (deterministic output).
def test_assistant_is_deterministic(assistant):
    first = assistant.ask("how do I trim my dog's nails?")
    second = assistant.ask("how do I trim my dog's nails?")

    assert first.answer == second.answer
    assert first.confidence == second.confidence


# format_response renders each status into user-facing text without crashing.
@pytest.mark.parametrize(
    "question",
    [
        "how often should I feed my puppy?",  # answered
        "my dog is choking",                  # emergency
        "does my dog have cancer?",           # diagnosis
        "what is the capital of France?",     # abstained
    ],
)
def test_format_response_renders_every_status(assistant, question):
    text = format_response(assistant.ask(question))

    assert isinstance(text, str)
    assert text.strip()
