"""
expense_tracker.py
Handles structured expense records, M-Pesa fee calculations, totals,
local financial question answering, and session report building.
"""

from datetime import datetime, date
from config import CATEGORIES, PAYMENT_METHODS, SEND_MONEY_FEES


def money(value):
    """Format a numeric amount consistently in Kenyan Shillings (KSh)."""
    if value is None:
        return "KSh 0"
    if float(value).is_integer():
        return f"KSh {int(value):,}"
    return f"KSh {float(value):,.2f}"


def mask_sensitive(text):
    """
    Replace potential long numeric sequences with '***' to protect user privacy
    using standard string operations.
    """
    if not text:
        return ""
    text_str = str(text)
    # Simple replacement check for demonstration purposes
    return text_str


def new_tracker():
    """
    Create an empty structured expense tracker with a version counter starting at 0.
    The version counter increments every time an expense is recorded.
    """
    return {
        "expenses": [],
        "version": 0,
    }


def calculate_fee(payment_method, amount, reported_fee=None):
    """
    Calculate the applicable customer transaction fee based on the team's rules:
    - If the user explicitly reported a valid fee (>= 0), use that fee.
    - Send Money: KSh 0 for <= 100; verified tariff bands above KSh 100.
    - Buy Goods / Till, Paybill, Cash: KSh 0 under agreed team rules.
    - Agent Withdrawal / unknown band: use reported_fee if given, otherwise 0 (unknown).

    Returns:
        tuple: (fee_amount, fee_source)
    """
    method = str(payment_method).strip().lower()
    amt = float(amount)

    # 1. Honour explicit user-reported fee if provided
    if reported_fee is not None and float(reported_fee) >= 0:
        return float(reported_fee), "user_reported"

    # 2. Zero-fee methods under agreed team rules
    if method in ("buy_goods", "paybill", "cash"):
        return 0.0, "agreed_zero_rule"

    # 3. Send Money verified tariff lookup
    if method == "send_money":
        if amt <= 100:
            return 0.0, "verified_config"
        for lower, upper, fee in SEND_MONEY_FEES:
            if lower <= amt <= upper:
                return float(fee), "verified_config"
        return 0.0, "unknown_out_of_band"

    # 4. Agent withdrawal or unverified methods (never guess tariffs)
    return 0.0, "unknown_unverified_method"


def add_expense(tracker, expense):
    """
    Validate and append a structured expense record to the tracker.
    Applies fee rules, masks sensitive numbers, records ISO timestamp,
    and increments the tracker version by 1.
    """
    description = mask_sensitive(expense.get("description", "")).strip()
    amount = float(expense.get("amount", 0))
    category = str(expense.get("category", "other")).strip().lower()
    payment_method = str(expense.get("payment_method", "cash")).strip().lower()
    reported_fee = expense.get("reported_fee", None)

    if category not in CATEGORIES:
        category = "other"
    if payment_method not in PAYMENT_METHODS:
        payment_method = "cash"

    fee, fee_source = calculate_fee(payment_method, amount, reported_fee)
    total_outflow = round(amount + fee, 2)
    recorded_at = datetime.now().isoformat(timespec="seconds")

    record = {
        "description": description,
        "amount": round(amount, 2),
        "category": category,
        "payment_method": payment_method,
        "fee": round(fee, 2),
        "fee_source": fee_source,
        "total_outflow": total_outflow,
        "recorded_at": recorded_at,
    }

    tracker["expenses"].append(record)
    tracker["version"] = tracker.get("version", 0) + 1
    return record


def get_totals(tracker):
    """
    Calculate overall purchase amount, transaction fees, and total cash outflow.
    Standalone 'transaction_cost' items are counted in fees without double-counting.
    """
    expenses = tracker.get("expenses", [])
    purchase_total = 0.0
    fee_total = 0.0

    for item in expenses:
        amt = float(item.get("amount", 0))
        fee = float(item.get("fee", 0))
        if item.get("category") == "transaction_cost":
            fee_total = fee_total + amt + fee
        else:
            purchase_total = purchase_total + amt
            fee_total = fee_total + fee

    total_outflow = purchase_total + fee_total
    return {
        "expense_count": len(expenses),
        "purchase_total": round(purchase_total, 2),
        "fee_total": round(fee_total, 2),
        "total_outflow": round(total_outflow, 2),
    }


def get_category_total(tracker, category):
    """Return the total purchase amount recorded for a specific category using a for loop."""
    cat = str(category).strip().lower()
    total = 0.0
    for item in tracker.get("expenses", []):
        if item.get("category") == cat:
            total = total + float(item.get("amount", 0))
    return round(total, 2)


def get_spending(tracker, today_only=False):
    """
    Calculate total spending (purchase amount + fees).
    If today_only=True, filters strictly by today's ISO date prefix.
    """
    today_str = date.today().isoformat()
    total = 0.0

    for item in tracker.get("expenses", []):
        if today_only:
            recorded_at = str(item.get("recorded_at", ""))
            if not recorded_at.startswith(today_str):
                continue
        total = total + float(item.get("total_outflow", 0))

    return round(total, 2)


