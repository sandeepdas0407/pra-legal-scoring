/**
 * PRA Legal Scoring — App JS
 *
 * - Live score preview on the scoring form (uses window.SCORING_RULES when injected)
 * - Rule Engine page interactions
 */

// ── Score preview helpers ─────────────────────────────────────────────────────

function scoreWithRules(rules, vals) {
  const fieldVals = {
    debt_amount:   vals.amount,
    debt_age:      vals.age,
    credit_score:  vals.cs,
    employment:    vals.emp,
    assets:        vals.assets,
    prior_payment: vals.prior,
  };

  let total = 0;
  for (const factor of rules.factors) {
    const v = fieldVals[factor.key];
    let pts = 0;

    if (factor.type === 'tiered_gte') {
      const tiers = [...factor.tiers].sort((a, b) => b.threshold - a.threshold);
      for (const t of tiers) { if (v >= t.threshold) { pts = t.pts; break; } }
    } else if (factor.type === 'tiered_lte') {
      const tiers = [...factor.tiers].sort((a, b) => a.threshold - b.threshold);
      for (const t of tiers) { if (v <= t.threshold) { pts = t.pts; break; } }
    } else if (factor.type === 'categorical') {
      const map = {};
      factor.values.forEach(fv => { map[fv.label] = fv.pts; });
      pts = map[v] || 0;
    } else if (factor.type === 'boolean') {
      pts = v ? factor.max_pts : 0;
    }

    total += pts;
  }
  return Math.min(total, 100);
}

function estimateScore() {
  const amount = parseFloat(document.getElementById('debt_amount')?.value) || 0;
  const age    = parseInt(document.getElementById('debt_age_days')?.value) || 0;
  const cs     = parseInt(document.getElementById('credit_score')?.value) || 0;
  const emp    = document.getElementById('employment_status')?.value || '';
  const assets = document.querySelector('input[name="owns_assets"][type="checkbox"]')?.checked ? 1 : 0;
  const prior  = document.querySelector('input[name="prior_payment"][type="checkbox"]')?.checked ? 1 : 0;

  const scoreEl = document.getElementById('previewScore');
  const recEl   = document.getElementById('previewRec');
  if (!scoreEl) return;

  const hasInput = amount > 0 || age > 0 || cs > 0 || emp !== '';
  if (!hasInput) {
    scoreEl.textContent = '—';
    scoreEl.style.color = '';
    recEl.textContent   = 'Fill in the form to see an estimate';
    recEl.style.color   = '';
    return;
  }

  const rules = window.SCORING_RULES;
  let total;

  if (rules) {
    total = scoreWithRules(rules, { amount, age, cs, emp, assets, prior });
  } else {
    // Hard-coded fallback matching default rules
    total = 0;
    if      (amount >= 25000) total += 30;
    else if (amount >= 15000) total += 24;
    else if (amount >= 8000)  total += 18;
    else if (amount >= 3000)  total += 10;
    else if (amount > 0)      total += 4;

    if      (age > 0 && age <= 90)  total += 20;
    else if (age <= 180)             total += 16;
    else if (age <= 365)             total += 10;
    else if (age <= 730)             total += 5;
    else if (age > 730)              total += 1;

    if      (cs >= 700) total += 20;
    else if (cs >= 650) total += 16;
    else if (cs >= 580) total += 10;
    else if (cs >= 500) total += 5;
    else if (cs >= 300) total += 1;

    const empMap = { Employed: 15, 'Self-Employed': 10, Unemployed: 2 };
    total += empMap[emp] || 0;
    total += assets ? 10 : 0;
    total += prior  ? 5  : 0;
    total = Math.min(total, 100);
  }

  scoreEl.textContent = total;

  const bands = rules?.score_bands || { high_min: 70, medium_min: 40 };
  let rec, color;
  if (total >= bands.high_min) {
    rec   = 'High Priority — Recommend Legal Action';
    color = '#22c55e';
  } else if (total >= bands.medium_min) {
    rec   = 'Medium Priority — Further Investigation Required';
    color = '#f59e0b';
  } else {
    rec   = 'Low Priority — Legal Action Not Recommended';
    color = '#ef4444';
  }
  scoreEl.style.color = color;
  recEl.textContent   = rec;
  recEl.style.color   = color;
}

// ── Rule Engine helpers (global so inline oninput handlers work) ───────────────

function computeCardMaxPts(card) {
  const type = card.dataset.type;
  let maxPts = 0;

  if (type === 'boolean') {
    maxPts = parseInt(card.querySelector('.bool-pts')?.value) || 0;
  } else if (type === 'categorical') {
    card.querySelectorAll('.cat-pts').forEach(el => {
      maxPts = Math.max(maxPts, parseInt(el.value) || 0);
    });
  } else {
    card.querySelectorAll('.tier-pts').forEach(el => {
      maxPts = Math.max(maxPts, parseInt(el.value) || 0);
    });
  }

  card.dataset.maxPts = maxPts;
  const weightEl = card.querySelector('.weight-val');
  if (weightEl) weightEl.textContent = maxPts;
  return maxPts;
}

function updateCardWeight(input) {
  const card = input.closest('.rule-card');
  if (!card) return;
  computeCardMaxPts(card);
  updateTotalWeight();
}

