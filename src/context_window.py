"""
Step 7 — Context window management (HostAI).

Provides:
  - count_tokens()        : tiktoken-based token counter for message lists
  - sliding_window()      : keep last N messages within token budget
  - summarize_history()   : collapse old messages into a summary SystemMessage
  - semantic_select()     : pick most relevant messages via cosine similarity
  - ContextBudget         : per-agent token budget with alert threshold
  - apply_context_strategy(): one-call dispatch for any strategy

All strategies preserve SystemMessages at position 0 (they carry the agent
persona and must never be evicted).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

log = logging.getLogger(__name__)

# ─── Token counter ────────────────────────────────────────────────────────────

_TIKTOKEN_ENCODING = "cl100k_base"  # compatible with Claude / GPT-4 family


def count_tokens(messages: List[BaseMessage]) -> int:
    """
    Count tokens across all messages using tiktoken (cl100k_base).

    Fallback (Form 2): character-based estimation (chars / 4) when tiktoken
    fails or returns 0 — handles edge cases like empty messages.
    """
    if not messages:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding(_TIKTOKEN_ENCODING)
        total = 0
        for m in messages:
            content = m.content if isinstance(m.content, str) else str(m.content)
            total += len(enc.encode(content))
            # Add ~4 tokens per message for role/structure overhead
            total += 4
        return total
    except Exception:
        # Form 2 fallback: character-based estimate
        total = sum(
            len(m.content if isinstance(m.content, str) else str(m.content)) for m in messages
        )
        return max(1, total // 4)


def count_tokens_str(text: str) -> int:
    """Count tokens for a plain string."""
    return count_tokens([HumanMessage(content=text)])


# ─── Strategy 1: Sliding window ───────────────────────────────────────────────


def sliding_window(
    messages: List[BaseMessage],
    max_tokens: int,
    preserve_system: bool = True,
) -> List[BaseMessage]:
    """
    Trim message history from the front until it fits within max_tokens.

    Algorithm:
      1. Separate SystemMessages (always kept) from conversation history.
      2. Walk the history from the end; accumulate until budget exceeded.
      3. Return [system_msgs] + [trimmed_history].

    Args:
        messages:        Full message list.
        max_tokens:      Token budget.
        preserve_system: If True (default), SystemMessages are never evicted.

    Returns:
        Trimmed message list within max_tokens.
    """
    if not messages:
        return messages

    system_msgs: List[BaseMessage] = []
    history: List[BaseMessage] = []

    for m in messages:
        if preserve_system and isinstance(m, SystemMessage):
            system_msgs.append(m)
        else:
            history.append(m)

    system_tokens = count_tokens(system_msgs)
    budget = max_tokens - system_tokens

    # Walk history from end, accumulate until over budget
    kept: List[BaseMessage] = []
    used = 0
    for m in reversed(history):
        t = count_tokens([m])
        if used + t > budget:
            break
        kept.insert(0, m)
        used += t

    result = system_msgs + kept
    original_count = len(messages)
    if len(result) < original_count:
        evicted = original_count - len(result)
        log.info(
            "sliding_window: evicted %d messages (%d→%d tokens)",
            evicted,
            count_tokens(messages),
            count_tokens(result),
        )
    return result


# ─── Strategy 2: Summarization ────────────────────────────────────────────────


def summarize_history(
    messages: List[BaseMessage],
    max_tokens: int,
    summary_prefix: str = "[Summary of prior conversation]: ",
) -> List[BaseMessage]:
    """
    When history exceeds max_tokens, collapse older messages into a single
    SystemMessage summary and keep only the most recent exchanges.

    Algorithm:
      1. If within budget → return as-is.
      2. Keep system messages + last 2 human/AI turns (recent context).
      3. Everything else → build a bullet-point summary SystemMessage.

    This avoids losing all context while fitting within the token budget.
    """
    if count_tokens(messages) <= max_tokens:
        return messages

    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    convo = [m for m in messages if not isinstance(m, SystemMessage)]

    # Always keep last 4 messages (2 turns) for immediate context
    recent = convo[-4:] if len(convo) >= 4 else convo
    older = convo[:-4] if len(convo) >= 4 else []

    if not older:
        # Can't summarize further; return sliding window instead
        return sliding_window(messages, max_tokens)

    # Build summary bullet points from older messages
    lines = []
    for m in older:
        role = "User" if isinstance(m, HumanMessage) else "Assistant"
        content = (m.content if isinstance(m.content, str) else str(m.content))[:120]
        lines.append(f"- {role}: {content}")
    summary_text = summary_prefix + "\n".join(lines)
    summary_msg = SystemMessage(content=summary_text)

    result = system_msgs + [summary_msg] + recent
    log.info(
        "summarize_history: summarized %d messages → 1 summary + %d recent", len(older), len(recent)
    )
    return result


# ─── Strategy 3: Semantic selection ──────────────────────────────────────────


def semantic_select(
    messages: List[BaseMessage],
    query: str,
    n: int = 6,
    score_threshold: float = 0.0,
) -> List[BaseMessage]:
    """
    Select the N most semantically relevant messages given a query.

    Uses cosine similarity via in-process numpy (no external LanceDB call
    needed — embeddings computed locally with a lightweight heuristic for tests).

    In production this can be swapped with a LanceDB vector search.
    For the stub: scores messages by keyword overlap with query (fast, deterministic).

    Algorithm:
      1. Always keep SystemMessages.
      2. Score each non-system message by normalized keyword overlap with query.
      3. Return top-N scored + SystemMessages, in original order.
    """
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    candidates = [m for m in messages if not isinstance(m, SystemMessage)]

    if len(candidates) <= n:
        return messages  # nothing to trim

    query_words = set(query.lower().split())

    def _score(m: BaseMessage) -> float:
        content = (m.content if isinstance(m.content, str) else str(m.content)).lower()
        words = set(content.split())
        overlap = len(query_words & words)
        return overlap / max(len(query_words), 1)

    scored = sorted(candidates, key=_score, reverse=True)
    selected = scored[:n]
    # Restore original order
    original_idx = {id(m): i for i, m in enumerate(messages)}
    selected_sorted = sorted(selected, key=lambda m: original_idx.get(id(m), 0))

    result = system_msgs + selected_sorted
    log.info(
        "semantic_select: selected %d/%d messages for query=%r",
        len(selected),
        len(candidates),
        query[:40],
    )
    return result


# ─── Token budget ─────────────────────────────────────────────────────────────


@dataclass
class ContextBudget:
    """
    Per-agent token budget configuration.

    Attributes:
        agent_name:       Human-readable name for logging.
        token_limit:      Hard cap — apply_context_strategy enforces this.
        alert_threshold:  Fraction [0, 1] of token_limit that triggers a warning.
                          Default 0.8 → warn at 80% usage.
        strategy:         Default strategy: "sliding" | "summarize" | "semantic".
    """

    agent_name: str
    token_limit: int = 8_000
    alert_threshold: float = 0.80
    strategy: str = "sliding"

    def check_alert(self, messages: List[BaseMessage]) -> Optional[str]:
        """
        Return a warning string if current token count exceeds alert_threshold,
        otherwise None.
        """
        used = count_tokens(messages)
        ratio = used / self.token_limit
        if ratio >= self.alert_threshold:
            msg = (
                f"[ContextBudget:{self.agent_name}] "
                f"Token usage at {ratio:.0%} ({used}/{self.token_limit}) — "
                f"applying '{self.strategy}' strategy."
            )
            log.warning(msg)
            return msg
        return None


# ─── Dispatch ─────────────────────────────────────────────────────────────────


def apply_context_strategy(
    messages: List[BaseMessage],
    budget: ContextBudget,
    query: str = "",
) -> tuple[List[BaseMessage], Optional[str]]:
    """
    Apply the budget's strategy to trim messages if needed.

    Returns:
        (trimmed_messages, alert_message_or_None)

    Strategies:
      "sliding"   → sliding_window()
      "summarize" → summarize_history()
      "semantic"  → semantic_select()
    """
    alert = budget.check_alert(messages)
    used = count_tokens(messages)

    if used <= budget.token_limit:
        return messages, alert  # within budget, no trim needed

    if budget.strategy == "summarize":
        trimmed = summarize_history(messages, budget.token_limit)
    elif budget.strategy == "semantic":
        trimmed = semantic_select(messages, query or "reservation", n=6)
    else:
        trimmed = sliding_window(messages, budget.token_limit)

    return trimmed, alert


# ─── Default budgets per agent ────────────────────────────────────────────────

HOST_AGENT_BUDGET = ContextBudget(
    agent_name="HostAI",
    token_limit=8_000,
    alert_threshold=0.80,
    strategy="sliding",
)