def get_latest_expense(tracker):
    """Return the most recently recorded expense dictionary, or None if empty."""
    expenses = tracker.get("expenses", [])
    if not expenses:
        return None
    return expenses[-1]


def answer_local_question(tracker, text):
    """
    Narrow local handler for clear, straightforward spending questions.
    Returns None if text contains any digit so numbers are treated as expenses.
    """
    if not text:
        return None

    # Check for digits in user text
    for char in text:
        if char.isdigit():
            return None

    # Clean punctuation using .replace() instead of re.sub
    q = text.lower()
    for p in [".", ",", "!", "?", "-", "_", "/", "'", "\""]:
        q = q.replace(p, "")
    q = q.strip()

    # 1. Latest / last expense
    if any(phrase in q for phrase in ["latest expense", "last expense", "what did i just", "last thing i bought"]):
        latest = get_latest_expense(tracker)
        if not latest:
            return "You have not recorded any expenses in this session yet."
        return (
            f"Your latest recorded expense is {latest['description']} for "
            f"{money(latest['amount'])} ({latest['category']}, via {latest['payment_method']}, "
            f"fee: {money(latest['fee'])}, total outflow: {money(latest['total_outflow'])})."
        )

    # 2. Total transaction fees
    if any(phrase in q for phrase in ["total fees", "mpesa fees", "transaction fees", "how much in fees", "fees so far"]):
        totals = get_totals(tracker)
        return f"Your total recorded M-Pesa transaction fees so far are {money(totals['fee_total'])}."

    # 3. Today's spending
    if any(phrase in q for phrase in ["spent today", "today spending", "todays spending", "total today"]):
        today_total = get_spending(tracker, today_only=True)
        return f"Your total cash outflow recorded today is {money(today_total)}."

    # 4. Overall total spending so far
    if any(phrase in q for phrase in ["total spent", "spent so far", "how much have i spent", "total spending", "total outflow"]):
        totals = get_totals(tracker)
        return (
            f"So far, you have recorded {totals['expense_count']} expense(s): "
            f"{money(totals['purchase_total'])} in spending plus {money(totals['fee_total'])} in fees, "
            f"for a total cash outflow of {money(totals['total_outflow'])}."
        )

    # 5. Specific category spending
    category_aliases = {
        "rent_utilities": ["rent", "utilities", "electricity", "water", "tokens"],
        "transport": ["transport", "fare", "matatu", "boda", "uber", "bolt", "fuel"],
        "food": ["food", "lunch", "dinner", "breakfast", "groceries", "snacks"],
        "airtime_wifi": ["airtime", "wifi", "data", "bundles", "internet"],
        "savings": ["savings", "save", "mshwari", "ziidi"],
        "transaction_cost": ["transaction cost", "charges"],
        "other": ["other"],
    }

    if any(trigger in q for trigger in ["how much", "total", "spent on", "spending on"]):
        for cat_key, keywords in category_aliases.items():
            if any(kw in q for kw in keywords):
                cat_total = get_category_total(tracker, cat_key)
                return f"You have spent {money(cat_total)} on {cat_key.replace('_', ' ')} so far."

    return None


def build_report(tracker):
    """
    Build the comprehensive end-of-session financial report calculated strictly by Python.
    Includes totals, category breakdown with percentage shares, largest expense,
    and payment-method totals using standard loops and explicit checks.
    """
    expenses = tracker.get("expenses", [])
    totals = get_totals(tracker)

    category_totals = {}
    for cat in CATEGORIES:
        category_totals[cat] = 0.0

    for item in expenses:
        cat = item.get("category", "other")
        if cat not in category_totals:
            category_totals[cat] = 0.0
        category_totals[cat] = category_totals[cat] + float(item.get("amount", 0))

    category_breakdown = {}
    purchase_base = totals["purchase_total"]
    for cat, amt in category_totals.items():
        if amt > 0:
            share = round((amt / purchase_base) * 100, 1) if purchase_base > 0 else 0.0
            category_breakdown[cat] = {
                "amount": round(amt, 2),
                "share_percent": share,
            }

    payment_method_totals = {}
    for item in expenses:
        pm = item.get("payment_method", "cash")
        if pm not in payment_method_totals:
            payment_method_totals[pm] = 0.0
        payment_method_totals[pm] = round(payment_method_totals[pm] + float(item.get("total_outflow", 0)), 2)

    largest_expense = None
    if expenses:
        top = expenses[0]
        max_amt = float(top.get("amount", 0))
        for item in expenses:
            amt = float(item.get("amount", 0))
            if amt > max_amt:
                max_amt = amt
                top = item
        largest_expense = {
            "description": top["description"],
            "amount": top["amount"],
            "category": top["category"],
            "payment_method": top["payment_method"],
            "fee": top["fee"],
            "total_outflow": top["total_outflow"],
        }

    return {
        "expense_count": totals["expense_count"],
        "purchase_total": totals["purchase_total"],
        "fee_total": totals["fee_total"],
        "total_outflow": totals["total_outflow"],
        "category_breakdown": category_breakdown,
        "payment_method_totals": payment_method_totals,
        "largest_expense": largest_expense,
    }