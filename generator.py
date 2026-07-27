"""Build a short, cited answer from retrieved passages.

Selects the sentences in the retrieved chunks that best match the query and
joins them into a brief answer, recording which sources were used and carrying
the top retrieval score through as a confidence value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from retriever import RetrievedChunk, _tokenize

# The most sentences to include in one answer. Small on purpose: a focused
# answer is easier to trust and cite than a wall of text.
MAX_SENTENCES = 4


@dataclass
class Answer:
    """A draft answer and the evidence behind it.

    ``text`` is the answer shown to the user. ``citations`` lists the unique
    "source > heading" locations the sentences came from. ``confidence`` is the
    top retrieval score (0.0-1.0) carried through so the self-check can threshold
    on it. ``used_sources`` is the set of filenames actually quoted.
    """

    text: str
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    used_sources: list[str] = field(default_factory=list)


def _split_sentences(text: str) -> list[str]:
    """Break a passage into whole sentences and bullet-list items.

    Knowledge-base documents wrap prose across several lines, so a naive split
    on newlines would shatter one sentence into fragments. Instead, consecutive
    prose lines are joined back together and then split on sentence-ending
    punctuation, while bullet lines (starting with "-") are kept as their own
    items so lists like the emergency checklist survive intact. Markdown heading
    lines ("## ...") are dropped -- they are labels, not answer content.
    """
    sentences: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        """Turn the buffered prose lines into sentences and clear the buffer."""
        if paragraph:
            joined = " ".join(paragraph)
            sentences.extend(
                s.strip() for s in re.split(r"(?<=[.!?])\s+", joined) if s.strip()
            )
            paragraph.clear()

    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            flush()  # blank line or heading ends the current prose run
            continue
        if line.startswith("-"):
            flush()  # a bullet ends the prose run and stands on its own
            sentences.append(line.lstrip("-").strip())
        else:
            paragraph.append(line)
    flush()
    return sentences


def generate(query: str, retrieved: list[RetrievedChunk]) -> Answer:
    """Build a short, cited answer from the retrieved passages.

    Scores every sentence in the retrieved chunks by how many query words it
    shares (breaking ties toward higher-ranked chunks), keeps the best few in
    their original reading order, and records which sources were used. Returns an
    empty-text ``Answer`` when nothing was retrieved, so the caller can abstain.
    """
    if not retrieved:
        return Answer(text="", confidence=0.0)

    query_terms = set(_tokenize(query))
    top_score = retrieved[0].score

    # Score each candidate sentence, remembering where it came from: its chunk's
    # retrieval RANK (0 = most relevant passage) and its position within that
    # chunk, so we can restore a sensible reading order after ranking.
    scored: list[tuple[int, int, float, str, RetrievedChunk]] = []
    for rank, rc in enumerate(retrieved):
        for position, sentence in enumerate(_split_sentences(rc.chunk.text)):
            overlap = len(query_terms & set(_tokenize(sentence)))
            if overlap == 0:
                continue  # a sentence sharing no query words adds no answer
            # Primary: word overlap. Secondary: the chunk's own relevance score.
            scored.append((rank, position, overlap + rc.score, sentence, rc))

    # Nothing in the retrieved text matched the query wording. Fall back to the
    # single best chunk's opening sentences so the user still gets its gist.
    if not scored:
        best = retrieved[0].chunk
        fallback = " ".join(_split_sentences(best.text)[:2])
        citation = f"{best.source} > {best.heading}"
        return Answer(
            text=fallback,
            citations=[citation],
            confidence=top_score,
            used_sources=[best.source],
        )

    # Keep the highest-scoring sentences, then re-sort the survivors back into
    # reading order -- most-relevant chunk first (rank), then top-to-bottom
    # within each chunk (position) -- so the answer leads with the best passage.
    scored.sort(key=lambda item: item[2], reverse=True)
    best = scored[:MAX_SENTENCES]
    best.sort(key=lambda item: (item[0], item[1]))

    seen: set[str] = set()
    answer_sentences: list[str] = []
    citations: list[str] = []
    used_sources: list[str] = []
    for _rank, _position, _score, sentence, rc in best:
        if sentence in seen:
            continue  # the same line can appear in overlapping chunks
        seen.add(sentence)
        answer_sentences.append(sentence)
        citation = f"{rc.chunk.source} > {rc.chunk.heading}"
        if citation not in citations:
            citations.append(citation)
        if rc.chunk.source not in used_sources:
            used_sources.append(rc.chunk.source)

    text = " ".join(answer_sentences)
    if not text.endswith((".", "!", "?")):
        text += "."
    return Answer(
        text=text,
        citations=citations,
        confidence=top_score,
        used_sources=used_sources,
    )
