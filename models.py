import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "database.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════

def create_user(username, password, role="klant"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return user


def username_exists(username):
    conn = get_db()
    result = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return result is not None


def check_user_password(user, password):
    return check_password_hash(user["password"], password)


# ══════════════════════════════════════════════
# CHAIRS
# ══════════════════════════════════════════════

def get_all_chairs():
    conn = get_db()
    chairs = conn.execute("SELECT * FROM chairs ORDER BY id").fetchall()
    conn.close()
    return chairs


def get_chair(chair_id):
    conn = get_db()
    chair = conn.execute("SELECT * FROM chairs WHERE id=?", (chair_id,)).fetchone()
    conn.close()
    return chair


def update_status(chair_id, status):
    conn = get_db()
    conn.execute("UPDATE chairs SET status=? WHERE id=?", (status, chair_id))
    conn.commit()
    conn.close()


def mark_broken(chair_id, reason):
    """Mark a chair as kapot with a reason."""
    conn = get_db()
    conn.execute(
        "UPDATE chairs SET status='kapot', repair_reason=?, repair_status='kapot' WHERE id=?",
        (reason, chair_id)
    )
    conn.commit()
    conn.close()


def update_repair_status(chair_id, repair_status):
    """
    Admin-only: update repair_status.
    repair_status options: kapot | in_reparatie | gerepareerd
    When gerepareerd: also reset chair status to 'vrij'.
    """
    conn = get_db()
    if repair_status == "gerepareerd":
        conn.execute(
            """UPDATE chairs
               SET status='vrij', repair_status='gerepareerd', repair_reason=NULL
               WHERE id=?""",
            (chair_id,)
        )
    else:
        chair_status = "kapot" if repair_status == "kapot" else "kapot"
        conn.execute(
            "UPDATE chairs SET repair_status=?, status=? WHERE id=?",
            (repair_status, chair_status, chair_id)
        )
    conn.commit()
    conn.close()


def free_all_chairs():
    conn = get_db()
    conn.execute("UPDATE chairs SET status='vrij' WHERE status='bezet'")
    conn.commit()
    conn.close()


def get_chair_stats():
    conn = get_db()
    row = conn.execute("""
        SELECT
            SUM(CASE WHEN status='vrij'          THEN 1 ELSE 0 END) AS vrij,
            SUM(CASE WHEN status='bezet'         THEN 1 ELSE 0 END) AS bezet,
            SUM(CASE WHEN status='kapot'         THEN 1 ELSE 0 END) AS kapot,
            SUM(CASE WHEN repair_status='in_reparatie' THEN 1 ELSE 0 END) AS in_reparatie
        FROM chairs
    """).fetchone()
    conn.close()
    return {
        "vrij":         row["vrij"]         or 0,
        "bezet":        row["bezet"]        or 0,
        "kapot":        row["kapot"]        or 0,
        "in_reparatie": row["in_reparatie"] or 0,
    }


# ══════════════════════════════════════════════
# RENTALS
# ══════════════════════════════════════════════

def add_rental(chair_id, price, time_slot, rented_by):
    conn = get_db()
    conn.execute(
        """INSERT INTO rentals (chair_id, price, time_slot, rented_by, date)
           VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
        (chair_id, price, time_slot, rented_by)
    )
    conn.commit()
    conn.close()


def get_active_rental(chair_id):
    conn = get_db()
    rental = conn.execute(
        "SELECT * FROM rentals WHERE chair_id=? ORDER BY date DESC LIMIT 1",
        (chair_id,)
    ).fetchone()
    conn.close()
    return rental


def get_recent_rentals(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM rentals ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════════
# REVENUE
# ══════════════════════════════════════════════

def get_revenue_breakdown():
    conn = get_db()

    def fetch(sql):
        return conn.execute(sql).fetchone()[0] or 0

    day    = fetch("SELECT SUM(price) FROM rentals WHERE date(date)=date('now','localtime')")
    week   = fetch("SELECT SUM(price) FROM rentals WHERE strftime('%W-%Y',date)=strftime('%W-%Y','now','localtime')")
    month  = fetch("SELECT SUM(price) FROM rentals WHERE strftime('%m-%Y',date)=strftime('%m-%Y','now','localtime')")
    season = fetch("SELECT SUM(price) FROM rentals")

    conn.close()
    return {"day": day, "week": week, "month": month, "season": season}


def get_rentals_per_day(limit=7):
    conn = get_db()
    rows = conn.execute("""
        SELECT date(date) AS dag, SUM(price) AS totaal, COUNT(*) AS aantal
        FROM rentals GROUP BY dag ORDER BY dag DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"dag": r["dag"], "totaal": r["totaal"], "aantal": r["aantal"]} for r in rows]


def get_rentals_per_week(limit=8):
    conn = get_db()
    rows = conn.execute("""
        SELECT strftime('%W', date) AS week, SUM(price) AS totaal, COUNT(*) AS aantal
        FROM rentals GROUP BY week ORDER BY week DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"week": "W" + r["week"], "totaal": r["totaal"], "aantal": r["aantal"]} for r in rows]


# ══════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════

def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def is_always_open():
    return get_setting("always_open") == "true"