import json
from flask import render_template, request, redirect, url_for, flash, jsonify
from database import (get_all_accounts, get_account, create_account,
                      save_score, get_score_history,
                      get_active_rules, save_rules, activate_rules, get_rules_history,
                      get_ruleset_by_id)
from .scoring_engine import score_account, get_default_rules
from modules.attorney_placements.db import (
    get_active_placement_for_account, get_placements_for_account,
)
from modules.legal_eligibility.eligibility_engine import (
    forecast_legal_recovery_value, check_exclusions,
)

_MIN_FRV = 500.0
from modules.constants import US_STATES
from . import bp

_BAND_MAP = {
    "High Priority":   ("Recommend Legal Action",        "high"),
    "Medium Priority": ("Further Investigation Required", "medium"),
    "Low Priority":    ("Legal Action Not Recommended",  "low"),
}


@bp.route("/")
@bp.route("/dashboard")
def dashboard():
    accounts = get_all_accounts()
    stats = {
        "total":  len(accounts),
        "scored": sum(1 for a in accounts if a["legal_score"] is not None),
        "high":   sum(1 for a in accounts if a["recommendation"] == "High Priority"),
        "medium": sum(1 for a in accounts if a["recommendation"] == "Medium Priority"),
        "low":    sum(1 for a in accounts if a["recommendation"] == "Low Priority"),
    }
    return render_template("legal_scoring/dashboard.html", accounts=accounts, stats=stats)


@bp.route("/score/new", methods=["GET", "POST"])
def new_score():
    all_rulesets = get_rules_history()
    active_rule_id = next((r['id'] for r in all_rulesets if r['is_active']), None)
    all_rules_data = {str(r['id']): json.loads(r['rules_json']) for r in all_rulesets}

    if request.method == "POST":
        rule_id = request.form.get('rule_id', type=int)
        rules = all_rules_data.get(str(rule_id)) if rule_id else None
        if not rules:
            rules = all_rules_data.get(str(active_rule_id)) or get_default_rules()
            rule_id = None

        def _render_form(selected_rule_id):
            return render_template("legal_scoring/score_form.html", states=US_STATES,
                                   form=request.form, rules_json=json.dumps(rules),
                                   all_rulesets=all_rulesets,
                                   active_rule_id=active_rule_id,
                                   selected_rule_id=selected_rule_id,
                                   all_rules_json=json.dumps(all_rules_data))

        selected_rule_id = rule_id or active_rule_id

        try:
            data = {
                "account_number":    request.form["account_number"].strip(),
                "debtor_name":       request.form["debtor_name"].strip(),
                "debt_amount":       float(request.form["debt_amount"]),
                "debt_age_days":     int(request.form["debt_age_days"]),
                "credit_score":      int(request.form["credit_score"]),
                "employment_status": request.form["employment_status"],
                "owns_assets":       1 if request.form.get("owns_assets") == "1" else 0,
                "prior_payment":     1 if request.form.get("prior_payment") == "1" else 0,
                "state":             request.form["state"],
                "is_bankruptcy":     1 if request.form.get("is_bankruptcy") == "1" else 0,
                "is_sol_expired":    1 if request.form.get("is_sol_expired") == "1" else 0,
                "is_disputed":       1 if request.form.get("is_disputed") == "1" else 0,
                "is_military":       1 if request.form.get("is_military") == "1" else 0,
                "is_deceased":       1 if request.form.get("is_deceased") == "1" else 0,
            }

            if not (300 <= data["credit_score"] <= 850):
                flash("Credit score must be between 300 and 850.", "error")
                return _render_form(selected_rule_id)

            result = score_account(data, rules=rules)
            account_id = create_account(data)
            save_score(account_id, result["legal_score"], result["recommendation"],
                       json.dumps(result["breakdown"]), rule_id=rule_id)

            return redirect(url_for("legal.result", account_id=account_id))

        except ValueError as e:
            flash(f"Invalid input: {e}", "error")
            return _render_form(selected_rule_id)

    active_rules = all_rules_data.get(str(active_rule_id)) or get_default_rules()
    return render_template("legal_scoring/score_form.html", states=US_STATES, form={},
                           rules_json=json.dumps(active_rules),
                           all_rulesets=all_rulesets,
                           active_rule_id=active_rule_id,
                           selected_rule_id=active_rule_id,
                           all_rules_json=json.dumps(all_rules_data))


