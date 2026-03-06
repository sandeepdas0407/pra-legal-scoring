"""
Legal Eligibility Engine
------------------------
Two-stage process flow for determining which accounts should proceed to legal action.

Stage 1 — Eligibility Scoring (Forecasted Legal Recovery Value)
  Calculates the net dollar amount expected to be recovered through legal action.
  FRV = (Debt Amount × Recovery Probability) − Estimated Legal Costs
  Accounts where FRV >= configured minimum threshold pass Stage 1.

Stage 2 — Exclusion Filtering
  Mandatory exclusions that disqualify an account regardless of FRV:
    - Active attorney placement already exists
    - Bankruptcy filed
    - Statute of limitations expired
    - Account disputed
    - Military / SCRA protection
    - Deceased debtor
    - Debt below minimum ($500)

An account is "Legal Eligible" only when it passes BOTH stages.
"""

MIN_DEBT_THRESHOLD = 500.0

EXCLUSION_LABELS = {
    'active_placement':   'Active Attorney Placement',
    'bankruptcy':         'Bankruptcy Filed',
    'sol_expired':        'Statute of Limitations Expired',
    'disputed':           'Account Disputed',
    'military':           'Military / SCRA Protection',
    'deceased':           'Deceased Debtor',
    'below_minimum_debt': f'Debt Below Minimum (${MIN_DEBT_THRESHOLD:,.0f})',
}


# ── Stage 1: Forecasted Legal Recovery Value ──────────────────────────────────

def _estimate_recovery_probability(credit_score, employment_status,
                                   owns_assets, prior_payment, debt_age_days):
    """
    Estimate the probability (0.0–0.95) of collecting through legal action.
    Built from four independent components that reflect collectability.
    """
    prob = 0.0

    # Credit score → repayment capacity (0–0.35)
    if credit_score >= 700:   prob += 0.35
    elif credit_score >= 650: prob += 0.28
    elif credit_score >= 580: prob += 0.20
    elif credit_score >= 500: prob += 0.12
    else:                     prob += 0.05

    # Employment → wage garnishment feasibility (0–0.30)
    emp_weight = {'Employed': 0.30, 'Self-Employed': 0.20, 'Unemployed': 0.05}
    prob += emp_weight.get(employment_status, 0.05)

    # Asset ownership → lien / levy opportunity (0–0.20)
    if owns_assets:
        prob += 0.20

    # Prior payment → willingness to resolve (0–0.10)
    if prior_payment:
        prob += 0.10

    # Debt age decay — older debts are harder to collect
    if debt_age_days > 730:
        prob *= 0.65
    elif debt_age_days > 365:
        prob *= 0.82

    return round(min(prob, 0.95), 4)


def _estimate_legal_cost(debt_amount):
    """Tiered estimate of attorney fees and court costs."""
    if debt_amount >= 25000: return 2500.0
    if debt_amount >= 10000: return 1500.0
    if debt_amount >= 3000:  return 800.0
    return 500.0


def forecast_legal_recovery_value(account_data):
    """
    Calculate the Forecasted Legal Recovery Value (FRV) for a single account.

    Returns a dict with:
      frv                    — net recovery estimate (dollars)
      gross_recovery_estimate — debt × probability
      legal_cost_estimate    — estimated litigation cost
      recovery_probability   — probability as a percentage (e.g. 62.5)
    """
    debt       = float(account_data.get('debt_amount', 0))
    credit     = int(account_data.get('credit_score', 300))
    employment = account_data.get('employment_status', 'Unemployed')
    assets     = int(account_data.get('owns_assets', 0))
    prior_pay  = int(account_data.get('prior_payment', 0))
    age_days   = int(account_data.get('debt_age_days', 0))

    prob       = _estimate_recovery_probability(credit, employment, assets, prior_pay, age_days)
    gross      = round(debt * prob, 2)
    legal_cost = _estimate_legal_cost(debt)
    frv        = round(gross - legal_cost, 2)

    return {
        'frv':                     frv,
        'gross_recovery_estimate': gross,
        'legal_cost_estimate':     legal_cost,
        'recovery_probability':    round(prob * 100, 1),
    }


# ── Stage 2: Exclusion Checking ───────────────────────────────────────────────

def check_exclusions(account_data, has_active_placement=False):
    """
    Evaluate all mandatory exclusion criteria for an account.

    Returns a dict with:
      is_excluded       — True if any exclusion applies
      exclusion_reasons — list of human-readable reason strings
      flags             — dict of individual flag → bool
    """
    debt = float(account_data.get('debt_amount', 0))

    flags = {
        'active_placement':   has_active_placement,
        'bankruptcy':         bool(int(account_data.get('is_bankruptcy', 0))),
        'sol_expired':        bool(int(account_data.get('is_sol_expired', 0))),
        'disputed':           bool(int(account_data.get('is_disputed', 0))),
        'military':           bool(int(account_data.get('is_military', 0))),
        'deceased':           bool(int(account_data.get('is_deceased', 0))),
        'below_minimum_debt': debt < MIN_DEBT_THRESHOLD,
    }

    reasons = [EXCLUSION_LABELS[k] for k, v in flags.items() if v]

    return {
        'is_excluded':       any(flags.values()),
        'exclusion_reasons': reasons,
        'flags':             flags,
    }


# ── Combined Run ──────────────────────────────────────────────────────────────

def run_eligibility_check(accounts, active_placement_ids, min_frv=500.0):
    """
    Execute the full two-stage eligibility process over a list of accounts.

    Args:
        accounts             — iterable of account row dicts
        active_placement_ids — set of account_ids that have an active placement
        min_frv              — minimum FRV (dollars) required to pass Stage 1

    Returns:
        list of result dicts, one per account, with all scoring and flag details
    """
    results = []

    for acct in accounts:
        acct = dict(acct)
        aid  = acct['id']

        # Stage 1: Forecasted Legal Recovery Value
        frv_data        = forecast_legal_recovery_value(acct)
        is_frv_eligible = frv_data['frv'] >= min_frv

        # Stage 2: Exclusion check
        has_placement   = aid in active_placement_ids
        excl            = check_exclusions(acct, has_active_placement=has_placement)

        # Final verdict
        is_legal_eligible = is_frv_eligible and not excl['is_excluded']

        results.append({
            'account_id':              aid,
            'frv':                     frv_data['frv'],
            'gross_recovery_estimate': frv_data['gross_recovery_estimate'],
            'legal_cost_estimate':     frv_data['legal_cost_estimate'],
            'recovery_probability':    frv_data['recovery_probability'],
            'is_frv_eligible':         1 if is_frv_eligible else 0,
            'is_excluded':             1 if excl['is_excluded'] else 0,
            'exclusion_reasons':       excl['exclusion_reasons'],
            'is_legal_eligible':       1 if is_legal_eligible else 0,
        })

    return results
