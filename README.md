# M-Pesa Expense Coach

A menu-driven Python tool where you tell an AI assistant (Google Gemini) what you spent, in everyday language, over several turns. It remembers the whole conversation, keeps running totals and M-Pesa fees, and at the end of the session gives a spending breakdown with three ways to save. The session is saved to a dated JSON file.

WeCan Academy, AI Course, Season 12 group project.

**Group name:** Eden-techs  
**Members:** Gift Maghanga, Jacinta Koki, Edith Wandia

## Features (to be completed)
- Conversation memory: the full message list is sent with every Gemini call
- JSON replies checked by code, with one retry
- Python-calculated totals, categories and M-Pesa fees
- Final AI summary with three saving recommendations
- Dated saved sessions that can be reopened from the menu
- Terminal menu, plus a browser interface built with Streamlit

## Libraries used
| Library | Purpose |
|---|---|
| google-genai | Connects to the Google Gemini API |
| python-dotenv | Loads the API key from the `.env` file |
| streamlit | Browser interface (no HTML or CSS needed) |
| pytest | Runs the tests |

Everything else (json, os, datetime) comes with Python.

## Setup
1. Install Python 3.15 (the version the team tested).
2. Create a virtual environment: `python -m venv venv`
3. Activate it:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. Install the libraries: `python -m pip install -r requirements.txt`

To install them one by one instead: `pip install google-genai python-dotenv streamlit pytest`

## How to set the API key
1. Get a Gemini API key from Google AI Studio.
2. Open the `.env` file in the project folder and replace `your_api_key_here` with your key, so the line reads `GEMINI_API_KEY=your key`. If the file is missing, create a file named `.env` with that one line.
3. Never commit `.env`. It is listed in `.gitignore`, and the code reads the key from `.env`; the key is never written in the code.

## Run
Terminal version:

    python main.py

Menu: 1 start a new session, 2 open a past session, 3 exit.

Browser version (once `app_streamlit.py` is added):

    streamlit run app_streamlit.py

## Files
| File | Purpose |
|---|---|
| main.py | Menu and session flow (Gift Maghanga) |
| response_validator.py | Checks every AI reply, one retry (Gift Maghanga) |
| app_streamlit.py | Browser interface (Gift Maghanga, planned) |
| ai_client.py, prompts.py | Gemini connection and the two R-T-C-C-O prompts (Jacinta Koki) |
| expense_tracker.py, session_manager.py | Expenses, fees, report, saving (Edith Wandia) |
| config.py | Shared constants |
| requirements.txt | List of libraries to install |
| samples/ | One saved session from our own testing |
| sessions/ | Created automatically when the first session is saved (not committed) |

## Known limitations
(add before submission)
