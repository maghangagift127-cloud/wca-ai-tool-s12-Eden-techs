# response_validator.py - checks every Gemini reply before the user sees it.
# Every check returns a dictionary: {"ok": True or False, "data": ..., "error": ...}

import json

import ai_client
import config

# The reply types Gemini is allowed to send.
INTENTS = ["chat", "clarify", "record_expense", "spending_enquiry", "advice"]


# Builds the result for a reply that failed a check.
def fail(error):
    return {"ok": False, "data": None, "error": error}


# True only for a string that is not blank.
def is_text(value):
    return type(value) == str and value.strip() != ""


# True for a whole number or a decimal (True and False are not numbers here).
def is_number(value):
    return type(value) == int or type(value) == float


# Turns the reply text into a dictionary, or fails with a clear error.
def read_json(raw_text):
    if type(raw_text) != str or raw_text.strip() == "":
        return fail("The reply was empty.")
    text = raw_text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text)
    except ValueError:
        return fail("The reply was not valid JSON.")
    if type(data) != dict:
        return fail("The reply must be a JSON object.")
    return {"ok": True, "data": data, "error": None}


# Checks one expense and returns an error message, or None when it is fine.
def check_expense(expense):
    if type(expense) != dict:
        return "Each expense must be an object."
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
    if fee != None and (not is_number(fee) or fee < 0):
        return "reported_fee must be null or a number of 0 or more."
    return None


# Checks a normal reply: the right fields, not blank, and allowed values.
def validate_reply(raw_text):
    result = read_json(raw_text)
    if not result["ok"]:
        return result
    data = result["data"]

    intent = data.get("intent")
    if intent not in INTENTS:
        return fail("Missing or unknown intent.")
    if not is_text(data.get("message")):
        return fail("The message is missing or blank.")

    if intent == "record_expense":
        expenses = data.get("expenses")
        if expenses == None and type(data.get("expense")) == dict:
            expenses = [data["expense"]]  # the old single-expense shape is still accepted
        if type(expenses) != list or len(expenses) == 0:
            return fail("record_expense needs a list of expenses.")
        for expense in expenses:
            error = check_expense(expense)
            if error != None:
                return fail(error)
        data["expenses"] = expenses

    if intent == "spending_enquiry":
        query = data.get("query")
        if type(query) != dict:
            return fail("spending_enquiry needs a query object.")
        category = query.get("category")
        if category != "all" and category not in config.CATEGORIES:
            return fail("The query category must be a known category or 'all'.")

    return {"ok": True, "data": data, "error": None}


# Checks the final summary: a non-blank overview and exactly three non-blank tips.
def validate_summary(raw_text):
    result = read_json(raw_text)
    if not result["ok"]:
        return result
    data = result["data"]

    if not is_text(data.get("overview")):
        return fail("The summary overview is missing or blank.")
    tips = data.get("recommendations")
    if type(tips) != list or len(tips) != 3:
        return fail("The summary needs exactly three recommendations.")
    for tip in tips:
        if not is_text(tip):
            return fail("Every recommendation must be non-empty text.")

    return {"ok": True, "data": data, "error": None}


# Builds the result returned when both tries fail, with a clear message.
def give_up(error):
    message = "Sorry, I could not get a valid answer. " + error + " Please try again."
    return {"ok": False, "data": None, "raw": None, "error": message}


# Asks Gemini with the full history, checks the reply, and tries once more if it is bad.
def get_valid_reply(history):
    error = "Unknown error."
    for attempt in range(2):  # first try, then one retry
        try:
            raw = ai_client.ask_model(history)
        except Exception as problem:  # no internet, wrong key, etc.
            error = "The AI service could not be reached: " + str(problem)
            continue
        result = validate_reply(raw)
        if result["ok"]:
            return {"ok": True, "data": result["data"], "raw": raw, "error": None}
        error = result["error"]
    return give_up(error)


# Asks Gemini for the final summary (full history and report), with one retry.
def get_valid_summary(history, report):
    error = "Unknown error."
    for attempt in range(2):
        try:
            raw = ai_client.summarise(history, report)
        except Exception as problem:
            error = "The AI service could not be reached: " + str(problem)
            continue
        result = validate_summary(raw)
        if result["ok"]:
            return {"ok": True, "data": result["data"], "raw": raw, "error": None}
        error = result["error"]
    return give_up(error)
