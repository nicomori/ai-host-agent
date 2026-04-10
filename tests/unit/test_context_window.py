"""
Step 7 — Context window management tests (ai-host-agent).

7 test cases covering:
  TC1: count_tokens returns positive int
  TC2: sliding_window trims from front, preserves SystemMessages
  TC3: sliding_window no-op when within budget
  TC4: summarize_history collapses old messages to SystemMessage
  TC5: semantic_select returns top-N by keyword match
  TC6: ContextBudget.check_alert fires at threshold, silent below
  TC7: apply_context_strategy dispatches correctly + returns alert
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.context_window import (
    ContextBudget,
    HOST_AGENT_BUDGET,
    apply_context_strategy,
    count_tokens,
    count_tokens_str,
    semantic_select,
    sliding_window,
    summarize_history,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_history(n: int, prefix: str = "message") -> list:
    """Build alternating Human/AI messages."""
    msgs = []
    for i in range(n):
        if i % 2 == 0:
            msgs.append(HumanMessage(content=f"{prefix} human {i}"))
        else:
            msgs.append(AIMessage(content=f"{prefix} ai {i}"))
    return msgs


def _sys(content: str = "You are a helpful assistant.") -> SystemMessage:
    return SystemMessage(content=content)


# ══════════════════════════════════════════════════════════════════════════════
# TC1 — count_tokens returns positive integer for any non-empty messages
# ══════════════════════════════════════════════════════════════════════════════


def test_tc1_count_tokens_positive():
    msgs = [HumanMessage(content="Hello"), AIMessage(content="Hi there!")]
    result = count_tokens(msgs)
    assert isinstance(result, int)
    assert result > 0


def test_tc1_count_tokens_str_positive():
    result = count_tokens_str("Make a reservation for two at 7pm")
    assert isinstance(result, int)
    assert result > 0


def test_tc1_count_tokens_empty_list():
    result = count_tokens([])
    assert result == 0


# ══════════════════════════════════════════════════════════════════════════════
# TC2 — sliding_window: trims old messages, always preserves SystemMessages
# ══════════════════════════════════════════════════════════════════════════════


def test_tc2_sliding_window_trims_old_messages():
    sys_msg = _sys()
    # Long history — each message ~5 tokens; set tight budget
    history = [HumanMessage(content=f"human turn {i} with some words") for i in range(20)]
    msgs = [sys_msg] + history

    budget = 50  # intentionally small
    result = sliding_window(msgs, max_tokens=budget)

    # Result must fit within budget
    assert count_tokens(result) <= budget
    # SystemMessage always preserved
    assert any(isinstance(m, SystemMessage) for m in result)
    # Some messages were trimmed
    assert len(result) < len(msgs)


def test_tc2_sliding_window_preserves_recent_over_old():
    sys_msg = _sys()
    old = HumanMessage(content="old message from long ago")
    recent = HumanMessage(content="very recent message about reservation")
    msgs = [sys_msg, old, recent]

    # Budget just enough for sys + recent
    budget = count_tokens([sys_msg, recent]) + 2
    result = sliding_window(msgs, max_tokens=budget)
    contents = [m.content for m in result]

    assert recent.content in contents
    assert old.content not in contents


# ══════════════════════════════════════════════════════════════════════════════
# TC3 — sliding_window: no-op when already within budget
# ══════════════════════════════════════════════════════════════════════════════


def test_tc3_sliding_window_noop_within_budget():
    msgs = [_sys(), HumanMessage(content="book a table"), AIMessage(content="Sure!")]
    original_len = len(msgs)
    result = sliding_window(msgs, max_tokens=10_000)
    assert len(result) == original_len


def test_tc3_sliding_window_empty():
    result = sliding_window([], max_tokens=100)
    assert result == []


# ══════════════════════════════════════════════════════════════════════════════
# TC4 — summarize_history: collapses old messages into SystemMessage summary
# ══════════════════════════════════════════════════════════════════════════════


def test_tc4_summarize_history_creates_summary():
    sys_msg = _sys()
    # 8 conversation messages → older ones get summarized
    history = _build_history(8, prefix="reservation talk")
    msgs = [sys_msg] + history

    # Set budget so it needs to summarize
    budget = count_tokens([sys_msg]) + count_tokens(history[-4:]) + 10
    result = summarize_history(msgs, max_tokens=budget)

    # Should have a SystemMessage summary
    system_msgs = [m for m in result if isinstance(m, SystemMessage)]
    summary_msgs = [m for m in system_msgs if "Summary" in m.content]
    assert len(summary_msgs) >= 1


def test_tc4_summarize_history_noop_within_budget():
    msgs = [_sys(), HumanMessage(content="hi"), AIMessage(content="hello")]
    result = summarize_history(msgs, max_tokens=10_000)
    assert len(result) == len(msgs)


# ══════════════════════════════════════════════════════════════════════════════
# TC5 — semantic_select: returns top-N most relevant messages
# ══════════════════════════════════════════════════════════════════════════════


def test_tc5_semantic_select_returns_top_n():
    sys_msg = _sys()
    msgs = [sys_msg]
    msgs += [HumanMessage(content=f"reservation table booking restaurant {i}") for i in range(5)]
    msgs += [HumanMessage(content=f"unrelated topic weather sports {i}") for i in range(5)]

    result = semantic_select(msgs, query="reservation booking", n=3)

    non_system = [m for m in result if not isinstance(m, SystemMessage)]
    assert len(non_system) == 3
    # Reservation-related messages should score higher
    assert all("reservation" in m.content or "booking" in m.content for m in non_system)


def test_tc5_semantic_select_noop_when_few_msgs():
    msgs = [_sys(), HumanMessage(content="book a table")]
    result = semantic_select(msgs, query="reservation", n=6)
    assert len(result) == len(msgs)  # nothing trimmed


# ══════════════════════════════════════════════════════════════════════════════
# TC6 — ContextBudget: alert fires at threshold, silent below
# ══════════════════════════════════════════════════════════════════════════════


def test_tc6_context_budget_alert_at_threshold():
    # Very low token limit so 2 messages exceed 80%
    budget = ContextBudget(agent_name="TestAgent", token_limit=10, alert_threshold=0.80)
    msgs = [HumanMessage(content="Hello there, I need a reservation tonight please")]
    alert = budget.check_alert(msgs)
    assert alert is not None
    assert "TestAgent" in alert
    assert "%" in alert


def test_tc6_context_budget_no_alert_below_threshold():
    budget = ContextBudget(agent_name="TestAgent", token_limit=100_000, alert_threshold=0.80)
    msgs = [HumanMessage(content="Hi")]
    alert = budget.check_alert(msgs)
    assert alert is None


def test_tc6_host_agent_budget_defaults():
    assert HOST_AGENT_BUDGET.agent_name == "HostAI"
    assert HOST_AGENT_BUDGET.token_limit == 8_000
    assert HOST_AGENT_BUDGET.alert_threshold == 0.80
    assert HOST_AGENT_BUDGET.strategy == "sliding"


# ══════════════════════════════════════════════════════════════════════════════
# TC7 — apply_context_strategy: dispatches by strategy, returns (msgs, alert)
# ══════════════════════════════════════════════════════════════════════════════


def test_tc7_apply_strategy_within_budget_no_trim():
    budget = ContextBudget(agent_name="A", token_limit=10_000, strategy="sliding")
    msgs = [_sys(), HumanMessage(content="hello")]
    result_msgs, alert = apply_context_strategy(msgs, budget)
    assert result_msgs is msgs  # no copy — returned as-is


def test_tc7_apply_strategy_sliding_trims():
    budget = ContextBudget(agent_name="A", token_limit=30, strategy="sliding")
    msgs = [_sys()] + [
        HumanMessage(content=f"word word word {i} extra padding here") for i in range(10)
    ]
    result_msgs, _alert = apply_context_strategy(msgs, budget)
    assert count_tokens(result_msgs) <= budget.token_limit


def test_tc7_apply_strategy_summarize():
    budget = ContextBudget(agent_name="A", token_limit=100, strategy="summarize")
    sys_msg = _sys()
    history = _build_history(10, prefix="long detailed message about booking")
    msgs = [sys_msg] + history
    result_msgs, _alert = apply_context_strategy(msgs, budget, query="booking")
    assert count_tokens(result_msgs) <= budget.token_limit or len(result_msgs) < len(msgs)


def test_tc7_apply_strategy_semantic():
    budget = ContextBudget(agent_name="A", token_limit=50, strategy="semantic")
    sys_msg = _sys()
    msgs = [sys_msg]
    msgs += [HumanMessage(content=f"table reservation restaurant booking {i}") for i in range(8)]
    result_msgs, _alert = apply_context_strategy(msgs, budget, query="reservation")
    non_system = [m for m in result_msgs if not isinstance(m, SystemMessage)]
    # semantic_select caps at n=6
    assert len(non_system) <= 6
