/**
 * PRA Legal Scoring — App JS
 *
 * - Live score preview on the scoring form (uses window.SCORING_RULES when injected)
 * - Rule Engine page interactions
 */

// ── Ruleset switcher (called by score form dropdown) ──────────────────────────

function onRulesetChange(ruleId) {
  if (window.ALL_RULESETS && window.ALL_RULESETS[String(ruleId)]) {
    window.SCORING_RULES = window.ALL_RULESETS[String(ruleId)];
  }
  estimateScore();
}

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
  if (!rules) return;

  const total = scoreWithRules(rules, { amount, age, cs, emp, assets, prior });
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

// ── Attorney auto-suggest ─────────────────────────────────────────────────────

async function loadPlacementSuggest(state) {
  const panel   = document.getElementById('suggest-panel');
  const listEl  = document.getElementById('suggest-list');
  const selectEl = document.getElementById('attorney_id');
  if (!panel || !listEl || !selectEl) return;

  const baseUrl = window.SUGGEST_URL || '/placements/attorneys/suggest';
  const resp = await fetch(baseUrl + '?state=' + encodeURIComponent(state));
  const attorneys = await resp.json();

  if (!attorneys.length) { panel.style.display = 'none'; return; }

  listEl.innerHTML = attorneys.map(a => `
    <div class="suggest-item">
      <div class="suggest-item-info">
        <span class="suggest-firm">${a.firm_name}</span>
        <span class="suggest-meta">${a.contact_name} &nbsp;·&nbsp; ${a.active_cases}/${a.max_capacity} cases &nbsp;·&nbsp; ${a.available} available</span>
      </div>
      <button type="button" class="suggest-select-btn" data-id="${a.id}">Select</button>
    </div>
  `).join('');

  listEl.querySelectorAll('.suggest-select-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      selectEl.value = this.dataset.id;
      listEl.querySelectorAll('.suggest-item').forEach(it => it.style.outline = '');
      this.closest('.suggest-item').style.outline = '2px solid var(--accent)';
    });
  });

  panel.style.display = 'block';
}

// ── Placement status AJAX update ──────────────────────────────────────────────

function initPlacementStatusForm() {
  const form      = document.getElementById('statusForm');
  const selectEl  = document.getElementById('statusSelect');
  const outcomeDiv = document.getElementById('outcomeField');
  const updateBtn = document.getElementById('updateBtn');
  const msgEl     = document.getElementById('updateMsg');
  if (!form || !window.PLACEMENT_ID) return;

  const outcomeStatuses = ['Settled', 'Judgment'];

  selectEl.addEventListener('change', function () {
    if (outcomeDiv) {
      outcomeDiv.style.display = outcomeStatuses.includes(this.value) ? '' : 'none';
    }
  });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const status       = selectEl.value;
    const outcomeInput = document.getElementById('outcomeAmount');
    const notesInput   = document.getElementById('statusNotes');
    const body = {
      status,
      outcome_amount: outcomeInput && outcomeInput.value ? parseFloat(outcomeInput.value) : null,
      notes: notesInput ? notesInput.value : null,
    };

    updateBtn.disabled = true;
    updateBtn.textContent = 'Saving…';

    const updateUrl = window.PLACEMENT_UPDATE_URL ||
      '/placements/' + window.PLACEMENT_ID + '/update';

    try {
      const resp = await fetch(updateUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (data.ok) {
        if (msgEl) { msgEl.style.display = 'block'; setTimeout(() => msgEl.style.display = 'none', 3000); }
        // Update badge on page
        const badge = document.querySelector('.page-hero .status-badge');
        if (badge) {
          badge.textContent = data.status;
          badge.className = 'status-badge status-' + data.status.toLowerCase().replace(/[^a-z]/g, '');
        }
      } else {
        alert('Error: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    }

    updateBtn.disabled = false;
    updateBtn.textContent = 'Update Status';
  });
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

  // Rule Engine page — only runs on /legal/rules
  if (!document.getElementById('rules-page')) {
    // Placement form — auto-suggest
    if (window.PLACEMENT_ACCOUNT_STATE) {
      loadPlacementSuggest(window.PLACEMENT_ACCOUNT_STATE);
    }
    // Placement detail — status AJAX form
    initPlacementStatusForm();
    return;
  }

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

  // Save button — uses injected URL
  const saveBtn = document.getElementById('save-rules-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async function () {
      const rules = buildRulesJSON();
      this.disabled = true;
      this.textContent = 'Saving\u2026';
      const saveUrl = window.RULES_SAVE_URL || '/legal/rules';
      try {
        const resp = await fetch(saveUrl, {
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

  // Activate historical version buttons — uses injected base URL
  document.querySelectorAll('.activate-btn').forEach(btn => {
    btn.addEventListener('click', async function () {
      const id = this.dataset.ruleId;
      const activateBase = window.RULES_ACTIVATE_BASE || '/legal/rules/activate/';
      try {
        const resp = await fetch(activateBase + id, { method: 'POST' });
        const data = await resp.json();
        if (data.ok) window.location.reload();
        else showRulesError(data.error || 'Could not activate ruleset');
      } catch (e) {
        showRulesError('Network error: ' + e.message);
      }
    });
  });

});
