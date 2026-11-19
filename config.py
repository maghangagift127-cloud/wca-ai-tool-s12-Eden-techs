"""Shared constants for the M-Pesa Expense Coach.

No API key is stored here: the key is read from .env by ai_client.py.
"""

# Allowed expense categories
CATEGORIES = ["rent_utilities", "transport", "food", "airtime_wifi",
              "savings", "transaction_cost", "other"]

# Allowed payment methods
PAYMENT_METHODS = ["send_money", "buy_goods", "paybill", "cash"]

# Words the user can type to end a session
END_WORDS = ["end", "end session", "quit session", "done"]

# Gemini model name and temperature (a low value gives steadier, more predictable replies)
MODEL_NAME = "gemini-3.5-flash-lite"
MODEL_TEMPERATURE = 0.2

# Send Money fee bands: (lowest amount, highest amount, fee), all in KSh.
SEND_MONEY_FEES = [
    (1, 100, 0), (101, 500, 7), (501, 1000, 13), (1001, 1500, 23),
    (1501, 2500, 33), (2501, 3500, 53), (3501, 5000, 57), (5001, 7500, 78),
    (7501, 10000, 90), (10001, 15000, 100), (15001, 20000, 105),
    (20001, 250000, 108),
]

# Date the fee table was checked against Safaricom's published tariff.
FEES_LAST_VERIFIED = "19 Nov 2026, checked against Safaricom's published Send Money tariff"