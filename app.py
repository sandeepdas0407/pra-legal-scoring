import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import (init_db, get_all_accounts, get_account, create_account,
                      save_score, get_score_history,
                      get_active_rules, save_rules, activate_rules, get_rules_history)
from scoring_engine import score_account

app = Flask(__name__)
app.secret_key = "pra-legal-scoring-2024"

US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
]


@app.route("/")
def dashboard():
    accounts = get_all_accounts()
    stats = {
        "total": len(accounts),
        "scored": sum(1 for a in accounts if a["legal_score"] is not None),
        "high": sum(1 for a in accounts if a["recommendation"] == "High Priority"),
        "medium": sum(1 for a in accounts if a["recommendation"] == "Medium Priority"),
        "low": sum(1 for a in accounts if a["recommendation"] == "Low Priority"),
    }
    return render_template("dashboard.html", accounts=accounts, stats=stats)


@app.route("/score/new", methods=["GET", "POST"])
def new_score():
    if request.method == "POST":
        try:
            data = {
                "account_number": request.form["account_number"].strip(),
                "debtor_name":    request.form["debtor_name"].strip(),
                "debt_amount":    float(request.form["debt_amount"]),
                "debt_age_days":  int(request.form["debt_age_days"]),
                "credit_score":   int(request.form["credit_score"]),
                "employment_status": request.form["employment_status"],
                "owns_assets":    1 if request.form.get("owns_assets") == "1" else 0,
                "prior_payment":  1 if request.form.get("prior_payment") == "1" else 0,
                "state":          request.form["state"],
            }

            if not (300 <= data["credit_score"] <= 850):
                flash("Credit score must be between 300 and 850.", "error")
                rules = get_active_rules()
                return render_template("score_form.html", states=US_STATES,
                                       form=request.form, rules_json=json.dumps(rules))

            rules = get_active_rules()
            account_id = create_account(data)
            result = score_account(data, rules=rules)
            save_score(account_id, result["legal_score"], result["recommendation"],
                       json.dumps(result["breakdown"]))

            return redirect(url_for("result", account_id=account_id))

        except ValueError as e:
            flash(f"Invalid input: {e}", "error")
            rules = get_active_rules()
            return render_template("score_form.html", states=US_STATES,
                                   form=request.form, rules_json=json.dumps(rules))

    rules = get_active_rules()
    return render_template("score_form.html", states=US_STATES, form={},
                           rules_json=json.dumps(rules))


@app.route("/score/<int:account_id>")
def result(account_id):
    account = get_account(account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("dashboard"))

    history = get_score_history(account_id)
    if not history:
        flash("No score found for this account.", "error")
        return redirect(url_for("dashboard"))

    latest = history[0]
    rules = get_active_rules()
    result_data = score_account(dict(account), rules=rules)
    result_data["legal_score"] = latest["legal_score"]

    return render_template("result.html",
                           account=account,
                           result=result_data,
                           history=history)


@app.route("/score/existing/<int:account_id>", methods=["POST"])
def rescore(account_id):
    account = get_account(account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("dashboard"))
    rules = get_active_rules()
    result = score_account(dict(account), rules=rules)
    save_score(account_id, result["legal_score"], result["recommendation"],
               json.dumps(result["breakdown"]))
    return redirect(url_for("result", account_id=account_id))


@app.route("/accounts")
def accounts_list():
    accounts = get_all_accounts()
    return render_template("accounts.html", accounts=accounts)


@app.route("/rules", methods=["GET"])
def rule_engine():
    rules = get_active_rules()
    history = get_rules_history()
    active_name = "Default Ruleset"
    for h in history:
        if h["is_active"]:
            active_name = h["rule_name"]
            break
    return render_template("rules.html", rules=rules, history=history,
                           active_name=active_name)


@app.route("/rules", methods=["POST"])
def save_rules_route():
    try:
        body = request.get_json(force=True)
        if not body:
            return jsonify({"error": "No JSON body"}), 400
        if "factors" not in body or "score_bands" not in body:
            return jsonify({"error": "Missing factors or score_bands"}), 400

        rule_name = (body.get("rule_name") or "Custom Ruleset").strip() or "Custom Ruleset"
        rules_to_save = {
            "score_bands": body["score_bands"],
            "factors": body["factors"],
        }
        save_rules(rule_name, rules_to_save)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/rules/activate/<int:rule_id>", methods=["POST"])
def activate_rule(rule_id):
    try:
        activate_rules(rule_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
