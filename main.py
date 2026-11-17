# main.py - the menu, the conversation loop and the end of a session.
# process_turn() and finish_session() return results and never print,
# so the terminal and a later Streamlit page can both use them.

import ai_client
import config
import expense_tracker
import response_validator
import session_manager

NOTICE = "Do not type PINs, passwords, ID numbers or phone numbers. Your messages are saved in the session file."


# Handles one user message and returns a dictionary with kind, message and extra lines.
def process_turn(session, text):
    text = text.strip()
    if text == "":
        return {"kind": "empty", "message": "Please type something.", "extra": []}
    if text.lower() in config.END_WORDS:
        return {"kind": "end", "message": "", "extra": []}

    tracker = session["tracker"]
    session_manager.add_message(session, "user", text)

    # Python answers simple spending questions itself (no Gemini call).
    answer = expense_tracker.answer_local_question(tracker, text)
    if answer != None:
        reply_text = session_manager.make_local_reply(answer)
        check = response_validator.validate_reply(reply_text)
        if check["ok"]:
            session_manager.add_message(session, "model", reply_text)
            session["stats"]["local_answers"] = session["stats"]["local_answers"] + 1
            return {"kind": "reply", "message": check["data"]["message"], "extra": []}

    # Otherwise ask Gemini with the FULL history (one retry happens inside).
    result = response_validator.get_valid_reply(session["history"])
    session["stats"]["api_calls"] = ai_client.get_api_call_count()
    if not result["ok"]:
        session["history"].pop()  # remove the user message so the history stays in order
        return {"kind": "error", "message": result["error"], "extra": []}

    data = result["data"]
    session_manager.add_message(session, "model", result["raw"])
    extra = []

    # Act on what Gemini understood.
    if data["intent"] == "record_expense":
        for expense in data["expenses"]:
            try:
                record = expense_tracker.add_expense(tracker, expense)
                extra.append("Expense recorded: " + str(record.get("description")) + ", " + expense_tracker.money(record.get("amount")) + ", fee " + expense_tracker.money(record.get("fee")))
            except Exception as problem:
                extra.append("Sorry, I could not record that expense: " + str(problem))

    if data["intent"] == "spending_enquiry":
        category = data["query"]["category"]
        if category == "all":
            totals = expense_tracker.get_totals(tracker)
            line = "Spending " + expense_tracker.money(totals["purchase_total"])
            line = line + ", fees " + expense_tracker.money(totals["fee_total"])
            line = line + ", total outflow " + expense_tracker.money(totals["total_outflow"])
        else:
            line = category + ": " + expense_tracker.money(expense_tracker.get_category_total(tracker, category))
        extra.append("Calculated by the tool: " + line)

    return {"kind": "reply", "message": data["message"], "extra": extra}


# Builds the report, gets the AI summary, saves the session and returns everything.
def finish_session(session):
    report = expense_tracker.build_report(session["tracker"])
    session["report"] = report
    session["summary"] = None
    session["summary_status"] = "unavailable"
    error = None

    if len(session["history"]) == 0:
        error = "Nothing was recorded, so there is no summary."
    else:
        result = response_validator.get_valid_summary(session["history"], report)
        session["stats"]["api_calls"] = ai_client.get_api_call_count()
        if result["ok"]:
            session["summary"] = result["data"]
            session["summary_status"] = "ok"
        else:
            error = result["error"]

    saved_file = None
    try:
        saved_file = session_manager.save_session(session)
    except Exception as problem:
        error = "The session could not be saved: " + str(problem)

    return {"report": report, "summary": session["summary"], "error": error, "file": saved_file}


# Prints one reply from process_turn().
def show_result(result):
    if result["kind"] == "reply":
        print("Coach:", result["message"])
        for line in result["extra"]:
            print("   ", line)
    else:
        print(result["message"])


# Prints the report, the three tips and where the session was saved.
def show_end(outcome):
    print("\n===== Session report =====")
    print(session_manager.format_report(outcome["report"]))
    if outcome["summary"] != None:
        print("\n" + outcome["summary"]["overview"])
        number = 1
        for tip in outcome["summary"]["recommendations"]:
            print(str(number) + ". " + tip)
            number = number + 1
    if outcome["error"] != None:
        print("\nNote:", outcome["error"])
    if outcome["file"] != None:
        print("\nSession saved to:", outcome["file"])


# Shows the three menu choices and returns what the user typed.
def show_menu():
    print("\n=== M-Pesa Expense Coach ===")
    print("1. Start a new session")
    print("2. Open a past session")
    print("3. Exit")
    try:
        return input("Choose 1, 2 or 3: ").strip()
    except:  # Ctrl+C or a closed input: treat it as Exit
        return "3"


# Runs one live session: reads messages until the user types an end word.
def run_session(session):
    print("\n" + NOTICE)
    print("Tell me what you spent. Type 'end' when you are done.")
    while True:
        try:
            text = input("\nYou: ")
        except:  # Ctrl+C or a closed input: end the session
            text = "end"
        try:
            result = process_turn(session, text)
        except Exception as problem:  # the program must never crash on a turn
            print("Something went wrong:", problem)
            continue
        if result["kind"] == "end":
            break
        show_result(result)
    show_end(finish_session(session))


# Starts a new session with a reset API-call counter.
def start_new_session():
    ai_client.reset_api_call_count()
    session = session_manager.new_session()
    run_session(session)


# Lists saved sessions, lets the user pick one and displays it (no Gemini call).
def open_past_session():
    try:
        files = session_manager.list_sessions()
    except Exception as problem:
        print("Could not list sessions:", problem)
        return
    if len(files) == 0:
        print("No saved sessions yet.")
        return

    number = 1
    for entry in files:
        line = str(number) + ". " + entry["filename"] + " | " + entry["date"]
        line = line + " | expenses: " + str(entry["expense_count"])
        line = line + " | total: " + expense_tracker.money(entry["total_outflow"])
        print(line)
        number = number + 1

    try:
        choice = int(input("Choose a number: "))
    except ValueError:
        print("That was not a number. Going back to the menu.")
        return
    if choice < 1 or choice > len(files):
        print("That number is not in the list.")
        return

    try:
        loaded = session_manager.load_session(files[choice - 1]["filename"])
        if loaded[0] == None:
            print(loaded[1])  # a clear message: file missing or damaged
        else:
            print(session_manager.display_session(loaded[0]))
    except Exception as problem:
        print("Could not open that session:", problem)


# The menu loop: repeats until the user chooses Exit.
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
