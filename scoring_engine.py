"""
Legal Scoring Engine
--------------------
Rules-driven scoring engine. Scores an account (0-100) across configurable
factors to determine the priority and viability of pursuing legal recovery.

Score Bands (configurable via Rule Engine):
  70-100 : High Priority  — Recommend Legal Action
  40-69  : Medium Priority — Further Investigation Required
  0-39   : Low Priority   — Legal Action Not Recommended
"""

# Maps factor key → account data field name
FIELD_MAP = {
    "debt_amount":   "debt_amount",
    "debt_age":      "debt_age_days",
    "credit_score":  "credit_score",
    "employment":    "employment_status",
    "assets":        "owns_assets",
    "prior_payment": "prior_payment",
}


def get_default_rules() -> dict:
    """Return the default scoring ruleset as a structured dict."""
    return {
        "score_bands": {"high_min": 70, "medium_min": 40},
        "factors": [
            {
                "key": "debt_amount", "type": "tiered_gte",
                "label": "Debt Amount", "max_pts": 30,
                "tiers": [
                    {"threshold": 25000, "pts": 30},
                    {"threshold": 15000, "pts": 24},
                    {"threshold": 8000,  "pts": 18},
                    {"threshold": 3000,  "pts": 10},
                    {"threshold": 0,     "pts": 4},
                ],
            },
            {
                "key": "debt_age", "type": "tiered_lte",
                "label": "Debt Age", "max_pts": 20,
                "tiers": [
                    {"threshold": 90,   "pts": 20},
                    {"threshold": 180,  "pts": 16},
                    {"threshold": 365,  "pts": 10},
                    {"threshold": 730,  "pts": 5},
                    {"threshold": 9999, "pts": 1},
                ],
            },
            {
                "key": "credit_score", "type": "tiered_gte",
                "label": "Credit Score", "max_pts": 20,
                "tiers": [
                    {"threshold": 700, "pts": 20},
                    {"threshold": 650, "pts": 16},
                    {"threshold": 580, "pts": 10},
                    {"threshold": 500, "pts": 5},
                    {"threshold": 300, "pts": 1},
                ],
            },
            {
                "key": "employment", "type": "categorical",
                "label": "Employment Status", "max_pts": 15,
                "values": [
                    {"label": "Employed",      "pts": 15},
                    {"label": "Self-Employed", "pts": 10},
                    {"label": "Unemployed",    "pts": 2},
                ],
            },
            {
                "key": "assets", "type": "boolean",
                "label": "Asset Ownership", "max_pts": 10,
            },
            {
                "key": "prior_payment", "type": "boolean",
                "label": "Prior Payment", "max_pts": 5,
            },
        ],
    }


def _score_factor(factor: dict, value) -> int:
    ftype = factor["type"]
    if ftype == "tiered_gte":
        tiers = sorted(factor["tiers"], key=lambda t: t["threshold"], reverse=True)
        for tier in tiers:
            if float(value) >= tier["threshold"]:
                return tier["pts"]
        return 0
    elif ftype == "tiered_lte":
        tiers = sorted(factor["tiers"], key=lambda t: t["threshold"])
        for tier in tiers:
            if float(value) <= tier["threshold"]:
                return tier["pts"]
        return 0
    elif ftype == "categorical":
        lookup = {v["label"]: v["pts"] for v in factor["values"]}
        return lookup.get(str(value), 0)
    elif ftype == "boolean":
        return factor["max_pts"] if int(value) else 0
    return 0


def score_account(data: dict, rules: dict = None) -> dict:
    if rules is None:
        rules = get_default_rules()

    breakdown = {}
    total = 0

    for factor in rules["factors"]:
        key = factor["key"]
        field = FIELD_MAP.get(key, key)
        raw_value = data.get(field, 0)
        pts = _score_factor(factor, raw_value)
        max_pts = factor["max_pts"]

        if factor["type"] == "boolean":
            detail = "Yes" if int(raw_value) else "No"
        elif key == "debt_amount":
            detail = f"${float(raw_value):,.2f}"
        else:
            detail = str(raw_value)

        breakdown[factor["label"]] = {"score": pts, "max": max_pts, "detail": detail}
        total += pts

    total = min(total, 100)

    bands = rules.get("score_bands", {"high_min": 70, "medium_min": 40})
    if total >= bands["high_min"]:
        recommendation = "High Priority"
        rec_detail = "Recommend Legal Action"
        band = "high"
    elif total >= bands["medium_min"]:
        recommendation = "Medium Priority"
        rec_detail = "Further Investigation Required"
        band = "medium"
    else:
        recommendation = "Low Priority"
        rec_detail = "Legal Action Not Recommended"
        band = "low"

    return {
        "legal_score": total,
        "recommendation": recommendation,
        "rec_detail": rec_detail,
        "band": band,
        "breakdown": breakdown,
    }
