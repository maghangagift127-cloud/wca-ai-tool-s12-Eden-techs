
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

import config
from prompts import CHAT_PROMPT, SUMMARY_PROMPT


# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

# Count Gemini API calls
_api_call_count = 0


def _get_client():
    """Create a Gemini client using the environment API key."""
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY is missing from .env")

    return genai.Client(api_key=API_KEY)


def _prepare_history(history):
    """Convert application history into Gemini Content objects."""
    return [
        types.Content(
            role=item["role"],
            parts=[
                types.Part.from_text(text=part["text"])
                for part in item["parts"]
            ],
        )
        for item in history
    ]


def ask_model(history):
    """Send the full conversation history to Gemini."""
    global _api_call_count

    client = _get_client()
    contents = _prepare_history(history)

    _api_call_count += 1

    response = client.models.generate_content(
        model=config.MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=config.MODEL_TEMPERATURE,
            system_instruction=CHAT_PROMPT,
        ),
    )

    return response.text


def summarise(history, report):
    """Generate a final summary using conversation history and report."""
    global _api_call_count

    client = _get_client()

    contents = _prepare_history(history)

    # Include the completed expense report in the final request.
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=f"Please summarise this expense report:\n{report}"
                )
            ],
        )
    )

    _api_call_count += 1

    response = client.models.generate_content(
        model=config.MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=config.MODEL_TEMPERATURE,
            system_instruction=SUMMARY_PROMPT,
        ),
    )

    return response.text


def get_api_call_count():
    """Return the number of Gemini API calls made."""
    return _api_call_count


def reset_api_call_count():
    """Reset the Gemini API call counter."""
    global _api_call_count
    _api_call_count = 0
