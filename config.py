"""Shared constants for the M-Pesa Expense Coach.

Agreed by all three members (Section 3 and 7 of the build plan).
No API key is stored here: the key is read from .env by ai_client.py.
"""

# Allowed expense categories (Section 3.1)
CATEGORIES = ["rent_utilities", "transport", "food", "airtime_wifi",
              "savings", "transaction_cost", "other"]

# Allowed payment methods (Section 3.1). agent_withdrawal only if its fee is handled safely.
PAYMENT_METHODS = ["send_money", "buy_goods", "paybill", "cash"]

# Words the user can type to end a session
END_WORDS = ["end", "end session", "quit session", "done"]

# Gemini model name and settings. TODO (Member 2): confirm the model name and parameters.
MODEL_NAME = "gemini-3.8-flash"
MODEL_TEMPERATURE = 0.2

# Draft Send Money fee bands (lower, upper, fee in KSh). Section 3.2.
# TODO (Member 3 / team): re-verify against Safaricom's official tariff and update the date.
SEND_MONEY_FEES = [
    (1, 100, 0), (101, 500, 7), (501, 1000, 13), (1001, 1500, 23),
    (1501, 2500, 33), (2501, 3500, 53), (3501, 5000, 57), (5001, 7500, 78),
    (7501, 10000, 90), (10001, 15000, 100), (15001, 20000, 105),
    (20001, 250000, 108),
]
FEES_LAST_VERIFIED = "NOT YET VERIFIED"
