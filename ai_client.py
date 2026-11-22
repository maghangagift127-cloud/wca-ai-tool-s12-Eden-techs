# ai_client.py - the only file that talks to the AI (Claude). It sends the full history
# with the system prompt and returns the reply text.

import os

import anthropic
from dotenv import load_dotenv

import config
from prompts import CHAT_PROMPT, SUMMARY_PROMPT

# Load the API key from the .env file (it is never written in the code).
load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Counts the AI calls made in this session.
_api_call_count = 0


# Creates the Claude client, or raises a clear error when the key is missing.
def _get_client():
    if not API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is missing from .env")
    return anthropic.Anthropic(api_key=API_KEY)


# Converts our saved history (roles user/model, text in "parts") into Claude messages (roles user/assistant).
def _prepare_history(history):
    messages = []
    for item in history:
        role = "user"
        if item["role"] == "model":
            role = "assistant"
        text = ""
        for part in item["parts"]:
            text = text + part["text"]
        messages.append({"role": role, "content": text})
    return messages


# Sends the messages with a system prompt to Claude and returns the reply text.
def _call_claude(messages, system_prompt):
    global _api_call_count
    client = _get_client()
    _api_call_count = _api_call_count + 1
    response = client.messages.create(
        model=config.MODEL_NAME,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


# Chat call: sends the FULL conversation history with the chat prompt.
def ask_model(history):
    return _call_claude(_prepare_history(history), CHAT_PROMPT)


# Summary call: sends the full history plus the Python report with the summary prompt.
def summarise(history, report):
    messages = _prepare_history(history)
    messages.append({"role": "user", "content": "Please summarise this expense report:\n" + str(report)})
    return _call_claude(messages, SUMMARY_PROMPT)


# Returns how many AI calls were made.
def get_api_call_count():
    return _api_call_count


# Resets the call counter when a new session starts.
def reset_api_call_count():
    global _api_call_count
    _api_call_count = 0
