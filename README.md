# PRA Legal Scoring

An internal web application for scoring debtors on the likelihood of successful legal recovery. Built with Python (Flask) + SQLite + vanilla JS.

---

## Features

- **Dashboard** — portfolio overview with High / Medium / Low priority counts
- **Accounts** — searchable table of all scored accounts
- **Score New Account** — form with a live score preview that mirrors the active ruleset
- **Rule Engine** — admin UI to configure scoring weights and thresholds without touching code; changes are versioned and take effect immediately

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

## Rule Engine

All scoring weights and thresholds are configurable from `/rules` — no code changes needed. Every save creates a new versioned ruleset. Previous versions can be reactivated at any time from the history panel.

---

## Getting Started

**Requirements:** Python 3.9+

```bash
# 1. Clone
git clone https://github.com/sandeepdas0407/pra-legal-scoring.git
cd pra-legal-scoring

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

Open **http://localhost:5000** in your browser.

The database is created automatically on first run and seeded with 10 sample accounts.

---

## Project Structure

```
legal_scoring/
├── app.py              # Flask routes
├── scoring_engine.py   # Rules-driven scoring logic
├── database.py         # SQLite helpers + rule versioning
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── accounts.html
│   ├── score_form.html
│   ├── result.html
│   └── rules.html      # Rule Engine page
└── static/
    ├── css/style.css
    └── js/app.js
```

---

*Internal use only — PRA Group*
