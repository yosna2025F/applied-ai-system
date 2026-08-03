"""Search over the pet-care knowledge base.

Loads the markdown documents in ``knowledge_base/``, splits them into
paragraph-sized chunks, and ranks chunks against a query using TF-IDF vectors
compared by cosine similarity. Pure standard library, no external services.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Directory holding the knowledge-base markdown documents, relative to this file.
KB_DIR = Path(__file__).parent / "knowledge_base"

# Extremely common words carry no topical signal, so they are dropped before
# scoring. Kept deliberately short -- TF-IDF already down-weights common words.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does",
    "for", "from", "how", "i", "in", "is", "it", "its", "me", "my", "of", "on",
    "or", "our", "should", "that", "the", "their", "them", "then", "there",
    "this", "to", "up", "us", "was", "we", "what", "when", "which", "who", "why",
    "with", "you", "your",
}


# Irregular word forms the crude suffix stemmer cannot unify on its own, mapped
# to a shared root so a query using one form matches a document using another
# (e.g. the verb "bathe" and the noun "bath"). Each entry maps an exact word, so
# there is no risk of accidentally collapsing unrelated words. Extend as needed.
NORMALIZE = {
    "bathe": "bath",
    "bathes": "bath",
    "bathed": "bath",
    "peeing": "urinate",
    "pee": "urinate",
    "poop": "stool",
    "vet": "veterinarian",
    "shots": "vaccination",
    "shot": "vaccination",
    # Food vocabulary: the feeding document speaks of "feed"/"food", but users
    # ask about "eat"/"diet". Collapse all of these to one root so a question
    # like "what should my dog eat" reaches feeding.md instead of the symptoms
    # doc, where "not eating" happens to share the word.
    "eat": "feed",
    "eats": "feed",
    "eating": "feed",
    "ate": "feed",
    "food": "feed",
    "foods": "feed",
    "fed": "feed",
    "diet": "feed",
    "diets": "feed",
}


def _stem(word: str) -> str:
    """Reduce a word to a crude root so variants match ("puppies" -> "puppy").

    A deliberately tiny suffix stripper, not a full linguistic stemmer: it maps
    common plural/verb endings to a shared form so "puppy"/"puppies" and
    "feed"/"feeding" line up during matching. Correctness matters less than
    CONSISTENCY -- the query and the documents run through the exact same rules,
    so both sides collapse to the same root even when that root is not a real
    word. Length guards stop it from mangling short words like "gas" or "yes".
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"  # puppies -> puppy, allergies -> allergy
    if len(word) > 4 and word.endswith("ing"):
        return word[:-3]  # feeding -> feed, grooming -> groom
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]  # walked -> walk
    if len(word) > 3 and word.endswith("es"):
        return word[:-2]  # doses -> dos, causes -> caus
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]  # dogs -> dog, meals -> meal
    return word


