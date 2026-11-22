# M-Pesa Expense Coach

A menu-driven Python tool where you tell an AI assistant (Claude) what you spent, in everyday language, over several turns. It remembers the whole conversation, keeps running totals and M-Pesa fees, and at the end of the session gives a spending breakdown with three ways to save. The session is saved to a dated JSON file.

WeCan Academy, AI Course, Season 12 group project.

**Group name:** Eden-techs  
**Members:** Gift Maghanga, Jacinta Koki, Edith Wandia

## What it does
- Conversation memory: the full message list is sent with every Claude call, so later answers use earlier turns.
- Python does the counting, Claude does the understanding: totals, categories and Send Money fees are calculated by code, not by the AI.
- One message can hold several expenses, for example rent through Paybill plus a withdrawal.
- The tool asks politely when something is missing, such as how you paid, the Paybill transaction cost or the withdrawal charge.
- Simple spending questions ("how much have I spent so far?") are answered by Python without an API call.
- Every AI reply is JSON, checked by code, with one retry and a clear message if it still fails.
- At the end, one final AI call writes a short summary with exactly three ways to save.
- Sessions are saved to a dated file and can be reopened from the menu.
- Terminal menu, plus a browser version built with Streamlit (no HTML or CSS) with a budget bar and a download button.

## Libraries used
| Library | Purpose |
|---|---|
| anthropic | Connects to the Claude API |
| python-dotenv | Loads the API key from the `.env` file |
| streamlit | Browser interface (no HTML or CSS needed) |

Everything else (json, os, datetime) comes with Python.

## Setup
1. Install Python 3.15 (the version the team tested).
2. Create a virtual environment: `python -m venv venv`
3. Activate it:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. Install the libraries: `python -m pip install -r requirements.txt`

To install them one by one instead: `pip install anthropic python-dotenv streamlit`

## How to set the API key
1. Get a Claude API key from the Anthropic Console (console.anthropic.com).
2. Create a file named `.env` in the project folder with one line: `ANTHROPIC_API_KEY=your_key_here` (replace `your_key_here` with your key).
3. Never commit `.env`. It is listed in `.gitignore`, and the code reads the key from `.env`; the key is never written in the code.

## Run
Terminal version:

    python main.py

Menu: 1 start a new session, 2 open a past session, 3 exit. Type `end` to finish a session.

Browser version:

    streamlit run app_streamlit.py

It opens in your browser at http://localhost:8501.

## Example messages
- `I spent 200 on transport via send money`
- `I have paid 15000 for rent through paybill and withdrawn 5000` (the tool asks for the Paybill cost and the withdrawal charge)
- `how much have I spent so far?`
- `what was my first expense?`

## Files
| File | Purpose |
|---|---|
| main.py | Menu and session flow (Gift Maghanga) |
| response_validator.py | Checks every AI reply, one retry (Gift Maghanga) |
| app_streamlit.py | Browser version (Gift Maghanga) |
| ai_client.py, prompts.py | Claude connection and the two R-T-C-C-O prompts (Jacinta Koki) |
| expense_tracker.py, session_manager.py | Expenses, fees, report, saving (Edith Wandia) |
| config.py | Shared constants: categories, payment methods, model name, fee table |
| requirements.txt | List of libraries to install |
| samples/ | One saved session from our own testing |
| sessions/ | Created automatically when the first session is saved (not committed) |

## Known limitations
- Send Money fees come from a table in `config.py`. Check it against Safaricom's current tariff (see `FEES_LAST_VERIFIED` in `config.py`). Paybill costs and withdrawal charges are typed in by the user, not calculated.
- Every AI reply uses the paid Claude API, so each message costs a small amount. If the API fails or the credit runs out, the tool shows a message instead of crashing.
- Claude can occasionally misread a sentence. Check the "Expense recorded" line after each message.
- Only simple spending questions are answered locally. Other questions go to Claude.
- Amounts are in Kenyan shillings only. There is no login, and session files are plain JSON on your computer. Do not type PINs, passwords, ID numbers or phone numbers.
