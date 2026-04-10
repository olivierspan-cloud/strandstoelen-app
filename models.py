import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = os.environ.get("DB_PATH", "database.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def auto_migrate():
    """Safely add any missing tables or columns to an existing database.
    This means you do NOT need to delete database.db after updating."""
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()

    # Add avatar column if missing
    try:
        cur.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT 'wave'")
    except Exception: pass

    # Create reservations table if missing
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chair_id    INTEGER NOT NULL,
        date        TEXT    NOT NULL,
        time_slot   TEXT    NOT NULL,
        price       REAL    NOT NULL,
        reserved_by TEXT    NOT NULL,
        created_at  TEXT    NOT NULL,
        FOREIGN KEY (chair_id) REFERENCES chairs(id)
    )""")

    # Create notifications table if missing
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT NOT NULL,
        message    TEXT NOT NULL,
        type       TEXT NOT NULL DEFAULT 'info',
        created_at TEXT NOT NULL,
        is_read    INTEGER NOT NULL DEFAULT 0
    )""")

    # Create settings table if missing
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    cur.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('always_open','false')")

    # Add repair columns to chairs if missing
    try:
        cur.execute("ALTER TABLE chairs ADD COLUMN repair_reason TEXT")
    except Exception: pass
    try:
        cur.execute("ALTER TABLE chairs ADD COLUMN repair_status TEXT")
    except Exception: pass

    # Add time_slot and rented_by to rentals if missing
    try:
        cur.execute("ALTER TABLE rentals ADD COLUMN time_slot TEXT")
    except Exception: pass
    try:
        cur.execute("ALTER TABLE rentals ADD COLUMN rented_by TEXT")
    except Exception: pass

    conn.commit()
    conn.close()


# Run migration on import — safe to call multiple times
auto_migrate()


# ══════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════

def create_user(username, password, role="klant"):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username,password,role) VALUES (?,?,?)",
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
    u = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return u


def username_exists(username):
    conn = get_db()
    r = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return r is not None


def check_user_password(user, password):
    return check_password_hash(user["password"], password)


def change_password(username, new_password):
    conn = get_db()
    conn.execute(
        "UPDATE users SET password=? WHERE username=?",
        (generate_password_hash(new_password), username)
    )
    conn.commit()
    conn.close()


def update_avatar(username, avatar_choice):
    conn = get_db()
    try:
        conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT 'wave'")
        conn.commit()
    except Exception:
        pass
    conn.execute("UPDATE users SET avatar=? WHERE username=?", (avatar_choice, username))
    conn.commit()
    conn.close()


