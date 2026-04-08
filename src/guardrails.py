"""
Step 9 — Guardrails + Prompt Security (HostAI).

Provides defence-in-depth at the invoke_agent boundary:
  - detect_prompt_injection : detects injection patterns in user input
  - sanitize_input          : strips/escapes known dangerous sequences
  - check_input_length      : enforces max character limit
  - mask_pii                : masks phone, email, credit-card numbers
  - validate_output         : ensures final response doesn't echo injection
  - GuardrailsConfig        : named configuration dataclass
  - apply_input_guardrails  : runs all input checks, raises GuardrailViolation
  - apply_output_guardrails : runs all output checks, returns safe text
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ─── Exception ────────────────────────────────────────────────────────────────

class GuardrailViolation(Exception):
    """Raised when a guardrail policy is violated."""


# ─── Prompt injection detection ───────────────────────────────────────────────

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS: list[re.Pattern] = [
    # Role confusion / override
    re.compile(r"ignore\s+(previous|all|your|prior)\s+(instructions?|prompt|rules?)", re.I),
    re.compile(r"disregard\s+(previous|all|your|prior)\s+(instructions?|prompt|rules?)", re.I),
    re.compile(r"forget\s+(your|all|previous)\s+(instructions?|prompt|rules?)", re.I),
    re.compile(r"\boverride\s+(?:(?:your|the|all|my)\s+)?(?:previous\s+)?(instructions?|prompt|rules?)\b", re.I),
    # Identity replacement
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bact\s+as\b(?!\s+a\s+reservation)", re.I),   # allow "act as a reservation..."
    re.compile(r"\bpretend\s+(to\s+be|you\s+are)\b", re.I),
    re.compile(r"\bimpersonate\b", re.I),
    # System prompt exfiltration
    re.compile(r"\breveal\s+(your|the)?\s*(system\s*)?prompt\b", re.I),
    re.compile(r"\bprint\s+(?:your|the|all)?\s*(?:system\s*)?(prompt|instructions?|rules?|directives?)\b", re.I),
    re.compile(r"\bshow\s+(your|the)?\s*(system\s*)?instructions?\b", re.I),
    re.compile(r"\bwhat\s+(are|is)\s+your\s*(system\s*)?prompt\b", re.I),
    # Delimiter injection
    re.compile(r"<\s*/?system\s*>", re.I),
    re.compile(r"<\s*/?human\s*>", re.I),
    re.compile(r"\[INST\]", re.I),
    re.compile(r"\[\/INST\]", re.I),
    re.compile(r"###\s*(system|instruction|prompt)\b", re.I),
    # Role tokens that break conversation structure
    re.compile(r"^\s*(SYSTEM|ASSISTANT|USER)\s*:\s", re.M),
    # Jailbreak keywords
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bDAN\s+mode\b", re.I),
    re.compile(r"\bdo\s+anything\s+now\b", re.I),
]


def detect_prompt_injection(text: str) -> bool:
    """Return True if text contains a known prompt injection pattern."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ─── Input sanitization ───────────────────────────────────────────────────────

# Sequences that should be neutralized (angle-bracket wrappers, role tokens)
_SANITIZE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"<\s*/?system\s*>", re.I), "[removed]"),
    (re.compile(r"<\s*/?human\s*>", re.I), "[removed]"),
    (re.compile(r"\[INST\]|\[\/INST\]", re.I), "[removed]"),
    (re.compile(r"###\s*(system|instruction|prompt)\b", re.I), "[removed]"),
    # Collapse runs of special chars sometimes used as separators
    (re.compile(r"-{5,}"), "---"),
    (re.compile(r"={5,}"), "==="),
]


def sanitize_input(text: str) -> str:
    """Remove known dangerous injection sequences from text."""
    for pattern, replacement in _SANITIZE_RULES:
        text = pattern.sub(replacement, text)
    return text.strip()


# ─── Length check ─────────────────────────────────────────────────────────────

def check_input_length(text: str, max_chars: int) -> bool:
    """Return True if text is within max_chars limit."""
    return len(text) <= max_chars


# ─── PII masking ──────────────────────────────────────────────────────────────

_PII_RULES: list[tuple[re.Pattern, str]] = [
    # Credit card numbers (Visa/MC/Amex patterns)
    (re.compile(r"\b(?:\d[ -]?){13,16}\d\b"), "[CARD-REDACTED]"),
    # Phone: +1-555-123-4567, (555) 123-4567, 555.123.4567, 5551234567
    (re.compile(r"\+?1?\s?[\(]?\d{3}[\)]?[\s.\-]?\d{3}[\s.\-]?\d{4}\b"), "[PHONE-REDACTED]"),
    # Email
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I), "[EMAIL-REDACTED]"),
]


def mask_pii(text: str) -> str:
    """Replace PII (phone, email, credit card) with redaction placeholders."""
    for pattern, replacement in _PII_RULES:
        text = pattern.sub(replacement, text)
    return text


# ─── Output validation ────────────────────────────────────────────────────────

# Check that the agent response doesn't start with role-confusion headers
_OUTPUT_INJECTION_ECHO: list[re.Pattern] = [
    re.compile(r"<\s*/?system\s*>", re.I),
    re.compile(r"\[INST\]", re.I),
    re.compile(r"^SYSTEM\s*:", re.M),
    re.compile(r"\bignore\s+previous\s+instructions\b", re.I),
]


def validate_output(text: str) -> str:
    """
    Validate agent output.
    Raises GuardrailViolation if injection echo is detected.
    Returns the text unchanged if clean.
    """
    for pattern in _OUTPUT_INJECTION_ECHO:
        if pattern.search(text):
            raise GuardrailViolation(
                f"Output contains injection echo: pattern '{pattern.pattern}' matched."
            )
    return text


# ─── Configuration ────────────────────────────────────────────────────────────

@dataclass
class GuardrailsConfig:
    """Named configuration for guardrail thresholds."""
    max_input_chars: int = 2_000
    block_injection: bool = True
    mask_pii_in_logs: bool = True
    validate_response: bool = True
    extra_blocked_phrases: list[str] = field(default_factory=list)


# Default config used by apply_*
DEFAULT_CONFIG = GuardrailsConfig()


# ─── Composite helpers ────────────────────────────────────────────────────────

def apply_input_guardrails(
    text: str,
    config: GuardrailsConfig = DEFAULT_CONFIG,
) -> str:
    """
    Run all input guardrails in order:
      1. Length check  → GuardrailViolation
      2. Injection detection → GuardrailViolation
      3. Extra blocked phrases → GuardrailViolation
      4. Sanitize (best-effort cleanup)

    Returns the sanitized text or raises GuardrailViolation.
    """
    if not check_input_length(text, config.max_input_chars):
        raise GuardrailViolation(
            f"Input exceeds max length ({len(text)} > {config.max_input_chars} chars)."
        )

    if config.block_injection and detect_prompt_injection(text):
        raise GuardrailViolation("Prompt injection attempt detected in user input.")

    for phrase in config.extra_blocked_phrases:
        if phrase.lower() in text.lower():
            raise GuardrailViolation(
                f"Input contains blocked phrase: '{phrase}'."
            )

    return sanitize_input(text)


def apply_output_guardrails(
    text: str,
    config: GuardrailsConfig = DEFAULT_CONFIG,
) -> str:
    """
    Run all output guardrails:
      1. Validate for injection echoes → GuardrailViolation
      2. PII masking (if enabled) → returns masked text

    Returns safe output text.
    """
    if config.validate_response:
        text = validate_output(text)

    if config.mask_pii_in_logs:
        text = mask_pii(text)

    return text
