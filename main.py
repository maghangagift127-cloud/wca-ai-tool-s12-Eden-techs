# main.py - the application entry point: menu, session loop, and the turn workflow.
# Owner: Member 1. Follows Section 7.1 of the build plan (order of a turn).
#
# process_turn() and finish_session() return results and never print, so the
# terminal (this file) and the Streamlit app can both use them.

import json
from datetime import datetime

import ai_client
import config
import expense_tracker
import response_validator
import session_manager

NOTICE = ("Do not type PINs, passwords, ID numbers or phone numbers. "
          "Your messages are saved in the session file.")
REPEAT_NOTE = "Repeated question: no new expenses since, so my earlier answer still applies."
REUSABLE_INTENTS = ["chat", "spending_enquiry", "advice"]


# ---------- small helpers ----------

# Formats a number as KSh text, or turns a dictionary of figures into readable text.
def format_figure(value):
    if isinstance(value, (int, float)):
        return expense_tracker.money(value)
    if isinstance(value, dict):
        return ", ".join(str(k) + ": " + format_figure(v) for k, v in value.items())
    return str(value)


# Describes a newly recorded expense in one line.
def describe_record(record):
    if not isinstance(record, dict):
        return "Expense recorded."
    text = "Expense recorded: " + str(record.get("description", ""))
    if "amount" in record:
        text += ", " + format_figure(record["amount"])
    if "fee" in record:
        text += ", fee " + format_figure(record["fee"])
    return text


# Builds the result dictionary for a reply that is shown to the user.
def make_result(data, source, extra=None):
    return {"kind": "reply", "source": source, "intent": data.get("intent"),
            "message": data["message"], "extra": extra or [], "note": None}


# Copies the real Gemini request count into the session statistics.
def update_api_count(session):
    session["stats"]["api_calls"] = ai_client.get_api_call_count()


# ---------- one turn of the conversation ----------

# Handles one user message in the order of Section 7.1 and returns a result (no printing).
def process_turn(session, text):
    text = (text or "").strip()
    if text == "":
        return {"kind": "empty", "message": "Please type something."}
    if text.lower() in config.END_WORDS:
        return {"kind": "end", "message": ""}

    tracker = session["tracker"]
    stats = session["stats"]
    session_manager.add_message(session, "user", text)

    # 1. Python answers simple questions from the expense records (no Gemini call).
    answer = expense_tracker.answer_local_question(tracker, text)
    if answer:
        reply_text = session_manager.make_local_reply(answer)
        ok, data, _error = response_validator.validate_reply(reply_text)
        if ok:
            session_manager.add_message(session, "model", reply_text)
            stats["local_answers"] += 1
            return make_result(data, "local")

    # 2. Reuse an earlier answer if the same question was asked and nothing has changed.
    old_reply = session_manager.find_reusable_reply(session, text, tracker)
    if old_reply:
        ok, data, _error = response_validator.validate_reply(old_reply)
        if ok:
            session_manager.add_message(session, "model", old_reply)
            stats["reused_answers"] += 1
            result = make_result(data, "reused")
            result["note"] = REPEAT_NOTE
            return result

    # 3. Ask Gemini with the FULL history (one retry happens inside get_valid_reply).
    facts = expense_tracker.build_facts(tracker)
    result = response_validator.get_valid_reply(session["history"], facts)
    update_api_count(session)
    if not result["ok"]:
        session["history"].pop()          # remove the user message so the history stays in order
        return {"kind": "error", "message": result["error"]}

    data = result["data"]
    session_manager.add_message(session, "model", result["raw"])
    extra = []

    # 4. Act on what Gemini understood.
    if data["intent"] == "record_expense":
        try:
            record = expense_tracker.add_expense(tracker, data["expense"])
            extra.append(describe_record(record))
        except Exception as problem:
            extra.append("Sorry, I could not record that expense: " + str(problem))
    elif data["intent"] == "spending_enquiry":
        category = data["query"]["category"]
        if category == "all":
            figure = expense_tracker.get_totals(tracker)
        else:
            figure = expense_tracker.get_category_total(tracker, category)
        extra.append("Calculated by the tool: " + format_figure(figure))

    # 5. Remember eligible answers so an identical repeated question can reuse them.
    if data["intent"] in REUSABLE_INTENTS:
        session_manager.store_reusable_reply(session, text, result["raw"], tracker)

    return make_result(data, "gemini", extra)


