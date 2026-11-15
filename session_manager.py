"""
session_manager.py
Manages session state, conversation history formatting, strict repeated-question
reuse, atomic JSON session saving, and loading/displaying past sessions.
"""

from datetime import datetime, date
import json
import os
import re
from expense_tracker import new_tracker, money

SESSIONS_DIR = "sessions"
ELIGIBLE_REUSE_INTENTS = {"chat", "spending_enquiry", "advice"}


def new_session():
    """
    Create a fresh session dictionary containing start timestamp, empty history,
    empty structured tracker, zeroed statistics, and placeholders for report/summary.
    """
    now = datetime.now()
    date_prefix = now.strftime("%Y-%m-%d")
    return {
        "session_id": f"{date_prefix}-pending",
        "started": now.isoformat(timespec="seconds"),
        "ended": None,
        "history": [],
        "tracker": new_tracker(),
        "stats": {
            "api_calls": 0,
            "local_answers": 0,
            "reused_answers": 0,
        },
        "report": {},
        "summary": None,
        "summary_status": "pending",
        "_reusable_cache": {},
    }


def add_message(session, role, text):
    """
    Append an ordered message dictionary to session['history'] in Gemini format.
    Role must be 'user' or 'model'.
    """
    if role not in ("user", "model"):
        raise ValueError(f"Invalid message role: {role}")
    session["history"].append({
        "role": role,
        "parts": [{"text": str(text)}],
    })


def make_local_reply(text):
    """
    Wrap a local Python-calculated answer in the shared Gemini JSON response shape
    so it can be validated and stored cleanly in conversation history.
    """
    payload = {
        "intent": "spending_enquiry",
        "message": str(text),
        "expense": None,
        "query": {"category": "all"},
    }
    return json.dumps(payload)


def normalise_question(text):
    """Tidy a user question for repeated-question matching: lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s]", "", str(text).lower())
    return " ".join(cleaned.split())


def store_reusable_reply(session, text, reply_text, tracker):
    """Store an eligible Gemini reply in memory for potential reuse during the same session."""
    norm = normalise_question(text)
    if len(norm.split()) < 4:
        return

    try:
        parsed = json.loads(reply_text)
        intent = parsed.get("intent")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return

    if intent not in ELIGIBLE_REUSE_INTENTS:
        return

    cache = session.setdefault("_reusable_cache", {})
    cache[norm] = {
        "reply_text": reply_text,
        "tracker_version": tracker.get("version", 0),
        "date": date.today().isoformat(),
    }


def find_reusable_reply(session, text, tracker):
    """Return an earlier stored Gemini reply if the question, tracker version, and date match."""
    norm = normalise_question(text)
    if len(norm.split()) < 4:
        return None

    cache = session.get("_reusable_cache", {})
    entry = cache.get(norm)
    if not entry:
        return None

    current_version = tracker.get("version", 0)
    current_date = date.today().isoformat()

    if entry["tracker_version"] == current_version and entry["date"] == current_date:
        return entry["reply_text"]

    return None


def _next_session_filepath(date_str):
    """Find the next unused sequential filename: sessions/session_YYYY-MM-DD_NNN.json"""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    counter = 1
    while True:
        filename = f"session_{date_str}_{counter:03d}.json"
        filepath = os.path.join(SESSIONS_DIR, filename)
        if not os.path.exists(filepath):
            session_id = f"{date_str}-{counter:03d}"
            return filepath, session_id
        counter += 1


def save_session(session):
    """Safely save the session to a dated JSON file under sessions/ using atomic write."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    filepath, session_id = _next_session_filepath(date_str)
    session["session_id"] = session_id
    if not session.get("ended"):
        session["ended"] = now.isoformat(timespec="seconds")

    data_to_save = {
        "session_id": session["session_id"],
        "started": session.get("started"),
        "ended": session["ended"],
        "history": session.get("history", []),
        "tracker": session.get("tracker", {"expenses": [], "version": 0}),
        "stats": session.get("stats", {"api_calls": 0, "local_answers": 0, "reused_answers": 0}),
        "report": session.get("report", {}),
        "summary": session.get("summary"),
        "summary_status": session.get("summary_status", "unavailable" if not session.get("summary") else "ok"),
    }

    tmp_filepath = f"{filepath}.tmp"
    with open(tmp_filepath, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, indent=2, ensure_ascii=False)

    os.replace(tmp_filepath, filepath)
    return filepath


