"""Screen questions for cases that must not be answered normally.

Catches two categories and returns a ready-to-show message instead of an
answer:
  * emergency -- signs that need urgent veterinary care (choking, seizures,
    suspected poisoning, heavy bleeding, ...).
  * diagnosis -- requests to name a disease or recommend medication.

Matching is done with keyword/phrase checks on the lowercased question, erring
toward caution.
"""

from __future__ import annotations

from dataclasses import dataclass

# Phrases that signal a possible emergency. Kept as substrings so "my dog is
# choking" and "she's choking!" both match. Lowercased before comparison.
EMERGENCY_TERMS = (
    "choking", "can't breathe", "cant breathe", "cannot breathe",
    "not breathing", "difficulty breathing", "collapse", "collapsed",
    "unconscious", "unresponsive", "seizure", "seizing", "convulsing",
    "poison", "poisoned", "ate chocolate", "ate xylitol", "ate grapes",
    "ate a battery", "swallowed", "overdose", "bleeding heavily",
    "won't stop bleeding", "wont stop bleeding", "hit by a car", "hit by car",
    "bloated", "bloat", "blue gums", "pale gums", "heatstroke", "heat stroke",
    "can't stand", "cant stand", "won't wake", "wont wake", "not moving",
    "can't pee", "cant pee", "straining to urinate", "broken bone",
)

# Phrases that signal the user wants a medical diagnosis rather than general
# care information. These are intentionally about ASKING FOR a verdict.
DIAGNOSIS_TERMS = (
    "diagnose", "diagnosis", "what disease", "what's wrong with my",
    "whats wrong with my", "what is wrong with my", "does my dog have",
    "does my cat have", "does my pet have", "is it cancer", "is it rabies",
    "is it parvo", "what do they have", "what does my", "is my dog dying",
    "is my cat dying", "is my pet dying", "prescribe", "what medication should",
    "what dose", "how much medicine", "what medicine should i give",
)


@dataclass
class GuardrailResult:
    """The guardrail's verdict on a single question.

    ``triggered`` is True when PawPal+ must NOT answer normally. ``category`` is
    "emergency", "diagnosis", or "" when clear. ``message`` is the ready-to-show
    text explaining what to do; it is empty when nothing triggered.
    """

    triggered: bool
    category: str
    message: str


# Pre-written responses so the message a user sees for a safety stop is
# consistent and reviewed, never improvised.
_EMERGENCY_MESSAGE = (
    "⚠️  This sounds like it could be an emergency.\n"
    "Please contact a veterinarian or an emergency animal clinic right now. "
    "Do not wait to see if it improves. If you can, call the clinic on the way "
    "so they can prepare.\n"
    "PawPal+ provides general care information only and cannot help with "
    "urgent medical situations."
)

_DIAGNOSIS_MESSAGE = (
    "🩺  PawPal+ can share general pet-care information, but it is not a "
    "veterinarian and cannot diagnose illnesses or recommend medication.\n"
    "For anything that involves what is medically wrong with your pet or how to "
    "treat it, please consult a licensed veterinarian, who can examine your pet "
    "and give a proper diagnosis."
)


def check(question: str) -> GuardrailResult:
    """Screen a question and decide whether PawPal+ must decline to answer it.

    Emergencies are checked first because they are the most time-critical: if a
    question looks like both an emergency and a diagnosis request, the user
    should be pushed to urgent care rather than a routine vet visit. Returns a
    non-triggered result for normal questions so the caller proceeds to
    retrieval.
    """
    text = (question or "").lower()

    if any(term in text for term in EMERGENCY_TERMS):
        return GuardrailResult(True, "emergency", _EMERGENCY_MESSAGE)

    if any(term in text for term in DIAGNOSIS_TERMS):
        return GuardrailResult(True, "diagnosis", _DIAGNOSIS_MESSAGE)

    return GuardrailResult(False, "", "")