function updateTotalWeight() {
  let total = 0;
  document.querySelectorAll('.rule-card[data-key]').forEach(card => {
    total += parseInt(card.dataset.maxPts) || 0;
  });

  const totalEl = document.getElementById('total-weight');
  const fillEl  = document.getElementById('weight-fill');
  const wrapEl  = document.getElementById('weight-wrap');

  if (totalEl) totalEl.textContent = total;
  if (fillEl)  fillEl.style.width = Math.min(total, 100) + '%';
  if (wrapEl) {
    wrapEl.classList.toggle('pts-over', total > 100);
    wrapEl.classList.toggle('pts-ok',   total <= 100);
  }
}

function addTier(key) {
  const tbody = document.getElementById('tier-tbody-' + key);
  if (!tbody) return;
  const row = document.createElement('tr');
  row.innerHTML =
    '<td><input type="number" class="tier-threshold tier-input" value="0" min="0" oninput="updateCardWeight(this)"></td>' +
    '<td><input type="number" class="tier-pts tier-input" value="0" min="0" max="999" oninput="updateCardWeight(this)"></td>' +
    '<td><button type="button" class="tier-remove" onclick="removeTier(this)" title="Remove tier">\u00d7</button></td>';
  tbody.appendChild(row);
}

function removeTier(btn) {
  const row   = btn.closest('tr');
  const tbody = row.parentElement;
  if (tbody.children.length <= 1) {
    alert('A factor must have at least one tier.');
    return;
  }
  const card = row.closest('.rule-card');
  row.remove();
  if (card) { computeCardMaxPts(card); updateTotalWeight(); }
}

function buildRulesJSON() {
  const ruleName = document.getElementById('ruleset-name')?.value.trim() || 'Custom Ruleset';
  const highMin  = parseInt(document.getElementById('high_min')?.value) || 70;
  const medMin   = parseInt(document.getElementById('med_min')?.value) || 40;

  const factors = [];
  document.querySelectorAll('.rule-card[data-key]').forEach(card => {
    const key    = card.dataset.key;
    const type   = card.dataset.type;
    const label  = card.dataset.label;
    const maxPts = parseInt(card.dataset.maxPts) || 0;
    const factor = { key, type, label, max_pts: maxPts };

    if (type === 'tiered_gte' || type === 'tiered_lte') {
      factor.tiers = [];
      card.querySelectorAll('tbody.tier-tbody tr').forEach(row => {
        const threshold = parseFloat(row.querySelector('.tier-threshold')?.value) || 0;
        const pts = parseInt(row.querySelector('.tier-pts')?.value) || 0;
        factor.tiers.push({ threshold, pts });
      });
    } else if (type === 'categorical') {
      factor.values = [];
      card.querySelectorAll('tbody.cat-tbody tr').forEach(row => {
        const catLabel = row.querySelector('.cat-label')?.value || '';
        const pts = parseInt(row.querySelector('.cat-pts')?.value) || 0;
        factor.values.push({ label: catLabel, pts });
      });
    }

    factors.push(factor);
  });

  return {
    rule_name:   ruleName,
    score_bands: { high_min: highMin, medium_min: medMin },
    factors,
  };
}

function showRulesError(msg) {
  const el = document.getElementById('rules-error');
  if (el) {
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 5000);
  } else {
    alert('Error: ' + msg);
  }
}

// ── DOMContentLoaded ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {

  // Score form live preview
  const scoreForm = document.getElementById('scoreForm');
  if (scoreForm) {
    ['debt_amount', 'debt_age_days', 'credit_score', 'employment_status'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', estimateScore);
    });
    ['owns_assets', 'prior_payment'].forEach(function (name) {
      const el = document.querySelector('input[name="' + name + '"][type="checkbox"]');
      if (el) el.addEventListener('change', estimateScore);
    });
    estimateScore();
  }

  // Rule Engine page — only runs on /rules
  if (!document.getElementById('rules-page')) return;

  // Initialise card max-pts from rendered values
  document.querySelectorAll('.rule-card[data-key]').forEach(card => {
    computeCardMaxPts(card);
  });
  updateTotalWeight();

  // Keep low-threshold display in sync with medium input
  const medInput   = document.getElementById('med_min');
  const lowDisplay = document.getElementById('low-threshold');
  if (medInput && lowDisplay) {
    medInput.addEventListener('input', () => { lowDisplay.textContent = medInput.value; });
  }

  // Save button
  const saveBtn = document.getElementById('save-rules-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async function () {
      const rules = buildRulesJSON();
      this.disabled = true;
      this.textContent = 'Saving\u2026';
      try {
        const resp = await fetch('/rules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(rules),
        });
        const data = await resp.json();
        if (data.ok) {
          window.location.reload();
        } else {
          showRulesError(data.error || 'Failed to save rules');
          this.disabled = false;
          this.textContent = 'Save Rules';
        }
      } catch (e) {
        showRulesError('Network error: ' + e.message);
        this.disabled = false;
        this.textContent = 'Save Rules';
      }
    });
  }

  // Activate historical version buttons
  document.querySelectorAll('.activate-btn').forEach(btn => {
    btn.addEventListener('click', async function () {
      const id = this.dataset.ruleId;
      try {
        const resp = await fetch('/rules/activate/' + id, { method: 'POST' });
        const data = await resp.json();
        if (data.ok) window.location.reload();
        else showRulesError(data.error || 'Could not activate ruleset');
      } catch (e) {
        showRulesError('Network error: ' + e.message);
      }
    });
  });
});
