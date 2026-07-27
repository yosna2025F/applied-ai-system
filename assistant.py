"""PawPal+ assistant: the agentic RAG orchestrator.

This module is where the AI feature is "fully integrated" -- it wires the
retriever, guardrail, and generator into a single plan -> act -> check loop and
is the one entry point the UI and tests call.

The loop for every question:
  1. PLAN  -- run the safety guardrail first. If it fires, stop and return the
              safety message; never retrieve or answer.
  2. ACT   -- retrieve the top-k passages and generate a grounded draft answer.
  3. CHECK -- the self-verification step: is the draft actually supported by the
              sources (retrieval confidence above threshold)? If it is too weak,
              retry once with a wider search; if it is still weak, ABSTAIN and
              say so rather than guess.
  4. LOG   -- append a structured record of what happened (query, decision,
              confidence, sources, guardrail status) for auditing and testing.

Every path returns a ``Response``, and every path is logged, so the system's
behavior is fully traceable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import guardrail
from generator import Answer, generate
from retriever import Retriever

# Below this retrieval confidence the draft is treated as unsupported and the
# assistant abstains instead of answering. Tuned against the sample questions:
# on-topic queries score well above it, off-topic ones fall below.
MIN_CONFIDENCE = 0.05

# When the first pass is weak, the self-check retries with this many chunks
# before giving up -- a wider net sometimes surfaces a passage the top-k missed.
RETRY_K = 6

# Where structured run logs are appended, relative to this file.
LOG_PATH = Path(__file__).parent / "logs" / "interactions.jsonl"


@dataclass
class Response:
    """Everything PawPal+ decided about one question, for the UI and the logs.

    ``status`` is one of "answered", "abstained", "emergency", "diagnosis", or
    "invalid_input" -- a single field tests and the UI can branch on. ``answer``
    and ``citations`` are filled only when status is "answered".
    """

    question: str
    status: str
    answer: str = ""
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sources: list[str] = field(default_factory=list)
    guardrail_category: str = ""
    note: str = ""


class Assistant:
    """Runs the guarded, self-checking RAG loop for pet-care questions.

    Build one and reuse it: the retriever indexes the knowledge base once in
    ``__init__``. ``ask`` is the single public entry point.
    """

    def __init__(self, retriever: Retriever | None = None, log_path: Path | str = LOG_PATH) -> None:
        """Create the assistant, building a default retriever if none is given.

        Accepting an injected retriever keeps the class testable (a test can
        pass one built from a tiny fixture corpus) while the default path "just
        works" for the app.
        """
        self.retriever = retriever or Retriever()
        self.log_path = Path(log_path)

    def ask(self, question: str) -> Response:
        """Answer one question through the full plan -> act -> check -> log loop.

        Returns a ``Response`` whose ``status`` says what happened. Never raises
        on ordinary bad input (empty/whitespace questions return an
        "invalid_input" response); genuine misconfiguration like a missing
        knowledge base surfaces earlier, when the retriever is built.
        """
        # --- Guard against empty or junk input before doing any work. ---
        if not question or not question.strip():
            response = Response(
                question=question or "",
                status="invalid_input",
                note="Empty question -- nothing to answer.",
            )
            self._log(response)
            return response

        # --- 1. PLAN: safety first. ---
        verdict = guardrail.check(question)
        if verdict.triggered:
            response = Response(
                question=question,
                status=verdict.category,  # "emergency" or "diagnosis"
                answer=verdict.message,
                guardrail_category=verdict.category,
                note="Stopped by safety guardrail before retrieval.",
            )
            self._log(response)
            return response

        # --- 2. ACT: retrieve, then generate a grounded draft. ---
        retrieved = self.retriever.retrieve(question, k=3)
        draft = generate(question, retrieved)

        # --- 3. CHECK: is the draft supported well enough to trust? ---
        if draft.confidence < MIN_CONFIDENCE:
            # Self-correction: try once more with a wider search before abstaining.
            retrieved = self.retriever.retrieve(question, k=RETRY_K)
            draft = generate(question, retrieved)

        if not draft.text or draft.confidence < MIN_CONFIDENCE:
            response = Response(
                question=question,
                status="abstained",
                confidence=round(draft.confidence, 4),
                note=(
                    "No knowledge-base passage was a strong enough match, so "
                    "PawPal+ declined to answer rather than guess."
                ),
            )
            self._log(response)
            return response

        # --- Answer accepted. ---
        response = Response(
            question=question,
            status="answered",
            answer=draft.text,
            citations=draft.citations,
            confidence=round(draft.confidence, 4),
            sources=draft.used_sources,
        )
        self._log(response)
        return response

    def _log(self, response: Response) -> None:
        """Append one JSON line describing this run to the log file.

        Uses JSON Lines (one record per line) so logs are both human-readable
        and trivially parseable by the tests. Creates the log directory on first
        use. A logging failure must never crash the assistant, so write errors
        are swallowed after a best-effort attempt.
        """
        record = {"timestamp": datetime.now().isoformat(timespec="seconds"), **asdict(response)}
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            pass  # logging is best-effort; never break answering over a log write


def format_response(response: Response) -> str:
    """Render a ``Response`` as readable text for the CLI or Streamlit UI.

    Keeps all display formatting in one place so the app and the demo print
    answers, citations, and safety messages identically.
    """
    if response.status in ("emergency", "diagnosis", "invalid_input"):
        return response.answer or response.note

    if response.status == "abstained":
        return (
            "I don't have a reliable source for that in my pet-care knowledge "
            "base, so I'd rather not guess. Try rephrasing, or ask your vet."
        )

    lines = [response.answer, ""]
    lines.append(f"Confidence: {response.confidence:.2f}")
    lines.append("Sources: " + "; ".join(response.citations))
    return "\n".join(lines)


if __name__ == "__main__":
    # Manual end-to-end demo: `python assistant.py`
    assistant = Assistant()
    for q in [
        "How often should I feed my puppy?",
        "My dog is choking, what do I do?",
        "Does my cat have cancer?",
        "What is the capital of France?",
        "",
    ]:
        result = assistant.ask(q)
        print(f"Q: {q!r}")
        print(f"[status: {result.status}]")
        print(format_response(result))
        print("-" * 70)
