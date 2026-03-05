"""
db.py — Attorney & Placement DB helpers
"""
import sqlite3
from database import get_db


# ── Attorney CRUD ─────────────────────────────────────────────────────────────

def get_all_attorneys():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*,
               COUNT(CASE WHEN p.status IN ('Placed','Active') THEN 1 END) AS active_cases
        FROM attorneys a
        LEFT JOIN placements p ON p.attorney_id = a.id
        GROUP BY a.id
        ORDER BY a.firm_name
    """).fetchall()
    conn.close()
    return rows


def get_attorney(attorney_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM attorneys WHERE id = ?", (attorney_id,)).fetchone()
    conn.close()
    return row


def create_attorney(data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attorneys (firm_name, contact_name, email, phone, states, max_capacity)
        VALUES (:firm_name, :contact_name, :email, :phone, :states, :max_capacity)
    """, data)
    conn.commit()
    attorney_id = cur.lastrowid
    conn.close()
    return attorney_id


def update_attorney(attorney_id, data):
    conn = get_db()
    conn.execute("""
        UPDATE attorneys
        SET firm_name=:firm_name, contact_name=:contact_name, email=:email,
            phone=:phone, states=:states, max_capacity=:max_capacity, is_active=:is_active
        WHERE id=:id
    """, {**data, "id": attorney_id})
    conn.commit()
    conn.close()


def deactivate_attorney(attorney_id):
    """Deactivate only if no Placed/Active placements."""
    conn = get_db()
    count = conn.execute("""
        SELECT COUNT(*) FROM placements
        WHERE attorney_id = ? AND status IN ('Placed', 'Active')
    """, (attorney_id,)).fetchone()[0]
    if count > 0:
        conn.close()
        return False, f"Cannot deactivate: {count} active case(s) still open."
    conn.execute("UPDATE attorneys SET is_active = 0 WHERE id = ?", (attorney_id,))
    conn.commit()
    conn.close()
    return True, "Attorney deactivated."


def get_attorneys_for_state(state):
    """Return active attorneys that handle the given state, ordered by available capacity."""
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*,
               COUNT(CASE WHEN p.status IN ('Placed','Active') THEN 1 END) AS active_cases,
               a.max_capacity - COUNT(CASE WHEN p.status IN ('Placed','Active') THEN 1 END) AS available
        FROM attorneys a
        LEFT JOIN placements p ON p.attorney_id = a.id
        WHERE a.is_active = 1
        GROUP BY a.id
        HAVING (a.states LIKE ? OR a.states LIKE ? OR a.states LIKE ? OR a.states = ?)
           AND available > 0
        ORDER BY available DESC
    """, (f"{state},%", f"%,{state},%", f"%,{state}", state)).fetchall()
    conn.close()
    return rows


# ── Placement CRUD ────────────────────────────────────────────────────────────

def get_all_placements(status_filter=None):
    conn = get_db()
    query = """
        SELECT p.*, a.firm_name, a.contact_name,
               ac.account_number, ac.debtor_name, ac.debt_amount, ac.state
        FROM placements p
        JOIN attorneys a  ON a.id = p.attorney_id
        JOIN accounts  ac ON ac.id = p.account_id
    """
    if status_filter:
        rows = conn.execute(query + " WHERE p.status = ? ORDER BY p.placed_at DESC",
                            (status_filter,)).fetchall()
    else:
        rows = conn.execute(query + " ORDER BY p.placed_at DESC").fetchall()
    conn.close()
    return rows


def get_placement(placement_id):
    conn = get_db()
    row = conn.execute("""
        SELECT p.*, a.firm_name, a.contact_name, a.email, a.phone,
               ac.account_number, ac.debtor_name, ac.debt_amount, ac.state,
               sr.legal_score, sr.recommendation
        FROM placements p
        JOIN attorneys a  ON a.id = p.attorney_id
        JOIN accounts  ac ON ac.id = p.account_id
        LEFT JOIN (
            SELECT account_id, legal_score, recommendation
            FROM score_results
            WHERE id IN (SELECT MAX(id) FROM score_results GROUP BY account_id)
        ) sr ON sr.account_id = p.account_id
        WHERE p.id = ?
    """, (placement_id,)).fetchone()
    conn.close()
    return row


def get_active_placement_for_account(account_id):
    """Return the most recent Placed/Active placement for an account, or None."""
    conn = get_db()
    row = conn.execute("""
        SELECT p.*, a.firm_name
        FROM placements p
        JOIN attorneys a ON a.id = p.attorney_id
        WHERE p.account_id = ? AND p.status IN ('Placed', 'Active')
        ORDER BY p.placed_at DESC LIMIT 1
    """, (account_id,)).fetchone()
    conn.close()
    return row


def get_placements_for_account(account_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, a.firm_name
        FROM placements p
        JOIN attorneys a ON a.id = p.attorney_id
        WHERE p.account_id = ?
        ORDER BY p.placed_at DESC
    """, (account_id,)).fetchall()
    conn.close()
    return rows


def create_placement(account_id, attorney_id, notes=""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO placements (account_id, attorney_id, status, notes)
        VALUES (?, ?, 'Placed', ?)
    """, (account_id, attorney_id, notes))
    conn.commit()
    placement_id = cur.lastrowid
    conn.close()
    return placement_id


def update_placement_status(placement_id, new_status, outcome_amount=None, notes=None):
    conn = get_db()
    fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [new_status]
    if outcome_amount is not None:
        fields.append("outcome_amount = ?")
        params.append(outcome_amount)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    params.append(placement_id)
    conn.execute(f"UPDATE placements SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_placement_stats():
    conn = get_db()
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Placed'            THEN 1 ELSE 0 END) AS placed,
            SUM(CASE WHEN status = 'Active'            THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'Settled'           THEN 1 ELSE 0 END) AS settled,
            SUM(CASE WHEN status = 'Judgment'          THEN 1 ELSE 0 END) AS judgment,
            SUM(CASE WHEN status = 'Closed-No Recovery' THEN 1 ELSE 0 END) AS closed_no_recovery,
            SUM(CASE WHEN status = 'Recalled'          THEN 1 ELSE 0 END) AS recalled,
            COALESCE(SUM(CASE WHEN status IN ('Settled','Judgment') THEN outcome_amount ELSE 0 END), 0) AS total_recovered
        FROM placements
    """).fetchone()
    conn.close()
    return row