def _tokenize(text: str) -> list[str]:
    """Lowercase, split into word tokens, drop stopwords, and stem.

    Splitting on non-alphanumeric runs keeps things like "24" and "week" while
    discarding punctuation. Stopwords are removed so they neither inflate the
    vocabulary nor skew similarity, and each surviving word is stemmed so
    different forms of the same word match.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(NORMALIZE.get(w, w)) for w in words if w not in STOPWORDS]


@dataclass
class Chunk:
    """One retrievable passage of the knowledge base.

    ``source`` is the file it came from (used for citations), ``heading`` is the
    nearest ``##`` title for a human-readable location, and ``text`` is the raw
    passage shown to the generator and the user.
    """

    source: str
    heading: str
    text: str


@dataclass
class RetrievedChunk:
    """A chunk paired with its similarity score for a specific query.

    ``score`` is the cosine similarity in [0.0, 1.0]; higher means a closer
    match. The generator and the guardrail layer both read this to decide how
    much to trust the passage.
    """

    chunk: Chunk
    score: float


class Retriever:
    """Loads the knowledge base once and answers top-k similarity queries.

    Build it a single time (indexing is done in ``__init__``) and reuse it for
    every question. All the expensive work -- reading files, chunking, and
    computing IDF weights -- happens up front.
    """

    def __init__(self, kb_dir: Path | str = KB_DIR) -> None:
        """Load and index every markdown document under ``kb_dir``.

        Raises ``FileNotFoundError`` if the directory is missing or holds no
        documents, rather than returning silent empty results.
        """
        self.kb_dir = Path(kb_dir)
        self.chunks = self._load_chunks()
        if not self.chunks:
            raise FileNotFoundError(
                f"No knowledge-base documents found in {self.kb_dir!r}. "
                "Add .md files before building the retriever."
            )
        # Per-chunk token frequency counts, computed once and reused.
        self._chunk_tokens = [Counter(_tokenize(c.text)) for c in self.chunks]
        self._idf = self._compute_idf()
        # The rarest term's weight, used as the weight for out-of-vocabulary query
        # words (a word absent from the whole corpus is at least as distinctive as
        # the rarest word we have seen).
        self._max_idf = max(self._idf.values())
        # Pre-compute each chunk's TF-IDF vector so queries only vectorize once.
        self._chunk_vectors = [self._tfidf(tokens) for tokens in self._chunk_tokens]

    def _load_chunks(self) -> list[Chunk]:
        """Read every ``.md`` file and split it into paragraph-sized chunks.

        A blank line separates chunks. The most recent ``##`` heading is carried
        onto following paragraphs so each chunk knows its section, which makes
        citations readable ("feeding.md > Foods that are unsafe").
        """
        chunks: list[Chunk] = []
        for path in sorted(self.kb_dir.glob("*.md")):
            heading = path.stem
            for block in path.read_text(encoding="utf-8").split("\n\n"):
                block = block.strip()
                if not block:
                    continue
                if block.startswith("#"):
                    # A heading block: capture ONLY the first line as the section
                    # heading (lstrip("#") alone would keep the body text too),
                    # and skip a bare "# Title" with no body as its own passage.
                    heading = block.splitlines()[0].lstrip("#").strip()
                    if "\n" not in block:
                        continue
                chunks.append(Chunk(source=path.name, heading=heading, text=block))
        return chunks

    def _compute_idf(self) -> dict[str, float]:
        """Compute inverse document frequency for every term in the corpus.

        A term appearing in few chunks gets a high weight; a term appearing in
        many gets a low one. The ``+1`` smoothing avoids division by zero and
        keeps weights finite for terms present in every chunk.
        """
        n_chunks = len(self.chunks)
        doc_freq: Counter[str] = Counter()
        for tokens in self._chunk_tokens:
            doc_freq.update(tokens.keys())  # each term counted once per chunk
        return {
            term: math.log(n_chunks / (1 + freq)) + 1.0
            for term, freq in doc_freq.items()
        }

    def _tfidf(self, token_counts: Counter[str]) -> dict[str, float]:
        """Turn raw token counts into a TF-IDF weight vector.

        Term frequency is normalized by the passage length so long chunks do not
        automatically outscore short ones, then multiplied by the term's IDF.
        Query terms unknown to the corpus have no IDF and are skipped.
        """
        total = sum(token_counts.values())
        if total == 0:
            return {}
        return {
            term: (count / total) * self._idf.get(term, 0.0)
            for term, count in token_counts.items()
        }

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        """Cosine similarity between two sparse TF-IDF vectors, in [0, 1].

        Only shared terms contribute to the dot product, so iterating the
        smaller vector keeps it fast. Returns 0.0 if either vector is empty
        (e.g. a query made entirely of unknown or stopword tokens).
        """
        if not a or not b:
            return 0.0
        smaller, larger = (a, b) if len(a) < len(b) else (b, a)
        dot = sum(weight * larger.get(term, 0.0) for term, weight in smaller.items())
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def retrieve(self, query: str, k: int = 3) -> list[RetrievedChunk]:
        """Return the ``k`` most relevant chunks for ``query``, best first.

        Chunks that share no meaningful terms with the query (score 0.0) are
        dropped, so a totally off-topic question returns an empty list.
        """
        query_vector = self._tfidf(Counter(_tokenize(query)))
        scored = [
            RetrievedChunk(chunk=chunk, score=self._cosine(query_vector, vector))
            for chunk, vector in zip(self.chunks, self._chunk_vectors)
        ]
        scored = [rc for rc in scored if rc.score > 0.0]
        scored.sort(key=lambda rc: rc.score, reverse=True)
        return scored[:k]

    def query_coverage(self, query: str, text: str) -> float:
        """Return the share of the query's "meaning weight" that ``text`` covers.

        Each query word is weighted by how distinctive it is (its IDF), and words
        absent from the whole corpus are treated as maximally distinctive. The
        result is the fraction of that total weight whose words actually appear in
        ``text``. A low value means the passage matched only the query's common,
        generic words and missed its distinctive topic word -- the signature of an
        answer that shares words with the question but is off-topic. Returns 1.0
        for an empty query (nothing to miss).
        """
        query_terms = set(_tokenize(query))
        if not query_terms:
            return 1.0
        text_terms = set(_tokenize(text))
        total = sum(self._idf.get(term, self._max_idf) for term in query_terms)
        covered = sum(
            self._idf.get(term, self._max_idf)
            for term in query_terms
            if term in text_terms
        )
        return covered / total if total else 1.0

    def missing_key_term(self, query: str) -> bool:
        """True if the query's most distinctive word is absent from the corpus.

        The query's meaning is carried by its rarest word; unknown words are the
        rarest of all. If that most-distinctive word never appears in any
        document, the knowledge base simply has no content for the topic (e.g.
        "sleep" or "biting"), and coverage of the query's generic words alone
        should not be trusted. Returns False for an empty query.
        """
        query_terms = set(_tokenize(query))
        if not query_terms:
            return False
        # Unknown words get a weight just above the rarest known word, so an
        # out-of-vocabulary word always ranks as the most distinctive term.
        key_term = max(query_terms, key=lambda t: self._idf.get(t, self._max_idf + 1))
        return key_term not in self._idf


if __name__ == "__main__":
    # Tiny manual smoke test: run `python retriever.py` to see retrieval work.
    retriever = Retriever()
    print(f"Indexed {len(retriever.chunks)} chunks from {retriever.kb_dir}\n")
    for question in [
        "How often should I feed my puppy?",
        "Is chocolate dangerous for dogs?",
        "When is a vomiting pet an emergency?",
    ]:
        print(f"Q: {question}")
        for rc in retriever.retrieve(question, k=2):
            preview = rc.chunk.text.replace("\n", " ")[:80]
            print(f"  [{rc.score:.3f}] {rc.chunk.source} > {rc.chunk.heading}")
            print(f"          {preview}...")
        print()