@bp.route("/score/<int:account_id>")
def result(account_id):
    account = get_account(account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("legal.dashboard"))

    history = get_score_history(account_id)
    if not history:
        flash("No score found for this account.", "error")
        return redirect(url_for("legal.dashboard"))

    latest = history[0]
    rec = latest["recommendation"]
    rec_detail, band = _BAND_MAP.get(rec, ("", "low"))
    result_data = {
        "legal_score":    latest["legal_score"],
        "recommendation": rec,
        "rec_detail":     rec_detail,
        "band":           band,
        "breakdown":      json.loads(latest["score_breakdown"]),
    }

    active_placement = get_active_placement_for_account(account_id)
    all_placements   = get_placements_for_account(account_id)

    # Inline eligibility assessment for this account
    acct_dict   = dict(account)
    frv_data    = forecast_legal_recovery_value(acct_dict)
    excl        = check_exclusions(acct_dict, has_active_placement=bool(active_placement))
    eligibility = {
        **frv_data,
        'is_frv_eligible':   frv_data['frv'] >= _MIN_FRV,
        'is_excluded':       excl['is_excluded'],
        'exclusion_reasons': excl['exclusion_reasons'],
        'is_legal_eligible': frv_data['frv'] >= _MIN_FRV and not excl['is_excluded'],
        'min_frv':           _MIN_FRV,
    }

    return render_template("legal_scoring/result.html", account=account, result=result_data,
                           history=history, active_placement=active_placement,
                           all_placements=all_placements, eligibility=eligibility)


@bp.route("/score/existing/<int:account_id>", methods=["POST"])
def rescore(account_id):
    account = get_account(account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("legal.dashboard"))
    rules = get_active_rules()
    result = score_account(dict(account), rules=rules)
    save_score(account_id, result["legal_score"], result["recommendation"],
               json.dumps(result["breakdown"]))
    return redirect(url_for("legal.result", account_id=account_id))


@bp.route("/accounts")
def accounts_list():
    accounts = get_all_accounts()
    return render_template("legal_scoring/accounts.html", accounts=accounts)


@bp.route("/rules", methods=["GET"])
def rule_engine():
    history = get_rules_history()
    load_id = request.args.get('load', type=int)
    is_new = request.args.get('new') == '1'

    if is_new:
        rules = get_default_rules()
        active_name = ''
        load_id = None
    elif load_id:
        rules = get_ruleset_by_id(load_id) or get_active_rules()
        active_name = next((r['rule_name'] for r in history if r['id'] == load_id), 'Default Ruleset')
    else:
        rules = get_active_rules()
        active_name = next((r['rule_name'] for r in history if r['is_active']), 'Default Ruleset')
        load_id = None

    return render_template("legal_scoring/rules.html", rules=rules, history=history,
                           active_name=active_name, loaded_id=load_id, is_new=is_new)


@bp.route("/rules", methods=["POST"])
def save_rules_route():
    try:
        body = request.get_json(force=True)
        if not body:
            return jsonify({"error": "No JSON body"}), 400
        if "factors" not in body or "score_bands" not in body:
            return jsonify({"error": "Missing factors or score_bands"}), 400

        rule_name = (body.get("rule_name") or "Custom Ruleset").strip() or "Custom Ruleset"
        save_rules(rule_name, {"score_bands": body["score_bands"], "factors": body["factors"]})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/rules/activate/<int:rule_id>", methods=["POST"])
def activate_rule(rule_id):
    try:
        activate_rules(rule_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
