import sqlite3
import json
import os

# On Azure App Service (Linux) WEBSITE_INSTANCE_ID is set; use /home for persistence
if os.environ.get("WEBSITE_INSTANCE_ID"):
    DB_PATH = "/home/legal_scoring.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "legal_scoring.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT UNIQUE NOT NULL,
            debtor_name TEXT NOT NULL,
            debt_amount REAL NOT NULL,
            debt_age_days INTEGER NOT NULL,
            credit_score INTEGER NOT NULL,
            employment_status TEXT NOT NULL,
            owns_assets INTEGER NOT NULL DEFAULT 0,
            prior_payment INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS score_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            legal_score INTEGER NOT NULL,
            recommendation TEXT NOT NULL,
            score_breakdown TEXT NOT NULL,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS score_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL DEFAULT 'Default Ruleset',
            rules_json TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attorneys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firm_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            states TEXT NOT NULL,
            max_capacity INTEGER NOT NULL DEFAULT 50,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            attorney_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Placed',
            placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            outcome_amount REAL,
            notes TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (attorney_id) REFERENCES attorneys(id)
        );

        CREATE INDEX IF NOT EXISTS idx_placements_account  ON placements(account_id);
        CREATE INDEX IF NOT EXISTS idx_placements_attorney ON placements(attorney_id);
        CREATE INDEX IF NOT EXISTS idx_placements_status   ON placements(status);
    """)

    # Seed default ruleset if table is empty
    cur.execute("SELECT COUNT(*) FROM score_rules")
    if cur.fetchone()[0] == 0:
        from modules.legal_scoring.scoring_engine import get_default_rules
        cur.execute(
            "INSERT INTO score_rules (rule_name, rules_json, is_active) VALUES (?, ?, 1)",
            ("Default Ruleset", json.dumps(get_default_rules())),
        )

    # Seed sample data if empty
    cur.execute("SELECT COUNT(*) FROM accounts")
    if cur.fetchone()[0] == 0:
        sample_accounts = [
            ("PRA-2024-001", "James Whitfield",    12500.00, 180, 620, "Employed",        1, 1, "TX"),
            ("PRA-2024-002", "Maria Gonzalez",      3200.00, 540, 480, "Unemployed",      0, 0, "FL"),
            ("PRA-2024-003", "Robert Chen",        28000.00,  90, 710, "Employed",        1, 1, "CA"),
            ("PRA-2024-004", "Linda Okafor",        8750.00, 365, 555, "Self-Employed",   1, 0, "NY"),
            ("PRA-2024-005", "Thomas Harrington",   1100.00, 720, 430, "Unemployed",      0, 0, "OH"),
            ("PRA-2024-006", "Sarah Mitchell",     45000.00,  60, 680, "Employed",        1, 1, "GA"),
            ("PRA-2024-007", "David Patel",         6400.00, 450, 510, "Employed",        0, 1, "IL"),
            ("PRA-2024-008", "Karen Thompson",     19800.00, 200, 640, "Self-Employed",   1, 0, "AZ"),
            ("PRA-2024-009", "Michael Brooks",      2300.00, 900, 390, "Unemployed",      0, 0, "PA"),
            ("PRA-2024-010", "Angela Rivera",      33500.00, 120, 695, "Employed",        1, 1, "NV"),
        ]
        cur.executemany("""
            INSERT INTO accounts
            (account_number, debtor_name, debt_amount, debt_age_days,
             credit_score, employment_status, owns_assets, prior_payment, state)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, sample_accounts)

    # Auto-score the sample accounts so the dashboard looks populated
    cur.execute("SELECT COUNT(*) FROM score_results")
    if cur.fetchone()[0] == 0:
        from modules.legal_scoring.scoring_engine import score_account, get_default_rules
        rules = get_default_rules()
        cur.execute("SELECT * FROM accounts")
        for row in cur.fetchall():
            data = dict(row)
            result = score_account(data, rules=rules)
            cur.execute("""
                INSERT INTO score_results (account_id, legal_score, recommendation, score_breakdown)
                VALUES (?,?,?,?)
            """, (data["id"], result["legal_score"], result["recommendation"],
                  json.dumps(result["breakdown"])))

    # Seed attorneys if empty
    cur.execute("SELECT COUNT(*) FROM attorneys")
    if cur.fetchone()[0] == 0:
        sample_attorneys = [
            ("Harrington & Associates",  "Carol Harrington", "c.harrington@harringtonlaw.com", "214-555-0101", "TX,OK,AR,LA", 60),
            ("Pacific Legal Group",       "James Tanaka",     "j.tanaka@pacificlegal.com",      "415-555-0202", "CA,OR,WA,NV", 80),
            ("Southeastern Recovery Law", "Maria Santos",     "m.santos@serecovery.com",        "404-555-0303", "FL,GA,SC,NC", 70),
            ("Midwestern Debt Solutions", "Robert Kowalski",  "r.kowalski@mwdebt.com",          "312-555-0404", "IL,IN,OH,MI", 50),
            ("Northeast Collections LLC", "Patricia Dunne",   "p.dunne@necollections.com",      "212-555-0505", "NY,NJ,CT,PA", 65),
        ]
        cur.executemany("""
            INSERT INTO attorneys
            (firm_name, contact_name, email, phone, states, max_capacity)
            VALUES (?,?,?,?,?,?)
        """, sample_attorneys)

    # ── Eligibility tables ────────────────────────────────────────────────────
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS eligibility_runs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_name       TEXT    NOT NULL,
            min_frv        REAL    NOT NULL DEFAULT 500.0,
            run_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_accounts INTEGER NOT NULL DEFAULT 0,
            eligible_count INTEGER NOT NULL DEFAULT 0,
            excluded_count INTEGER NOT NULL DEFAULT 0,
            below_frv_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS eligibility_results (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id                 INTEGER NOT NULL,
            account_id             INTEGER NOT NULL,
            frv                    REAL    NOT NULL,
            gross_recovery_estimate REAL   NOT NULL,
            legal_cost_estimate    REAL    NOT NULL,
            recovery_probability   REAL    NOT NULL,
            is_frv_eligible        INTEGER NOT NULL DEFAULT 0,
            is_excluded            INTEGER NOT NULL DEFAULT 0,
            exclusion_reasons      TEXT    NOT NULL DEFAULT '[]',
            is_legal_eligible      INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (run_id)    REFERENCES eligibility_runs(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_elig_results_run     ON eligibility_results(run_id);
        CREATE INDEX IF NOT EXISTS idx_elig_results_account ON eligibility_results(account_id);
    """)

    # Migrate: add rule_id column to score_results if not present
    try:
        cur.execute("ALTER TABLE score_results ADD COLUMN rule_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migrate: add exclusion flag columns to accounts if not present
    for col in ('is_bankruptcy', 'is_sol_expired', 'is_disputed', 'is_military', 'is_deceased'):
        try:
            cur.execute(f"ALTER TABLE accounts ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()
    conn.close()


def get_all_accounts():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, sr.legal_score, sr.recommendation, sr.scored_at
        FROM accounts a
        LEFT JOIN (
            SELECT account_id, legal_score, recommendation, scored_at
            FROM score_results
            WHERE id IN (SELECT MAX(id) FROM score_results GROUP BY account_id)
        ) sr ON a.id = sr.account_id
        ORDER BY a.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def get_account(account_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return row


def create_account(data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO accounts
        (account_number, debtor_name, debt_amount, debt_age_days,
         credit_score, employment_status, owns_assets, prior_payment, state,
         is_bankruptcy, is_sol_expired, is_disputed, is_military, is_deceased)
        VALUES (:account_number, :debtor_name, :debt_amount, :debt_age_days,
                :credit_score, :employment_status, :owns_assets, :prior_payment, :state,
                :is_bankruptcy, :is_sol_expired, :is_disputed, :is_military, :is_deceased)
    """, {
        **data,
        'is_bankruptcy':  data.get('is_bankruptcy', 0),
        'is_sol_expired': data.get('is_sol_expired', 0),
        'is_disputed':    data.get('is_disputed', 0),
        'is_military':    data.get('is_military', 0),
        'is_deceased':    data.get('is_deceased', 0),
    })
    conn.commit()
    account_id = cur.lastrowid
    conn.close()
    return account_id


def save_score(account_id, legal_score, recommendation, breakdown_json, rule_id=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO score_results (account_id, legal_score, recommendation, score_breakdown, rule_id)
        VALUES (?,?,?,?,?)
    """, (account_id, legal_score, recommendation, breakdown_json, rule_id))
    conn.commit()
    conn.close()


def get_score_history(account_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT sr.*, COALESCE(r.rule_name, 'Default') as rule_name_used
        FROM score_results sr
        LEFT JOIN score_rules r ON sr.rule_id = r.id
        WHERE sr.account_id = ?
        ORDER BY sr.scored_at DESC
    """, (account_id,)).fetchall()
    conn.close()
    return rows


def get_ruleset_by_id(rule_id: int):
    """Return a ruleset dict by its id, or None if not found."""
    conn = get_db()
    row = conn.execute("SELECT rules_json FROM score_rules WHERE id = ?", (rule_id,)).fetchone()
    conn.close()
    return json.loads(row["rules_json"]) if row else None


# ── Rule Engine helpers ──────────────────────────────────────────────────────

def get_active_rules() -> dict:
    """Return the active ruleset as a dict, falling back to defaults if none."""
    conn = get_db()
    row = conn.execute(
        "SELECT rules_json FROM score_rules WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["rules_json"])
    from modules.legal_scoring.scoring_engine import get_default_rules
    return get_default_rules()


def save_rules(rule_name: str, rules_dict: dict):
    """Insert a new ruleset row, activate it, and deactivate all others."""
    conn = get_db()
    conn.execute("UPDATE score_rules SET is_active = 0")
    conn.execute(
        "INSERT INTO score_rules (rule_name, rules_json, is_active) VALUES (?, ?, 1)",
        (rule_name, json.dumps(rules_dict)),
    )
    conn.commit()
    conn.close()


def activate_rules(rule_id: int):
    """Set the given rule version as active, deactivate all others."""
    conn = get_db()
    conn.execute("UPDATE score_rules SET is_active = 0")
    conn.execute("UPDATE score_rules SET is_active = 1 WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()


def get_rules_history():
    """Return all rule versions ordered newest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM score_rules ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows


# ── Eligibility helpers ───────────────────────────────────────────────────────

def get_eligible_accounts_for_placement():
    """
    Return accounts that are legal eligible from the most recent eligibility run
    and do not currently have an active attorney placement, ordered by FRV desc.
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*,
               er.frv,
               er.recovery_probability,
               er.gross_recovery_estimate,
               er.legal_cost_estimate,
               sr.legal_score,
               sr.recommendation,
               run.run_name,
               run.run_at
        FROM eligibility_results er
        JOIN eligibility_runs run ON run.id = er.run_id
        JOIN accounts a ON a.id = er.account_id
        LEFT JOIN (
            SELECT account_id, legal_score, recommendation
            FROM score_results
            WHERE id IN (SELECT MAX(id) FROM score_results GROUP BY account_id)
        ) sr ON sr.account_id = a.id
        WHERE er.run_id = (SELECT MAX(id) FROM eligibility_runs)
          AND er.is_legal_eligible = 1
          AND a.id NOT IN (
              SELECT account_id FROM placements WHERE status IN ('Placed', 'Active')
          )
        ORDER BY er.frv DESC
    """).fetchall()
    conn.close()
    return rows


def get_active_placement_account_ids():
    """Return a set of account IDs that have an active (Placed/Active) placement."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT account_id FROM placements
        WHERE status IN ('Placed', 'Active')
    """).fetchall()
    conn.close()
    return {row['account_id'] for row in rows}


def create_eligibility_run(run_name, min_frv, total, eligible, excluded, below_frv):
    """Insert a new eligibility run record and return its id."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO eligibility_runs
            (run_name, min_frv, total_accounts, eligible_count, excluded_count, below_frv_count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (run_name, min_frv, total, eligible, excluded, below_frv))
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def save_eligibility_results(run_id, results):
    """Bulk-insert eligibility results for a run."""
    conn = get_db()
    conn.executemany("""
        INSERT INTO eligibility_results
            (run_id, account_id, frv, gross_recovery_estimate, legal_cost_estimate,
             recovery_probability, is_frv_eligible, is_excluded, exclusion_reasons, is_legal_eligible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            run_id,
            r['account_id'],
            r['frv'],
            r['gross_recovery_estimate'],
            r['legal_cost_estimate'],
            r['recovery_probability'],
            r['is_frv_eligible'],
            r['is_excluded'],
            json.dumps(r['exclusion_reasons']),
            r['is_legal_eligible'],
        )
        for r in results
    ])
    conn.commit()
    conn.close()


def get_eligibility_runs():
    """Return all eligibility runs, newest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM eligibility_runs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows


def get_eligibility_run(run_id):
    """Return a single eligibility run by id."""
    conn = get_db()
    row  = conn.execute(
        "SELECT * FROM eligibility_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()
    return row


def get_eligibility_results(run_id, tab='eligible'):
    """
    Return eligibility result rows joined with account details for a given run.
    tab: 'eligible' | 'excluded' | 'below_frv' | 'all'
    """
    filters = {
        'eligible':  "WHERE er.run_id = ? AND er.is_legal_eligible = 1",
        'excluded':  "WHERE er.run_id = ? AND er.is_excluded = 1 AND er.is_frv_eligible = 1",
        'below_frv': "WHERE er.run_id = ? AND er.is_frv_eligible = 0",
        'all':       "WHERE er.run_id = ?",
    }
    where = filters.get(tab, filters['all'])

    conn = get_db()
    rows = conn.execute(f"""
        SELECT er.*,
               a.account_number, a.debtor_name, a.debt_amount, a.state,
               a.credit_score, a.employment_status, a.owns_assets, a.prior_payment,
               a.debt_age_days
        FROM eligibility_results er
        JOIN accounts a ON a.id = er.account_id
        {where}
        ORDER BY er.frv DESC
    """, (run_id,)).fetchall()
    conn.close()

    # Parse exclusion_reasons JSON and attach as a list attribute
    parsed = []
    for row in rows:
        d = dict(row)
        d['exclusion_reasons_list'] = json.loads(d.get('exclusion_reasons') or '[]')
        parsed.append(d)
    return parsed
