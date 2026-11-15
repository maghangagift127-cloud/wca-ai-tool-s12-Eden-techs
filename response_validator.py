# Checks every Gemini reply before the user sees it, and retries once if it is bad.

import json

import config

# The reply types Gemini is allowed to send.
INTENTS = ["chat", "clarify", "record_expense", "spending_enquiry", "advice"]


# Removes spaces and the ```json fences that Gemini sometimes adds.
def clean_text(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


# True only for a string that is not blank.
def is_text(value):
    return isinstance(value, str) and value.strip() != ""


# True for a number (True/False do not count as numbers).
def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# Turns the reply text into a dictionary, or returns an error message.
def read_json(raw_text):
    if not isinstance(raw_text, str) or raw_text.strip() == "":
        return None, "The reply was empty."
    try:
        data = json.loads(clean_text(raw_text))
    except json.JSONDecodeError:
        return None, "The reply was not valid JSON."
    if not isinstance(data, dict):
        return None, "The reply must be a JSON object."
    return data, None


# Checks the expense part of a reply and returns an error message, or None if fine.
def check_expense(expense):
    if not isinstance(expense, dict):
        return "record_expense needs an expense object."
    if not is_text(expense.get("description")):
        return "The expense description is missing or blank."
    amount = expense.get("amount")
    if not is_number(amount) or amount <= 0:
        return "The expense amount must be a number above 0."
    if expense.get("category") not in config.CATEGORIES:
        return "The expense category is not allowed."
    if expense.get("payment_method") not in config.PAYMENT_METHODS:
        return "The payment method is not allowed."
    fee = expense.get("reported_fee")  # None (null) or 0 are both fine
    if fee is not None and (not is_number(fee) or fee < 0):
        return "reported_fee must be null or a number of 0 or more."
    return None


# Checks a normal reply and returns (is_valid, data, error).
def validate_reply(raw_text):
    data, error = read_json(raw_text)
    if error:
        return False, None, error

    intent = data.get("intent")
    if intent not in INTENTS:
        return False, None, "Missing or unknown intent."
    if not is_text(data.get("message")):
        return False, None, "The message is missing or blank."

    if intent == "record_expense":
        error = check_expense(data.get("expense"))
        if error:
            return False, None, error

    if intent == "spending_enquiry":
        query = data.get("query")
        if not isinstance(query, dict):
            return False, None, "spending_enquiry needs a query object."
        category = query.get("category")
        if category != "all" and category not in config.CATEGORIES:
            return False, None, "The query category must be a known category or 'all'."

    return True, data, None


# Checks the final summary: a non-blank overview and exactly three non-blank tips.
def validate_summary(raw_text):
    data, error = read_json(raw_text)
    if error:
        return False, None, error
    if not is_text(data.get("overview")):
        return False, None, "The summary overview is missing or blank."
    tips = data.get("recommendations")
    if not isinstance(tips, list) or len(tips) != 3:
        return False, None, "The summary needs exactly three recommendations."
    for tip in tips:
        if not is_text(tip):
            return False, None, "Every recommendation must be non-empty text."
    return True, data, None


# Builds the result returned when both tries fail, with a clear message.
def failure(error):
    message = "Sorry, I could not get a valid answer. " + error + " Please try again."
    return {"ok": False, "data": None, "raw": None, "error": message}


# Asks Gemini with the full history, checks the reply, and retries once if it is bad.
def get_valid_reply(history, facts=None):
    import ai_client  # Member 2's file
    error = "Unknown error."
    extra = facts  # extra text added to the system instruction
    for attempt in range(2):  # first try, then one retry
        try:
            raw = ai_client.ask_model(history, extra)
        except Exception as problem:  # no internet, wrong key, etc.
            error = "The AI service could not be reached: " + str(problem)
            extra = facts
            continue
        ok, data, problem = validate_reply(raw)
        if ok:
            return {"ok": True, "data": data, "raw": raw, "error": None}
        error = problem
        # On the retry, tell Gemini what was wrong (the history stays unchanged).
        extra = (facts or "") + "\nYour previous reply was rejected: " + problem + \
                " Reply again with valid JSON only."
    return failure(error)


# Asks Gemini for the final summary with the full history and report, retrying once.
def get_valid_summary(history, report):
    import ai_client
    error = "Unknown error."
    for attempt in range(2):
        try:
            raw = ai_client.summarise(history, report)
        except Exception as problem:
            error = "The AI service could not be reached: " + str(problem)
            continue
        ok, data, problem = validate_summary(raw)
        if ok:
            return {"ok": True, "data": data, "raw": raw, "error": None}
        error = problem
    return failure(error)
