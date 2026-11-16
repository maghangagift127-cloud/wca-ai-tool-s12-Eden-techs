# app_streamlit.py - the browser version of the coach. Run: streamlit run app_streamlit.py
# It reuses main.py (process_turn, finish_session), so there is no extra logic here.

import streamlit as st

import ai_client
import main
import session_manager

st.title("M-Pesa Expense Coach")
st.caption(main.NOTICE)


# Starts a fresh session and clears the chat on screen.
def start_new():
    ai_client.reset_api_call_count()
    st.session_state.session = session_manager.new_session()
    st.session_state.chat = []
    st.session_state.outcome = None


# Streamlit re-runs this file on every click, so the session is kept in session_state.
if "session" not in st.session_state:
    start_new()

session = st.session_state.session

# Sidebar: new session and end session buttons.
st.sidebar.button("New session", on_click=start_new)
end_clicked = st.sidebar.button("End session", disabled=st.session_state.outcome != None)

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

# Show the conversation.
for who, message in st.session_state.chat:
    st.chat_message(who).write(message)

# Show the report after the session has ended.
outcome = st.session_state.outcome
if outcome != None:
    st.subheader("Session report")
    st.text(session_manager.format_report(outcome["report"]))
    if outcome["summary"] != None:
        st.write(outcome["summary"]["overview"])
        for tip in outcome["summary"]["recommendations"]:
            st.write("- " + tip)
    if outcome["error"] != None:
        st.warning(outcome["error"])
    if outcome["file"] != None:
        st.success("Session saved to: " + str(outcome["file"]))

# Sidebar: counters (drawn last so they are up to date), then past sessions.
st.sidebar.write("API calls: " + str(session["stats"]["api_calls"]))
st.sidebar.write("Answered locally: " + str(session["stats"]["local_answers"]))
st.sidebar.divider()
st.sidebar.subheader("Past sessions")
names = []
for entry in session_manager.list_sessions():
    names.append(entry["filename"])
if len(names) == 0:
    st.sidebar.write("None yet.")
else:
    chosen = st.sidebar.selectbox("Open one", names)
    if st.sidebar.button("Show"):
        loaded = session_manager.load_session(chosen)
        if loaded[0] == None:
            st.sidebar.warning(loaded[1])
        else:
            st.sidebar.text(session_manager.display_session(loaded[0]))
