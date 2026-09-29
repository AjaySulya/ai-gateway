"""Security Engine - rules-based prompt-injection detection and PII
redaction. Deliberately simple pattern matching, not ML-based
classification - see this package's __init__.py for the reasoning.

Neither detector is comprehensive, and both have real false positive/
negative rates - that's exactly why blocking/redacting is opt-in per
policy (gateway.policy.schemas.PolicyConfig.block_prompt_injection /
redact_pii) rather than a hardcoded default: a monitoring-first posture is
the responsible one for a rules-based detector this simple.
"""

import re

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all|any|the) (previous|prior|above) instructions", re.IGNORECASE),
    re.compile(r"disregard (all|any|the) (previous|prior|above)", re.IGNORECASE),
    re.compile(r"you are now (in )?(dan|jailbreak|developer mode)", re.IGNORECASE),
    re.compile(r"reveal (your|the) system prompt", re.IGNORECASE),
    re.compile(
        r"pretend (you have no|there are no) (restrictions|rules|guidelines)", re.IGNORECASE
    ),
]

_PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


def detect_prompt_injection(messages: list[dict]) -> list[str]:
    """Returns the list of matched pattern strings (empty if none) - kept
    deliberately generic in any user-facing rejection message rather than
    echoed back, so a probing caller doesn't get a map of the detection
    rules from the error text."""
    hits = []
    for msg in messages:
        content = msg.get("content", "") or ""
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(content):
                hits.append(pattern.pattern)
    return hits


def redact_pii(messages: list[dict]) -> tuple[list[dict], list[str]]:
    """Always scans and returns (possibly-redacted messages, kinds found) -
    callers that haven't opted into redact_pii still get kinds_found back,
    to log for visibility without changing the content sent onward."""
    kinds_found: set[str] = set()
    redacted = []
    for msg in messages:
        content = msg.get("content", "") or ""
        for kind, pattern in _PII_PATTERNS.items():
            if pattern.search(content):
                kinds_found.add(kind)
                content = pattern.sub(f"[REDACTED_{kind.upper()}]", content)
        redacted.append({**msg, "content": content})
    return redacted, sorted(kinds_found)
