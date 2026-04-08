import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = os.environ.get("DB_PATH", "database.db")

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ── USERS ─────────────────────────────────────────────────
def create_user(username, password, role="klant"):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",
                     (username, generate_password_hash(password), role))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user(username):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close(); return u

def username_exists(username):
    conn = get_db()
    r = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    conn.close(); return r is not None

def check_user_password(user, password):
    return check_password_hash(user["password"], password)

# ── CHAIRS ────────────────────────────────────────────────
def get_all_chairs():
    conn = get_db()
    chairs = conn.execute("SELECT * FROM chairs ORDER BY id").fetchall()
    conn.close(); return chairs

def get_chair(cid):
    conn = get_db()
    c = conn.execute("SELECT * FROM chairs WHERE id=?", (cid,)).fetchone()
    conn.close(); return c

def update_status(cid, status):
    conn = get_db()
    conn.execute("UPDATE chairs SET status=? WHERE id=?", (status, cid))
    conn.commit(); conn.close()

def mark_broken(cid, reason):
    conn = get_db()
    conn.execute("UPDATE chairs SET status='kapot', repair_reason=?, repair_status='kapot' WHERE id=?",
                 (reason, cid))
    conn.commit(); conn.close()

def update_repair_status(cid, repair_status):
    conn = get_db()
    if repair_status == "gerepareerd":
        conn.execute("UPDATE chairs SET status='vrij', repair_status='gerepareerd', repair_reason=NULL WHERE id=?", (cid,))
    else:
        conn.execute("UPDATE chairs SET repair_status=?, status='kapot' WHERE id=?", (repair_status, cid))
    conn.commit(); conn.close()

def free_all_chairs():
    conn = get_db()
    conn.execute("UPDATE chairs SET status='vrij' WHERE status='bezet'")
    conn.commit(); conn.close()

def get_chair_stats():
    conn = get_db()
    r = conn.execute("""
        SELECT
          SUM(CASE WHEN status='vrij'  THEN 1 ELSE 0 END) vrij,
          SUM(CASE WHEN status='bezet' THEN 1 ELSE 0 END) bezet,
          SUM(CASE WHEN status='kapot' OR status='in_reparatie' THEN 1 ELSE 0 END) kapot
        FROM chairs""").fetchone()
    conn.close()
    return {"vrij": r["vrij"] or 0, "bezet": r["bezet"] or 0, "kapot": r["kapot"] or 0}

# ── RENTALS ───────────────────────────────────────────────
def add_rental(cid, price, time_slot, rented_by):
    conn = get_db()
    conn.execute("INSERT INTO rentals (chair_id,price,time_slot,rented_by,date) VALUES (?,?,?,?,datetime('now','localtime'))",
                 (cid, price, time_slot, rented_by))
    conn.commit(); conn.close()

def get_active_rental(cid):
    conn = get_db()
    r = conn.execute("SELECT * FROM rentals WHERE chair_id=? ORDER BY date DESC LIMIT 1", (cid,)).fetchone()
    conn.close(); return r

def get_recent_rentals(limit=20):
    conn = get_db()
    rows = conn.execute("SELECT * FROM rentals ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    conn.close(); return rows

# ── REVENUE ───────────────────────────────────────────────
def get_revenue_breakdown():
    conn = get_db()
    def q(sql): return conn.execute(sql).fetchone()[0] or 0
    r = {
        "day":    q("SELECT SUM(price) FROM rentals WHERE date(date)=date('now','localtime')"),
        "week":   q("SELECT SUM(price) FROM rentals WHERE strftime('%W-%Y',date)=strftime('%W-%Y','now','localtime')"),
        "month":  q("SELECT SUM(price) FROM rentals WHERE strftime('%m-%Y',date)=strftime('%m-%Y','now','localtime')"),
        "season": q("SELECT SUM(price) FROM rentals"),
    }
    conn.close(); return r

def get_rentals_per_day(limit=7):
    conn = get_db()
    rows = conn.execute("""
        SELECT date(date) dag, SUM(price) totaal, COUNT(*) aantal
        FROM rentals GROUP BY dag ORDER BY dag DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [{"dag": r["dag"], "totaal": r["totaal"], "aantal": r["aantal"]} for r in rows]

def get_rentals_per_week(limit=8):
    conn = get_db()
    rows = conn.execute("""
        SELECT strftime('%W',date) week, SUM(price) totaal, COUNT(*) aantal
        FROM rentals GROUP BY week ORDER BY week DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [{"week": "W"+r["week"], "totaal": r["totaal"], "aantal": r["aantal"]} for r in rows]

# ── SETTINGS ──────────────────────────────────────────────
def get_setting(key):
    conn = get_db()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close(); return r["value"] if r else None

def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    conn.commit(); conn.close()

def is_always_open():
    return get_setting("always_open") == "true"