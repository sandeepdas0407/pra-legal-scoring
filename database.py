import sqlite3
import json
import os

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

    # Migrate: add rule_id column to score_results if not present
    try:
        cur.execute("ALTER TABLE score_results ADD COLUMN rule_id INTEGER")
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
         credit_score, employment_status, owns_assets, prior_payment, state)
        VALUES (:account_number, :debtor_name, :debt_amount, :debt_age_days,
                :credit_score, :employment_status, :owns_assets, :prior_payment, :state)
    """, data)
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