def get_avatar(username):
    conn = get_db()
    try:
        r = conn.execute("SELECT avatar FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        return r["avatar"] if r and r["avatar"] else "wave"
    except Exception:
        conn.close()
        return "wave"


def get_all_users():
    conn = get_db()
    rows = conn.execute("SELECT id, username, role, avatar FROM users ORDER BY id").fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════════════════════
# CHAIRS
# ══════════════════════════════════════════════════════════

def get_all_chairs():
    conn = get_db()
    chairs = conn.execute("SELECT * FROM chairs ORDER BY id").fetchall()
    conn.close()
    return chairs


def get_chair(cid):
    conn = get_db()
    c = conn.execute("SELECT * FROM chairs WHERE id=?", (cid,)).fetchone()
    conn.close()
    return c


def update_status(cid, status):
    conn = get_db()
    conn.execute("UPDATE chairs SET status=? WHERE id=?", (status, cid))
    conn.commit()
    conn.close()


def mark_broken(cid, reason):
    conn = get_db()
    conn.execute(
        "UPDATE chairs SET status='kapot', repair_reason=?, repair_status='kapot' WHERE id=?",
        (reason, cid)
    )
    conn.commit()
    conn.close()


def update_repair_status(cid, repair_status):
    conn = get_db()
    if repair_status == "gerepareerd":
        conn.execute(
            "UPDATE chairs SET status='vrij', repair_status='gerepareerd', repair_reason=NULL WHERE id=?",
            (cid,)
        )
    else:
        conn.execute(
            "UPDATE chairs SET repair_status=?, status='kapot' WHERE id=?",
            (repair_status, cid)
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
    r = conn.execute("""
        SELECT
          SUM(CASE WHEN status='vrij'  THEN 1 ELSE 0 END) vrij,
          SUM(CASE WHEN status='bezet' THEN 1 ELSE 0 END) bezet,
          SUM(CASE WHEN status='kapot' OR status='in_reparatie' THEN 1 ELSE 0 END) kapot
        FROM chairs
    """).fetchone()
    conn.close()
    return {"vrij": r["vrij"] or 0, "bezet": r["bezet"] or 0, "kapot": r["kapot"] or 0}


# ══════════════════════════════════════════════════════════
# RESERVATIONS (feature 1)
# ══════════════════════════════════════════════════════════

def add_reservation(chair_id, date, time_slot, price, username):
    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO reservations (chair_id, date, time_slot, price, reserved_by, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
        """, (chair_id, date, time_slot, price, username))
        conn.commit()
        conn.close()
    except Exception as e:
        raise e


def get_reservations_for_date(date):
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM reservations WHERE date=? ORDER BY chair_id", (date,)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_user_reservations(username, upcoming_only=True):
    try:
        conn = get_db()
        if upcoming_only:
            rows = conn.execute("""
                SELECT * FROM reservations
                WHERE reserved_by=? AND date >= date('now','localtime')
                ORDER BY date, time_slot
            """, (username,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reservations WHERE reserved_by=? ORDER BY date DESC", (username,)
            ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def cancel_reservation(res_id, username, is_admin=False):
    try:
        conn = get_db()
        if is_admin:
            conn.execute("DELETE FROM reservations WHERE id=?", (res_id,))
        else:
            conn.execute("DELETE FROM reservations WHERE id=? AND reserved_by=?", (res_id, username))
        conn.commit()
        conn.close()
    except Exception:
        pass


def chair_reserved_on(chair_id, date, time_slot):
    try:
        conn = get_db()
        r = conn.execute("""
            SELECT id FROM reservations WHERE chair_id=? AND date=? AND time_slot=?
        """, (chair_id, date, time_slot)).fetchone()
        conn.close()
        return r is not None
    except Exception:
        return False


def get_all_reservations(limit=50):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM reservations ORDER BY date DESC, chair_id LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_week_reservations():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT date, COUNT(*) as count, SUM(price) as revenue
            FROM reservations
            WHERE date BETWEEN date('now','localtime') AND date('now','localtime','+6 days')
            GROUP BY date ORDER BY date
        """).fetchall()
        conn.close()
        return [{"date": r["date"], "count": r["count"], "revenue": r["revenue"]} for r in rows]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════
# RENTALS
# ══════════════════════════════════════════════════════════

def add_rental(cid, price, time_slot, rented_by):
    conn = get_db()
    conn.execute(
        "INSERT INTO rentals (chair_id,price,time_slot,rented_by,date) VALUES (?,?,?,?,datetime('now','localtime'))",
        (cid, price, time_slot, rented_by)
    )
    conn.commit()
    conn.close()


def get_active_rental(cid):
    conn = get_db()
    r = conn.execute(
        "SELECT * FROM rentals WHERE chair_id=? ORDER BY date DESC LIMIT 1", (cid,)
    ).fetchone()
    conn.close()
    return r


def get_recent_rentals(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM rentals ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def get_user_rentals(username, limit=15):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM rentals WHERE rented_by=? ORDER BY date DESC LIMIT ?",
        (username, limit)
    ).fetchall()
    conn.close()
    return rows


def get_user_stats(username):
    conn = get_db()
    r = conn.execute("""
        SELECT COUNT(*) total_rentals, SUM(price) total_spent, MAX(date) last_rental
        FROM rentals WHERE rented_by=?
    """, (username,)).fetchone()
    conn.close()
    return {
        "total_rentals": r["total_rentals"] or 0,
        "total_spent":   r["total_spent"]   or 0.0,
        "last_rental":   r["last_rental"]   or "—",
    }


# ══════════════════════════════════════════════════════════
# REVENUE
# ══════════════════════════════════════════════════════════

def get_revenue_breakdown():
    conn = get_db()
    def q(sql): return conn.execute(sql).fetchone()[0] or 0
    r = {
        "day":    q("SELECT SUM(price) FROM rentals WHERE date(date)=date('now','localtime')"),
        "week":   q("SELECT SUM(price) FROM rentals WHERE strftime('%W-%Y',date)=strftime('%W-%Y','now','localtime')"),
        "month":  q("SELECT SUM(price) FROM rentals WHERE strftime('%m-%Y',date)=strftime('%m-%Y','now','localtime')"),
        "season": q("SELECT SUM(price) FROM rentals"),
    }
    conn.close()
    return r


def get_rentals_per_day(limit=7):
    conn = get_db()
    rows = conn.execute("""
        SELECT date(date) dag, SUM(price) totaal, COUNT(*) aantal
        FROM rentals GROUP BY dag ORDER BY dag DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"dag": r["dag"], "totaal": r["totaal"], "aantal": r["aantal"]} for r in rows]


def get_rentals_per_week(limit=8):
    conn = get_db()
    rows = conn.execute("""
        SELECT strftime('%W',date) week, SUM(price) totaal, COUNT(*) aantal
        FROM rentals GROUP BY week ORDER BY week DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"week": "W"+r["week"], "totaal": r["totaal"], "aantal": r["aantal"]} for r in rows]


def get_hourly_heatmap():
    """Returns avg rentals per hour of day (0–23) across all data."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT CAST(strftime('%H', date) AS INTEGER) as hour,
                   COUNT(*) as count
            FROM rentals
            GROUP BY hour ORDER BY hour
        """).fetchall()
        conn.close()
        heat = {r["hour"]: r["count"] for r in rows}
        return [{"hour": h, "count": heat.get(h, 0)} for h in range(10, 19)]
    except Exception:
        return [{"hour": h, "count": 0} for h in range(10, 19)]


def get_revenue_csv():
    """Return all rentals as list of dicts for CSV export."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT id, chair_id, rented_by, time_slot, price, date
            FROM rentals ORDER BY date DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════
# NOTIFICATIONS (feature 9)
# ══════════════════════════════════════════════════════════

def get_user_notifications(username):
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM notifications
            WHERE username=? ORDER BY created_at DESC LIMIT 15
        """, (username,)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def count_unread_notifications(username):
    try:
        conn = get_db()
        n = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE username=? AND is_read=0", (username,)
        ).fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def mark_notifications_read(username):
    try:
        conn = get_db()
        conn.execute("UPDATE notifications SET is_read=1 WHERE username=?", (username,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def add_notification(username, message, notif_type="info"):
    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO notifications (username, message, type, created_at, is_read)
            VALUES (?, ?, ?, datetime('now','localtime'), 0)
        """, (username, message, notif_type))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════

def get_setting(key):
    conn = get_db()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else None


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def is_always_open():
    return get_setting("always_open") == "true"