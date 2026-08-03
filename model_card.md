# Model Card — PawPal+

A responsible-AI reflection on PawPal+, an offline retrieval-augmented pet-care
assistant with safety guardrails and a self-checking answer loop.

## System Overview

PawPal+ answers general pet-care questions by retrieving passages from a small,
curated knowledge base and building an answer *from those passages* (with
citations). It is not a machine-learned model — retrieval uses TF-IDF with cosine
similarity and answers are extractive (assembled from source sentences), so the
system is fully offline and deterministic. Before answering, a guardrail screens
for emergencies and diagnosis requests, and a confidence check makes the system
abstain rather than guess when no source is a strong match.

PawPal+ also includes the original deterministic scheduler carried over from the
base project. That component is rule-based logic with no model, training data, or
learned behavior, so it is out of scope for this model card; its design and
testing are covered in [`reflection.md`](reflection.md).

## Intended Use

- **Intended:** general, non-urgent pet-care information (feeding, exercise,
  grooming, vaccination basics, settling a new pet) for pet owners who want a
  quick, source-cited pointer.
- **Not intended:** medical diagnosis, treatment or medication advice, emergency
  response, or any decision that should involve a licensed veterinarian.

## Limitations and Biases

- **Keyword retrieval misses synonyms and paraphrases.** Matching is lexical
  (TF-IDF over stemmed words). A question worded very differently from the source
  document can retrieve poorly or abstain even when the knowledge base technically
  covers it. A neural embedding model would catch more synonyms, but at the cost
  of an external dependency and non-determinism.
- **Extractive answers can include a loosely related sentence.** Because the
  answer is stitched from the highest-scoring sentences, an answer can occasionally
  include an on-keyword but off-topic line (e.g. a puppy *vaccination* sentence
  surfacing inside a *feeding* answer because both mention "puppy").
- **Small, curated, and culturally narrow knowledge base.** The corpus is a handful
  of general-care documents written from a mainstream, US-centric perspective. It
  does not cover exotic species, breed-specific needs, regional laws beyond a
  general mention, or non-Western care practices — so coverage is uneven and its
  "silence" on a topic is not evidence the topic is unimportant.
- **Answers are only as current and correct as the documents.** There is no live
  data; if a document is outdated or wrong, the answer will be too. Guidance is
  general and never personalized to a specific animal.
- **Guardrails are keyword-based and imperfect.** They can miss an emergency phrased
  without any of the trigger words, or over-trigger on harmless questions that
  happen to contain one. The design deliberately errs toward over-triggering.

## Misuse and Prevention

- **Being treated as a substitute for a veterinarian.** The main misuse risk is a
  user relying on PawPal+ for a real medical decision. *Prevention:* the diagnosis
  guardrail refuses to name diseases or recommend medication and redirects to a
  vet; every answer is framed as general information; and the system abstains when
  unsure instead of projecting false confidence.
- **Delayed care in an emergency.** A user might type an urgent situation hoping for
  a home fix. *Prevention:* the emergency guardrail runs *before* retrieval and
  returns an escalation message urging immediate veterinary care — the answer engine
  never handles these questions.
- **Over-trust from confident-sounding text.** *Prevention:* answers cite their
  sources and show a confidence score, so a user can see where information came from
  and how strong the match was, rather than taking an unattributed claim at face
  value.
- **Feeding the log sensitive text.** Interactions are logged locally to
  `logs/interactions.jsonl`. *Prevention:* logging is local-only (no network), and
  for any real deployment the log would need a retention and privacy policy.

## What Surprised Me While Testing Reliability

- **A silent word-form mismatch broke ranking.** The biggest surprise was how a tiny
  detail — "puppy" not matching "puppies" — quietly produced a *confidently wrong*
  answer. Nothing errored; the system just returned an irrelevant sentence. It
  taught me that in a retrieval system the scary failures are silent, not loud, and
  that you only catch them by reading the actual outputs, not by checking that the
  code runs.
- **Grounding had to be tested explicitly.** "The answer looks like it came from the
  docs" is not proof. Writing a test that asserts the answer text appears *verbatim*
  in a source document turned grounding from a hope into a guarantee.
- **Abstention is a feature, not a failure.** I expected "no answer" to feel like a
  bug. Seeing the system correctly decline "What is the capital of France?" made me
  realize a trustworthy system needs to be measured partly by what it refuses to do.

## AI Collaboration

I built PawPal+ in collaboration with an AI coding assistant (Claude), using it to
plan the architecture, scaffold modules, and debug. I directed the design decisions
and reviewed every change.

**A helpful suggestion.** When I asked how to add RAG without an API key, the
assistant recommended a fully offline, extractive approach — TF-IDF retrieval plus
answers assembled from source sentences — and running the safety guardrail *before*
retrieval. This was genuinely good advice: it made the whole project reproducible
for anyone who clones it, kept the output deterministic (which made reliability
testing meaningful), and guaranteed the system cannot hallucinate facts outside its
knowledge base. It also caught, before I wrote my architecture diagram, that my repo
still contained *no* AI feature at all — only the original scheduler — which saved me
from documenting components that did not exist.

**A flawed suggestion.** The assistant's first version of the answer generator was
wrong. It split passages into sentences by breaking on every newline, but my
knowledge-base documents wrap sentences across lines — so a fact like "Puppies under
six months need three to four small meals a day" got shattered into a meaningless
fragment ("Puppies"). Its initial word-matching also ignored word forms and its
sentence ordering led with whichever sentence happened to sit first in its
paragraph, which surfaced an off-topic vaccination line for a feeding question. The
result read plausibly but was incorrect. Fixing it took three corrections — light
stemming, joining wrapped lines back into full sentences, and ordering sentences by
their passage's relevance rank. The lesson: AI-generated code can look reasonable
and still be subtly broken, and only reading the real output — not trusting that it
"should" work — exposed it.

## Ethical Summary

PawPal+ is designed to be helpful within a narrow, low-risk lane and to fail safely
outside it. Its core responsible-AI choices are: **refuse** emergencies and
diagnoses, **abstain** rather than guess, **cite** every answer, and stay **offline
and deterministic** so its behavior is transparent and reproducible. Its main
residual risk is a user over-trusting general information as veterinary advice, which
the guardrails, citations, and confidence scores are all meant to counter.
