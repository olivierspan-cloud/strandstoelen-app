import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = "database.db"
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# ── USERS ────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT    UNIQUE NOT NULL,
    password TEXT    NOT NULL,
    role     TEXT    NOT NULL DEFAULT 'klant'
)
""")

# ── CHAIRS ───────────────────────────────────────────────
# status: vrij | bezet | kapot | in_reparatie | gerepareerd
cursor.execute("""
CREATE TABLE IF NOT EXISTS chairs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    status         TEXT    NOT NULL DEFAULT 'vrij',
    repair_reason  TEXT,
    repair_status  TEXT
)
""")

# ── RENTALS ──────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS rentals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chair_id  INTEGER NOT NULL,
    price     REAL    NOT NULL,
    time_slot TEXT,
    rented_by TEXT,
    date      TEXT    NOT NULL,
    FOREIGN KEY (chair_id) REFERENCES chairs(id)
)
""")

# ── SETTINGS ─────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
""")

# Default: always_open = false
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('always_open', 'false')")

# ── TRIGGER: reset bezet → vrij after 18:00 ──────────────
cursor.execute("""
CREATE TRIGGER IF NOT EXISTS reset_after_18
AFTER INSERT ON rentals
WHEN strftime('%H', 'now', 'localtime') >= '18'
BEGIN
    UPDATE chairs SET status = 'vrij' WHERE id = NEW.chair_id;
END;
""")

# ── SEED: 50 CHAIRS ──────────────────────────────────────
cursor.execute("SELECT COUNT(*) FROM chairs")
if cursor.fetchone()[0] == 0:
    for _ in range(50):
        cursor.execute("INSERT INTO chairs (status) VALUES ('vrij')")
    print("  50 stoelen aangemaakt.")

# ── SEED: USERS ──────────────────────────────────────────
def seed_user(username, password, role):
    cursor.execute("SELECT id FROM users WHERE username=?", (username,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), role)
        )
        print(f"  Gebruiker aangemaakt: {username} ({role})")
    else:
        print(f"  Bestaat al: {username}")

print("Gebruikers aanmaken...")

# ── JOUW PERSOONLIJKE ADMIN ACCOUNT ──────────────────────
# Verander 'olivier' en 'jouwwachtwoord' naar wat je wilt!
seed_user("Admin", "Zitkuil123", "admin")
seed_user("admin",   "admin123",       "admin")

conn.commit()
conn.close()

print()
print("╔══════════════════════════════════╗")
print("║   Database klaar! ✅              ║")
print("╠══════════════════════════════════╣")
print("║  Admin gebruiker : olivier       ║")
print("║  Admin wachtwoord: jouwwachtwoord║")
print("╚══════════════════════════════════╝")