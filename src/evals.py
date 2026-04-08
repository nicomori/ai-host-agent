"""
Step 10 — Evals framework (HostAI).

Provides a lightweight, deterministic evaluation system for the HostAI
multi-agent pipeline.  No LLM calls — all evals run against the existing
stub implementation for speed and reproducibility.

Components:
  EvalCase           : one input + expected + scoring metadata
  EvalResult         : outcome of running one EvalCase
  EvalReport         : aggregated metrics across a suite
  EvalSuite          : named collection of EvalCases
  EvalRunner         : orchestrates execution, collects EvalResults

Scoring functions:
  score_exact_match  : 1.0 iff actual == expected
  score_contains     : 1.0 iff expected ⊆ actual (case-insensitive)
  score_all_present  : fraction of expected keywords found in actual
  score_intent       : 1.0 iff result["intent"] == expected intent string
  score_response_quality : fraction of required phrases in final_response
  score_guardrail_raised : 1.0 iff result["exception"] is the expected type
  score_pii_masked   : 1.0 - (leak_fraction) — penalises PII that survived masking
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class EvalCase:
    """A single evaluation case: input kwargs, expected value, scoring function."""
    case_id: str
    name: str
    input: dict[str, Any]              # keyword args forwarded to the eval function
    expected: Any                      # expected output / value
    score_fn: Callable[[Any, Any], float]  # (actual, expected) → [0.0, 1.0]
    tags: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class EvalResult:
    """Outcome of running one EvalCase."""
    case_id: str
    name: str
    passed: bool           # score >= pass_threshold
    score: float           # [0.0, 1.0]
    actual: Any
    expected: Any
    error: Optional[str] = None    # set if the eval fn raised an exception
    latency_ms: float = 0.0


@dataclass
class EvalReport:
    """Aggregated metrics for a completed EvalSuite run."""
    suite_name: str
    results: list[EvalResult]
    pass_threshold: float = 0.8

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def avg_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / self.total

    @property
    def errored(self) -> list[EvalResult]:
        return [r for r in self.results if r.error is not None]

    def summary(self) -> str:
        return (
            f"[{self.suite_name}] "
            f"{self.passed}/{self.total} passed ({self.pass_rate:.0%}) "
            f"| avg_score={self.avg_score:.2f} "
            f"| errors={len(self.errored)}"
        )


@dataclass
class EvalSuite:
    """Named collection of EvalCases for a specific capability."""
    name: str
    cases: list[EvalCase] = field(default_factory=list)

    def add(self, case: EvalCase) -> "EvalSuite":
        """Append a case and return self for chaining."""
        self.cases.append(case)
        return self


# ─── Scoring functions ────────────────────────────────────────────────────────

def score_exact_match(actual: Any, expected: Any) -> float:
    """Return 1.0 if actual == expected, else 0.0."""
    return 1.0 if actual == expected else 0.0


def score_contains(actual: Any, expected: str) -> float:
    """Return 1.0 if expected is a case-insensitive substring of actual, else 0.0."""
    if not isinstance(actual, str):
        return 0.0
    return 1.0 if expected.lower() in actual.lower() else 0.0


def score_all_present(actual: str, expected: list[str]) -> float:
    """Return the fraction of expected strings found (case-insensitive) in actual."""
    if not isinstance(actual, str) or not expected:
        return 0.0
    hits = sum(1 for e in expected if e.lower() in actual.lower())
    return hits / len(expected)


def score_intent(actual: dict, expected: str) -> float:
    """Score intent classification: 1.0 iff result['intent'] == expected."""
    return 1.0 if actual.get("intent") == expected else 0.0


def score_response_quality(actual: dict, expected: list[str]) -> float:
    """
    Score response completeness: fraction of expected phrases present
    in result['final_response'] (case-insensitive).
    """
    response = actual.get("final_response", "") or ""
    return score_all_present(response, expected)


def score_guardrail_raised(actual: dict, expected: type) -> float:
    """
    Score 1.0 if the eval fn raised an exception of type `expected`.
    EvalRunner captures exceptions as {'exception': <exc>}.
    """
    exc = actual.get("exception")
    return 1.0 if exc is not None and isinstance(exc, expected) else 0.0


def score_pii_masked(actual: dict, expected: list[str]) -> float:
    """
    Score PII masking: 1.0 if none of the PII strings in `expected`
    appear in result['final_response'].  Penalises leaks proportionally.
    """
    response = actual.get("final_response", "") or ""
    if not expected:
        return 1.0
    leaks = sum(1 for pii in expected if pii in response)
    return 1.0 - (leaks / len(expected))


# ─── EvalRunner ───────────────────────────────────────────────────────────────

class EvalRunner:
    """
    Orchestrates the execution of an EvalSuite and returns an EvalReport.

    Usage:
        runner = EvalRunner(fn=my_eval_wrapper)
        report = runner.run(suite, pass_threshold=0.8)
        print(report.summary())
    """

    def __init__(self, fn: Callable[..., Any]):
        """
        Args:
            fn: Function under evaluation.  Called with **case.input.
                Must return a dict.  Exceptions are caught and stored.
        """
        self._fn = fn

    def run(
        self,
        suite: EvalSuite,
        pass_threshold: float = 0.8,
    ) -> EvalReport:
        """Execute every EvalCase in suite and return an EvalReport."""
        results: list[EvalResult] = []
        for case in suite.cases:
            result = self._run_case(case, pass_threshold)
            results.append(result)
        return EvalReport(
            suite_name=suite.name,
            results=results,
            pass_threshold=pass_threshold,
        )

    def _run_case(self, case: EvalCase, threshold: float) -> EvalResult:
        """Execute one EvalCase, capturing exceptions and timing."""
        start = time.perf_counter()
        error: Optional[str] = None
        try:
            actual = self._fn(**case.input)
        except Exception as exc:
            actual = {"exception": exc}
            error = f"{type(exc).__name__}: {exc}"

        latency_ms = (time.perf_counter() - start) * 1000

        try:
            score = float(case.score_fn(actual, case.expected))
        except Exception as exc:
            score = 0.0
            error = (error or "") + f" | score_fn error: {exc}"

        return EvalResult(
            case_id=case.case_id,
            name=case.name,
            passed=score >= threshold,
            score=score,
            actual=actual,
            expected=case.expected,
            error=error,
            latency_ms=round(latency_ms, 2),
        )
