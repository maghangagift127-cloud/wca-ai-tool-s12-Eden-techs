"""Tests for response_validator.py (Member 1). Run: python -m pytest"""
import json
import sys
import types

import pytest

import response_validator as rv


def reply(**kw):
    base = {"intent": "chat", "message": "Hello", "expense": None, "query": None}
    base.update(kw)
    return json.dumps(base)


def expense(**kw):
    e = {"description": "Matatu fare", "amount": 300, "category": "transport",
         "payment_method": "send_money", "reported_fee": None}
    e.update(kw)
    return e


# ---- validate_reply: valid cases
def test_valid_chat():
    assert rv.validate_reply(reply())[0]

def test_valid_record_expense():
    assert rv.validate_reply(reply(intent="record_expense", expense=expense()))[0]

def test_zero_fee_is_valid():
    assert rv.validate_reply(reply(intent="record_expense", expense=expense(reported_fee=0)))[0]

def test_valid_spending_enquiry():
    assert rv.validate_reply(reply(intent="spending_enquiry", query={"category": "all"}))[0]
    assert rv.validate_reply(reply(intent="spending_enquiry", query={"category": "food"}))[0]

def test_code_fence_is_tolerated():
    assert rv.validate_reply("```json\n" + reply() + "\n```")[0]

# ---- validate_reply: invalid cases
@pytest.mark.parametrize("raw", ["", "   ", "not json", "[1, 2]", "42", None])
def test_bad_json_rejected(raw):
    assert not rv.validate_reply(raw)[0]

def test_missing_or_blank_message():
    assert not rv.validate_reply(json.dumps({"intent": "chat"}))[0]
    assert not rv.validate_reply(reply(message="  "))[0]

def test_unknown_intent():
    assert not rv.validate_reply(reply(intent="dance"))[0]

@pytest.mark.parametrize("amount", [0, -5, "300", None, True])
def test_bad_amount(amount):
    assert not rv.validate_reply(reply(intent="record_expense", expense=expense(amount=amount)))[0]

def test_bad_category_and_method():
    assert not rv.validate_reply(reply(intent="record_expense", expense=expense(category="pets")))[0]
    assert not rv.validate_reply(reply(intent="record_expense", expense=expense(payment_method="card")))[0]

def test_blank_description_and_missing_expense():
    assert not rv.validate_reply(reply(intent="record_expense", expense=expense(description=" ")))[0]
    assert not rv.validate_reply(reply(intent="record_expense"))[0]

def test_bad_reported_fee():
    assert not rv.validate_reply(reply(intent="record_expense", expense=expense(reported_fee=-1)))[0]
    assert not rv.validate_reply(reply(intent="record_expense", expense=expense(reported_fee="7")))[0]

def test_bad_query():
    assert not rv.validate_reply(reply(intent="spending_enquiry"))[0]
    assert not rv.validate_reply(reply(intent="spending_enquiry", query={"category": "pets"}))[0]


# ---- validate_summary
def summary(**kw):
    s = {"overview": "You spent most on transport.", "recommendations": ["a", "b", "c"]}
    s.update(kw)
    return json.dumps(s)

def test_valid_summary():
    assert rv.validate_summary(summary())[0]

def test_summary_needs_exactly_three_tips():
    assert not rv.validate_summary(summary(recommendations=["a", "b"]))[0]
    assert not rv.validate_summary(summary(recommendations=["a", "b", "c", "d"]))[0]

def test_summary_blank_parts_rejected():
    assert not rv.validate_summary(summary(overview=""))[0]
    assert not rv.validate_summary(summary(recommendations=["a", "", "c"]))[0]
    assert not rv.validate_summary("nope")[0]


# ---- retry behaviour, using a fake ai_client (no real API call)
@pytest.fixture
def fake_client(monkeypatch):
    mod = types.ModuleType("ai_client")
    mod.calls = []
    mod.queue = []

    def ask_model(history, facts=None):
        mod.calls.append((list(history), facts))
        item = mod.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def summarise(history, report):
        mod.calls.append((list(history), report))
        item = mod.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    mod.ask_model, mod.summarise = ask_model, summarise
    monkeypatch.setitem(sys.modules, "ai_client", mod)
    return mod

HISTORY = [{"role": "user", "parts": [{"text": "I spent KSh 300 on transport."}]}]

def test_first_valid_reply_makes_one_call(fake_client):
    fake_client.queue = [reply()]
    result = rv.get_valid_reply(HISTORY)
    assert result["ok"] and len(fake_client.calls) == 1

def test_invalid_then_valid_retries_once_with_full_history(fake_client):
    fake_client.queue = ["not json", reply()]
    result = rv.get_valid_reply(HISTORY, facts="Total: KSh 300")
    assert result["ok"] and len(fake_client.calls) == 2
    assert all(c[0] == HISTORY for c in fake_client.calls)        # full history both times
    assert "rejected" in fake_client.calls[1][1] and "Total: KSh 300" in fake_client.calls[1][1]

def test_two_failures_give_clear_error(fake_client):
    fake_client.queue = ["bad", "still bad"]
    result = rv.get_valid_reply(HISTORY)
    assert not result["ok"] and "could not get a valid answer" in result["error"]
    assert len(fake_client.calls) == 2                              # only one retry

def test_api_failure_does_not_crash(fake_client):
    fake_client.queue = [ConnectionError("no internet"), ConnectionError("no internet")]
    result = rv.get_valid_reply(HISTORY)
    assert not result["ok"] and "could not be reached" in result["error"]

def test_summary_retry(fake_client):
    fake_client.queue = [summary(recommendations=["a"]), summary()]
    result = rv.get_valid_summary(HISTORY, {"total": 300})
    assert result["ok"] and len(fake_client.calls) == 2
    assert all(c[0] == HISTORY and c[1] == {"total": 300} for c in fake_client.calls)
