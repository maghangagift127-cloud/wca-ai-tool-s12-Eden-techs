# app_streamlit.py - the browser version of the coach. Run: streamlit run app_streamlit.py
# It reuses main.py (process_turn, finish_session), so there is no extra logic here.

import os

import streamlit as st

import ai_client
import expense_tracker
import main
import session_manager

st.set_page_config(page_title="M-Pesa Expense Coach", page_icon="💰")
st.title("💰 M-Pesa Expense Coach")
st.caption(main.NOTICE)


# Starts a fresh session and clears the chat on screen.
def start_new():
    ai_client.reset_api_call_count()
    st.session_state.session = session_manager.new_session()
    st.session_state.chat = []
    st.session_state.outcome = None
    st.session_state.viewed = None


# Streamlit re-runs this file on every click, so the session is kept in session_state.
if "session" not in st.session_state:
    start_new()

session = st.session_state.session
tracker = session["tracker"]

# Sidebar buttons: new session and end session.
st.sidebar.button("New session", on_click=start_new)
end_clicked = st.sidebar.button("End session", disabled=st.session_state.outcome != None)

# Budget: the user types a limit (0 = no limit); the progress bar is filled in below.
budget = st.sidebar.number_input("Budget in KSh (0 = no limit)", min_value=0, step=1000, value=0)
budget_box = st.sidebar.container()

# Handle a new message from the chat box.
text = st.chat_input("Tell me what you spent", disabled=st.session_state.outcome != None)
if text:
    st.session_state.chat.append(("user", text))
    with st.spinner("Thinking..."):
        result = main.process_turn(session, text)
    if result["kind"] == "end":
        end_clicked = True
    else:
        reply = result["message"]
        for line in result["extra"]:
            reply = reply + "\n\n" + line
        st.session_state.chat.append(("assistant", reply))

# End the session: report, three tips and the saved file.
if end_clicked and st.session_state.outcome == None:
    with st.spinner("Writing your summary..."):
        st.session_state.outcome = main.finish_session(session)

# Show a short help box until the first message.
if len(st.session_state.chat) == 0:
    st.info("Try: I spent 200 on transport via send money")

# Show the conversation.
for who, message in st.session_state.chat:
    st.chat_message(who).write(message)

# Show every recorded expense in a small table.
if len(tracker["expenses"]) > 0:
    with st.expander("Recorded expenses (" + str(len(tracker["expenses"])) + ")"):
        rows = []
        for item in tracker["expenses"]:
            rows.append({
                "Description": item["description"],
                "Amount": expense_tracker.money(item["amount"]),
                "Fee": expense_tracker.money(item["fee"]),
                "Paid by": item["payment_method"].replace("_", " "),
            })
        st.table(rows)

# Show the report after the session has ended.
outcome = st.session_state.outcome
if outcome != None:
    report = outcome["report"]
    st.subheader("Session report")
    col1, col2, col3 = st.columns(3)
    col1.metric("Spending", expense_tracker.money(report["purchase_total"]))
    col2.metric("Fees", expense_tracker.money(report["fee_total"]))
    col3.metric("Total outflow", expense_tracker.money(report["total_outflow"]))

    names = []
    amounts = []
    for category in report["category_breakdown"]:
        names.append(category.replace("_", " ").title())
        amounts.append(report["category_breakdown"][category]["amount"])
    if len(names) > 0:
        st.bar_chart({"Category": names, "KSh": amounts}, x="Category", y="KSh")

    if outcome["summary"] != None:
        st.write(outcome["summary"]["overview"])
        number = 1
        for tip in outcome["summary"]["recommendations"]:
            st.write(str(number) + ". " + tip)
            number = number + 1
    if outcome["error"] != None:
        st.warning(outcome["error"])
    if outcome["file"] != None:
        st.success("Session saved to: " + str(outcome["file"]))
        with open(outcome["file"], "r", encoding="utf-8") as saved:
            st.download_button("Download session file", saved.read(), file_name=os.path.basename(outcome["file"]))

# Budget bar (calculated by Python from the recorded expenses).
totals = expense_tracker.get_totals(tracker)
if budget > 0:
    used = totals["total_outflow"]
    budget_box.progress(min(used / budget, 1.0))
    budget_box.write(expense_tracker.money(used) + " of " + expense_tracker.money(budget) + " used")
    if used > budget:
        budget_box.error("Over budget by " + expense_tracker.money(used - budget))

# Sidebar: open a past session (no Gemini call). Newest first, with a readable label.
st.sidebar.divider()
st.sidebar.subheader("Past sessions")
labels = {}
number = 1
for entry in session_manager.list_sessions():
    label = "#" + str(number) + "  " + entry["date"] + "  " + expense_tracker.money(entry["total_outflow"])
    labels[label] = entry["filename"]
    number = number + 1
if len(labels) == 0:
    st.sidebar.write("None yet.")
else:
    options = list(labels)
    options.reverse()
    chosen = st.sidebar.selectbox("Open one", options)
    if st.sidebar.button("Show"):
        loaded = session_manager.load_session(labels[chosen])
        if loaded[0] == None:
            st.session_state.viewed = loaded[1]
        else:
            kept = []
            for line in session_manager.display_session(loaded[0]).split("\n"):
                if not line.startswith("[Stats]"):  # the API counters are not shown in the browser
                    kept.append(line)
            st.session_state.viewed = "\n".join(kept)

# Show the past session in the main area (it is long, so not in the sidebar).
if st.session_state.viewed != None:
    with st.expander("Past session", expanded=True):
        st.text(st.session_state.viewed)
