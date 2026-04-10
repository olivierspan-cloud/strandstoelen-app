import sqlite3, os
from werkzeug.security import generate_password_hash

DB_NAME = os.environ.get("DB_PATH", "database.db")
conn = sqlite3.connect(DB_NAME)
cur  = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT    UNIQUE NOT NULL,
    password TEXT    NOT NULL,
    role     TEXT    NOT NULL DEFAULT 'klant',
    avatar   TEXT    DEFAULT 'wave'
);

CREATE TABLE IF NOT EXISTS chairs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    status         TEXT NOT NULL DEFAULT 'vrij',
    repair_reason  TEXT,
    repair_status  TEXT
);

CREATE TABLE IF NOT EXISTS rentals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chair_id  INTEGER NOT NULL,
    price     REAL    NOT NULL,
    time_slot TEXT,
    rented_by TEXT,
    date      TEXT    NOT NULL,
    FOREIGN KEY (chair_id) REFERENCES chairs(id)
);

CREATE TABLE IF NOT EXISTS reservations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chair_id    INTEGER NOT NULL,
    date        TEXT    NOT NULL,
    time_slot   TEXT    NOT NULL,
    price       REAL    NOT NULL,
    reserved_by TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (chair_id) REFERENCES chairs(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    message    TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'info',
    created_at TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
""")

# Default settings
cur.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('always_open','false')")
cur.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('onboarding_enabled','true')")

# Trigger: reset bezet→vrij after 18:00
cur.execute("""
CREATE TRIGGER IF NOT EXISTS reset_after_18
AFTER INSERT ON rentals
WHEN strftime('%H','now','localtime') >= '18'
BEGIN
    UPDATE chairs SET status='vrij' WHERE id=NEW.chair_id;
END
""")

# Seed 50 chairs
cur.execute("SELECT COUNT(*) FROM chairs")
if cur.fetchone()[0] == 0:
    for _ in range(50):
        cur.execute("INSERT INTO chairs (status) VALUES ('vrij')")
    print("  50 stoelen aangemaakt.")

def seed(username, password, role):
    cur.execute("SELECT id FROM users WHERE username=?", (username,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username,password,role) VALUES (?,?,?)",
            (username, generate_password_hash(password), role)
        )
        print(f"  Gebruiker: {username} ({role})")

# ── VERANDER DIT naar jouw eigen gegevens ──────────────
seed("olivier", "jouwwachtwoord", "admin")
seed("admin",   "admin123",       "admin")

conn.commit()
conn.close()
print("\n✅ Database klaar!")
print("   Admin: olivier / jouwwachtwoord")