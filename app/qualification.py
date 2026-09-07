"""Lead qualification scoring.

Turns the answers collected during a call into a score and a hot/warm/cold
band, so the sales team knows which callbacks matter most.
"""

TIMEFRAME_SCORES = {
    "immediately": 40,
    "this_week": 35,
    "this_month": 25,
    "few_months": 10,
    "just_researching": 0,
}

INTENT_SCORES = {
    "ready_to_book": 40,
    "comparing_options": 25,
    "wants_information": 10,
    "general_enquiry": 5,
}

BUDGET_SCORES = {
    "insured": 20,
    "self_pay_confirmed": 20,
    "unsure": 8,
    "no_budget": 0,
}

HOT_THRESHOLD = 70
WARM_THRESHOLD = 40


def score_lead(timeframe: str | None = None,
               intent: str | None = None,
               budget: str | None = None,
               contact_complete: bool = False) -> dict:
    """Score a lead 0-105 and band it. Unknown/missing answers simply score 0."""
    score = 0
    score += TIMEFRAME_SCORES.get((timeframe or "").lower().replace(" ", "_"), 0)
    score += INTENT_SCORES.get((intent or "").lower().replace(" ", "_"), 0)
    score += BUDGET_SCORES.get((budget or "").lower().replace(" ", "_"), 0)
    if contact_complete:
        score += 5

    if score >= HOT_THRESHOLD:
        band = "hot"
    elif score >= WARM_THRESHOLD:
        band = "warm"
    else:
        band = "cold"

    return {"score": score, "band": band}


def describe(band: str) -> str:
    return {
        "hot": "high-intent lead, sales team notified directly",
        "warm": "interested lead, worth a follow-up call",
        "cold": "early-stage enquiry, nurture later",
    }.get(band, "unscored")
