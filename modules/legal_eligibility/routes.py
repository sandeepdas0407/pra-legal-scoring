import json
from flask import render_template, request, redirect, url_for, flash
from database import (
    get_all_accounts,
    get_eligibility_runs,
    get_eligibility_run,
    get_eligibility_results,
    create_eligibility_run,
    save_eligibility_results,
    get_active_placement_account_ids,
)
from .eligibility_engine import run_eligibility_check
from . import bp


@bp.route('/')
def eligibility_dashboard():
    runs = get_eligibility_runs()
    return render_template('legal_eligibility/eligibility_dashboard.html', runs=runs)


@bp.route('/run/new', methods=['GET', 'POST'])
def new_run():
    if request.method == 'POST':
        run_name = (request.form.get('run_name') or '').strip() or 'Eligibility Run'
        try:
            min_frv = float(request.form.get('min_frv', 500.0))
        except (ValueError, TypeError):
            min_frv = 500.0

        accounts             = get_all_accounts()
        active_placement_ids = get_active_placement_account_ids()

        results = run_eligibility_check(accounts, active_placement_ids, min_frv=min_frv)

        eligible_count  = sum(1 for r in results if r['is_legal_eligible'])
        excluded_count  = sum(1 for r in results if r['is_excluded'] and r['is_frv_eligible'])
        below_frv_count = sum(1 for r in results if not r['is_frv_eligible'])

        run_id = create_eligibility_run(
            run_name=run_name,
            min_frv=min_frv,
            total=len(accounts),
            eligible=eligible_count,
            excluded=excluded_count,
            below_frv=below_frv_count,
        )
        save_eligibility_results(run_id, results)

        flash(
            f'Eligibility run complete — {eligible_count} of {len(accounts)} accounts are Legal Eligible.',
            'success'
        )
        return redirect(url_for('eligibility.run_results', run_id=run_id))

    return render_template('legal_eligibility/new_run.html')


@bp.route('/run/<int:run_id>')
def run_results(run_id):
    run = get_eligibility_run(run_id)
    if not run:
        flash('Eligibility run not found.', 'error')
        return redirect(url_for('eligibility.eligibility_dashboard'))

    tab     = request.args.get('tab', 'eligible')
    results = get_eligibility_results(run_id, tab=tab)

    return render_template('legal_eligibility/run_results.html',
                           run=run, results=results, tab=tab)