# ---------- ending a session ----------

# Builds the report, gets the AI summary, saves the session file and returns everything.
def finish_session(session):
    tracker = session["tracker"]
    report = expense_tracker.build_report(tracker)
    session["report"] = report
    session["ended"] = datetime.now().isoformat(timespec="seconds")

    summary_error = None
    session["summary"] = None
    session["summary_status"] = "unavailable"
    if len(session["history"]) == 0:
        summary_error = "Nothing was recorded, so there is no summary."
    else:
        result = response_validator.get_valid_summary(session["history"], report)
        update_api_count(session)
        if result["ok"]:
            session["summary"] = result["data"]
            session["summary_status"] = "ok"
        else:
            summary_error = result["error"]

    try:
        saved_file = session_manager.save_session(session)
    except Exception as problem:
        saved_file = None
        summary_error = (summary_error or "") + " The session could not be saved: " + str(problem)

    return {"report": report, "summary": session["summary"],
            "summary_status": session["summary_status"],
            "error": summary_error, "file": saved_file}


# ---------- terminal screens ----------

# Prints one result from process_turn().
def show_result(result):
    if result["kind"] in ("empty", "error"):
        print(result["message"])
        return
    print("Coach:", result["message"])
    for line in result["extra"]:
        print("   ", line)
    if result["note"]:
        print("   ", result["note"])


# Prints the report, the AI summary and where the file was saved.
def show_end(outcome):
    print("\n===== Session report =====")
    text = session_manager.format_report(outcome["report"])
    if text:
        print(text)
    if outcome["summary"]:
        print("\n" + outcome["summary"]["overview"])
        for number, tip in enumerate(outcome["summary"]["recommendations"], 1):
            print(str(number) + ". " + tip)
    if outcome["error"]:
        print("\nNote:", outcome["error"])
    if outcome["file"]:
        print("\nSession saved to:", outcome["file"])


# Shows the three menu choices and returns what the user typed.
def show_menu():
    print("\n=== M-Pesa Expense Coach ===")
    print("1. Start a new session")
    print("2. Open a past session")
    print("3. Exit")
    try:
        return input("Choose 1, 2 or 3: ").strip()
    except (EOFError, KeyboardInterrupt):
        return "3"


# Runs one live session: reads messages until the user ends it, then finishes it.
def run_session(session):
    print("\n" + NOTICE)
    print("Tell me what you spent. Type 'end' when you are done.")
    while True:
        try:
            text = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nEnding the session.")
            text = "end"
        try:
            result = process_turn(session, text)
        except Exception as problem:      # the program must never crash on a turn
            print("Something went wrong:", problem)
            continue
        if result["kind"] == "end":
            break
        show_result(result)
    show_end(finish_session(session))


# Starts a new, empty session.
def start_new_session():
    ai_client.reset_api_call_count()
    session = session_manager.new_session()
    run_session(session)


# Lists saved sessions, lets the user pick one and displays it (no Gemini call).
def open_past_session():
    try:
        entries = session_manager.list_sessions()
    except Exception as problem:
        print("Could not list sessions:", problem)
        return
    if not entries:
        print("No saved sessions yet.")
        return
    for number, entry in enumerate(entries, 1):
        print(str(number) + ". " + str(entry))
    choice = input("Choose a number (or press Enter to go back): ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(entries):
        print("Going back to the menu.")
        return
    entry = entries[int(choice) - 1]
    name = str(entry)
    if isinstance(entry, dict):
        name = entry.get("file") or entry.get("filename") or name
    try:
        saved = session_manager.load_session(name)
        text = session_manager.display_session(saved)
    except Exception as problem:
        print("Could not open that session:", problem)
        return
    if text:
        print(text)


# The menu loop that keeps the program running until the user chooses Exit.
def main():
    while True:
        choice = show_menu()
        if choice == "1":
            start_new_session()
        elif choice == "2":
            open_past_session()
        elif choice == "3":
            print("Goodbye.")
            break
        else:
            print("Please type 1, 2 or 3.")


if __name__ == "__main__":
    main()
