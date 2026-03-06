from flask import render_template, request, redirect, url_for, flash, jsonify
from database import get_account, get_score_history, get_eligible_accounts_for_placement
from .db import (
    get_all_attorneys, get_attorney, create_attorney, update_attorney,
    deactivate_attorney, get_attorneys_for_state,
    get_all_placements, get_placement, get_active_placement_for_account,
    get_placements_for_attorney,
    create_placement, update_placement_status,
    get_placement_stats,
)
from modules.constants import US_STATES, PLACEMENT_STATUSES
from . import bp


def _parse_attorney_form(form, include_is_active=False):
    """Parse and validate attorney form fields. Raises ValueError on bad input."""
    states_raw = form.get("states", "").strip()
    data = {
        "firm_name":    form["firm_name"].strip(),
        "contact_name": form["contact_name"].strip(),
        "email":        form["email"].strip(),
        "phone":        form["phone"].strip(),
        "states":       ",".join(s.strip() for s in states_raw.split(",") if s.strip()),
        "max_capacity": int(form["max_capacity"]),
    }
    if include_is_active:
        data["is_active"] = 1 if form.get("is_active") == "1" else 0
    return data


# ── Attorney routes ────────────────────────────────────────────────────────────

@bp.route("/attorneys")
def attorney_list():
    attorneys = get_all_attorneys()
    return render_template("attorney_placements/attorney_list.html", attorneys=attorneys)


@bp.route("/attorneys/new", methods=["GET", "POST"])
def attorney_new():
    if request.method == "POST":
        try:
            data = _parse_attorney_form(request.form)
            if not data["firm_name"] or not data["contact_name"]:
                flash("Firm name and contact name are required.", "error")
                return render_template("attorney_placements/attorney_form.html",
                                       form=request.form, states=US_STATES)
            attorney_id = create_attorney(data)
            flash("Attorney added successfully.", "success")
            return redirect(url_for("placements.attorney_detail", attorney_id=attorney_id))
        except ValueError as e:
            flash(f"Invalid input: {e}", "error")
            return render_template("attorney_placements/attorney_form.html",
                                   form=request.form, states=US_STATES)
    return render_template("attorney_placements/attorney_form.html", form={}, states=US_STATES)


@bp.route("/attorneys/<int:attorney_id>")
def attorney_detail(attorney_id):
    attorney = get_attorney(attorney_id)
    if not attorney:
        flash("Attorney not found.", "error")
        return redirect(url_for("placements.attorney_list"))
    atty_placements = get_placements_for_attorney(attorney_id)
    return render_template("attorney_placements/attorney_detail.html", attorney=attorney,
                           placements=atty_placements, statuses=PLACEMENT_STATUSES)


@bp.route("/attorneys/<int:attorney_id>/edit", methods=["GET", "POST"])
def attorney_edit(attorney_id):
    attorney = get_attorney(attorney_id)
    if not attorney:
        flash("Attorney not found.", "error")
        return redirect(url_for("placements.attorney_list"))
    if request.method == "POST":
        try:
            data = _parse_attorney_form(request.form, include_is_active=True)
            update_attorney(attorney_id, data)
            flash("Attorney updated.", "success")
            return redirect(url_for("placements.attorney_detail", attorney_id=attorney_id))
        except ValueError as e:
            flash(f"Invalid input: {e}", "error")
    return render_template("attorney_placements/attorney_form.html", form=dict(attorney),
                           states=US_STATES, attorney=attorney, editing=True)


@bp.route("/attorneys/<int:attorney_id>/deactivate", methods=["POST"])
def attorney_deactivate(attorney_id):
    ok, msg = deactivate_attorney(attorney_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("placements.attorney_detail", attorney_id=attorney_id))


@bp.route("/attorneys/suggest")
def attorney_suggest():
    state = request.args.get("state", "")
    if not state:
        return jsonify([])
    attorneys = get_attorneys_for_state(state)
    return jsonify([{
        "id": a["id"], "firm_name": a["firm_name"], "contact_name": a["contact_name"],
        "active_cases": a["active_cases"], "max_capacity": a["max_capacity"],
        "available": a["available"],
    } for a in attorneys])


# ── Placement routes ───────────────────────────────────────────────────────────

@bp.route("/")
def placements_list():
    view          = request.args.get("view", "placements")
    status_filter = request.args.get("status")
    placements    = get_all_placements(status_filter)
    stats         = get_placement_stats()
    eligible      = get_eligible_accounts_for_placement()
    return render_template("attorney_placements/placements.html",
                           placements=placements, stats=stats,
                           statuses=PLACEMENT_STATUSES, current_filter=status_filter,
                           eligible=eligible, view=view)


@bp.route("/new", methods=["GET", "POST"])
def placement_new():
    account_id = request.args.get("account_id", type=int) or request.form.get("account_id", type=int)
    if not account_id:
        flash("No account specified.", "error")
        return redirect(url_for("placements.placements_list"))

    account = get_account(account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("placements.placements_list"))

    history = get_score_history(account_id)
    if not history or history[0]["legal_score"] < 40:
        flash("Account score is below 40 — not eligible for placement.", "error")
        return redirect(url_for("legal.result", account_id=account_id))

    existing = get_active_placement_for_account(account_id)
    if existing:
        flash(f"Account already has an active placement with {existing['firm_name']}.", "error")
        return redirect(url_for("legal.result", account_id=account_id))

    if request.method == "POST":
        try:
            attorney_id = int(request.form["attorney_id"])
            notes = request.form.get("notes", "").strip()
            placement_id = create_placement(account_id, attorney_id, notes)
            flash("Account placed successfully.", "success")
            return redirect(url_for("placements.placement_detail", placement_id=placement_id))
        except (ValueError, KeyError) as e:
            flash(f"Invalid input: {e}", "error")

    attorneys = get_all_attorneys()
    suggested = get_attorneys_for_state(account["state"])
    return render_template("attorney_placements/placement_form.html", account=account,
                           attorneys=attorneys, suggested=suggested)


@bp.route("/<int:placement_id>")
def placement_detail(placement_id):
    placement = get_placement(placement_id)
    if not placement:
        flash("Placement not found.", "error")
        return redirect(url_for("placements.placements_list"))
    return render_template("attorney_placements/placement_detail.html", placement=placement,
                           statuses=PLACEMENT_STATUSES)


@bp.route("/<int:placement_id>/update", methods=["POST"])
def placement_update(placement_id):
    placement = get_placement(placement_id)
    if not placement:
        return jsonify({"error": "Not found"}), 404
    if request.is_json:
        body = request.get_json(force=True)
        new_status = body.get("status")
        outcome_amount = body.get("outcome_amount")
        notes = body.get("notes")
    else:
        new_status = request.form.get("status")
        outcome_raw = request.form.get("outcome_amount", "").strip()
        outcome_amount = float(outcome_raw) if outcome_raw else None
        notes = request.form.get("notes", "").strip() or None
    if new_status not in PLACEMENT_STATUSES:
        if request.is_json:
            return jsonify({"error": "Invalid status"}), 400
        flash("Invalid status.", "error")
        return redirect(url_for("placements.placement_detail", placement_id=placement_id))
    update_placement_status(placement_id, new_status, outcome_amount, notes)
    if request.is_json:
        return jsonify({"ok": True, "status": new_status})
    flash(f"Status updated to {new_status}.", "success")
    return redirect(url_for("placements.placement_detail", placement_id=placement_id))