def list_sessions():
    """List all saved JSON sessions in sessions/ with metadata."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    files = sorted(
        f for f in os.listdir(SESSIONS_DIR)
        if f.endswith(".json") and not f.endswith(".tmp")
    )

    results = []
    for fname in files:
        fpath = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            started = str(data.get("started", ""))
            session_date = started[:10] if len(started) >= 10 else "Unknown"
            report = data.get("report") or {}
            expenses = (data.get("tracker") or {}).get("expenses", [])

            expense_count = report.get("expense_count", len(expenses))
            total_outflow = report.get(
                "total_outflow",
                sum(float(item.get("total_outflow", 0)) for item in expenses),
            )
            summary_status = data.get(
                "summary_status",
                "ok" if data.get("summary") else "unavailable",
            )

            results.append({
                "filename": fname,
                "date": session_date,
                "expense_count": expense_count,
                "total_outflow": round(float(total_outflow), 2),
                "summary_status": summary_status,
                "readable": True,
            })
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            results.append({
                "filename": fname,
                "date": "Unreadable",
                "expense_count": 0,
                "total_outflow": 0.0,
                "summary_status": "unreadable",
                "readable": False,
            })

    return results


def load_session(filename):
    """Safely load a saved session JSON file by filename or path."""
    filepath = filename if os.path.dirname(filename) else os.path.join(SESSIONS_DIR, filename)

    if not os.path.exists(filepath):
        return None, f"Session file '{filename}' was not found."

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read '{filename}' (file may be damaged or invalid JSON): {exc}"

    if not isinstance(data, dict):
        return None, f"Session file '{filename}' has an invalid format."

    data.setdefault("session_id", os.path.basename(filepath))
    data.setdefault("started", "Unknown")
    data.setdefault("ended", "Unknown")
    data.setdefault("history", [])
    data.setdefault("tracker", {"expenses": [], "version": 0})
    stats = data.setdefault("stats", {})
    stats.setdefault("api_calls", 0)
    stats.setdefault("local_answers", 0)
    stats.setdefault("reused_answers", 0)
    data.setdefault("report", {})
    data.setdefault("summary", None)
    data.setdefault("summary_status", "ok" if data.get("summary") else "unavailable")

    return data, None


def format_report(report):
    """Format the Python-calculated financial report into readable terminal lines."""
    if not report:
        return "No report figures available."

    lines = [
        "=== END-OF-SESSION EXPENSE REPORT ===",
        f"Total Expenses Recorded : {report.get('expense_count', 0)}",
        f"Total Purchase Amount   : {money(report.get('purchase_total', 0))}",
        f"Total Transaction Fees  : {money(report.get('fee_total', 0))}",
        f"Total Cash Outflow      : {money(report.get('total_outflow', 0))}",
    ]

    cat_breakdown = report.get("category_breakdown") or {}
    if cat_breakdown:
        lines.append("\n--- Spending by Category ---")
        for cat, info in cat_breakdown.items():
            label = cat.replace("_", " ").title()
            lines.append(f"  * {label:<18}: {money(info['amount'])} ({info['share_percent']}%)")

    pm_totals = report.get("payment_method_totals") or {}
    if pm_totals:
        lines.append("\n--- Outflow by Payment Method ---")
        for pm, amt in pm_totals.items():
            label = pm.replace("_", " ").title()
            lines.append(f"  * {label:<18}: {money(amt)}")

    largest = report.get("largest_expense")
    if largest:
        lines.append(
            f"\nLargest Single Expense  : {largest['description']} "
            f"({money(largest['amount'])}, {largest['category']})"
        )

    return "\n".join(lines)


def display_session(session):
    """Format a complete loaded session for terminal display."""
    lines = [
        f"==========================================",
        f"SESSION ID : {session.get('session_id', 'Unknown')}",
        f"STARTED    : {session.get('started', 'Unknown')}",
        f"ENDED      : {session.get('ended', 'Unknown')}",
        f"==========================================\n",
        "--- CONVERSATION HISTORY ---",
    ]

    history = session.get("history", [])
    if not history:
        lines.append("(No messages recorded)")
    else:
        for msg in history:
            role = msg.get("role", "unknown").upper()
            parts = msg.get("parts", [])
            raw_text = parts[0].get("text", "") if parts else ""
            if role == "MODEL":
                try:
                    parsed = json.loads(raw_text)
                    display_text = parsed.get("message", raw_text)
                except (json.JSONDecodeError, TypeError):
                    display_text = raw_text
            else:
                display_text = raw_text
            lines.append(f"[{role}]: {display_text}")

    lines.append("\n" + format_report(session.get("report", {})))

    lines.append("\n--- AI COACH SUMMARY & RECOMMENDATIONS ---")
    summary = session.get("summary")
    if summary and session.get("summary_status") == "ok":
        lines.append(f"Overview: {summary.get('overview', '')}")
        recs = summary.get("recommendations", [])
        for idx, rec in enumerate(recs, start=1):
            lines.append(f"  {idx}. {rec}")
    else:
        lines.append("AI summary unavailable for this session.")

    stats = session.get("stats", {})
    lines.append(
        f"\n[Stats] API calls: {stats.get('api_calls', 0)} | "
        f"Local Python answers: {stats.get('local_answers', 0)} | "
        f"Reused answers: {stats.get('reused_answers', 0)}"
    )

    return "\n".join(lines)