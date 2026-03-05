# PRA Legal Recovery

An internal web application for scoring debtors on the likelihood of successful legal recovery, and managing attorney placements. Built with Python (Flask) + SQLite + vanilla JS.

---

## Modules

### Legal Scoring
- **Dashboard** — portfolio overview with High / Medium / Low priority counts
- **Accounts** — full account table with scores and recommendations
- **Score New Account** — form with live score preview mirroring the active ruleset
- **Rule Engine** — configure scoring weights and thresholds without touching code; changes are versioned and take effect immediately

### Attorney Placements
- **Attorneys** — manage law firms, contact info, state coverage and capacity
- **Placements** — place scored accounts with attorneys; track status through Placed → Active → Settled / Judgment / Closed

---

## Scoring Model

Accounts are scored 0–100 across six weighted factors:

| Factor | Type | Max pts |
|---|---|---|
| Debt Amount | Tiered (≥) | 30 |
| Debt Age (days) | Tiered (≤) | 20 |
| Credit Score | Tiered (≥) | 20 |
| Employment Status | Categorical | 15 |
| Asset Ownership | Boolean | 10 |
| Prior Payment History | Boolean | 5 |

**Score bands (configurable via Rule Engine):**

| Range | Priority | Action |
|---|---|---|
| 70 – 100 | High | Recommend Legal Action |
| 40 – 69 | Medium | Further Investigation Required |
| 0 – 39 | Low | Legal Action Not Recommended |

---

## Getting Started

**Requirements:** Python 3.9+

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python app.py
```

Open **http://localhost:5000** in your browser.

The database is created automatically on first run and seeded with 10 sample accounts and 5 attorneys.

---

## Project Structure

```
legal_recovery/
├── app.py                          # Flask app factory + landing route
├── database.py                     # SQLite helpers, seeding, rule versioning
├── requirements.txt
├── run.bat                         # Windows launcher
├── modules/
│   ├── constants.py                # US_STATES, PLACEMENT_STATUSES
│   ├── legal_scoring/
│   │   ├── routes.py               # /legal/* routes
│   │   ├── scoring_engine.py       # Rules-driven scoring logic
│   │   └── templates/legal_scoring/
│   │       ├── dashboard.html
│   │       ├── accounts.html
│   │       ├── score_form.html
│   │       ├── result.html
│   │       └── rules.html
│   └── attorney_placements/
│       ├── routes.py               # /placements/* routes
│       ├── db.py                   # Attorney & placement DB helpers
│       └── templates/attorney_placements/
│           ├── attorney_list.html
│           ├── attorney_form.html
│           ├── attorney_detail.html
│           ├── placements.html
│           ├── placement_form.html
│           └── placement_detail.html
├── templates/
│   ├── base.html
│   ├── landing.html
│   └── _macros.html                # score_badge, rec_pill, placement_status_badge
└── static/
    ├── css/style.css
    └── js/app.js
```

---

*Internal use only — PRA Group*
