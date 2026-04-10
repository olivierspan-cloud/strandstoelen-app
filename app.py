import os
from flask import Flask, redirect, flash
from routes import main_routes

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "strandgeheim_verander_dit_2026!")
app.register_blueprint(main_routes)

# ── Rate limiting — feature 14 ─────────────────────────────
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(get_remote_address, app=app, storage_uri="memory://",
                      default_limits=[])
    # 10 login attempts per minute per IP
    limiter.limit("10 per minute", error_message="Te veel pogingen.")(
        app.view_functions.get("main.login") or (lambda: None)
    )

    @app.errorhandler(429)
    def rate_limit_error(e):
        flash("Te veel inlogpogingen. Wacht even en probeer opnieuw.", "error")
        return redirect("/login"), 429

except ImportError:
    print("⚠️  flask-limiter niet beschikbaar. Installeer: pip install flask-limiter")

# ── APScheduler — feature 4: auto einde dag om 18:00 ────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    import atexit

    def auto_einde_dag():
        from models import free_all_chairs
        from datetime import datetime
        free_all_chairs()
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] ✅ Auto einde dag — stoelen vrijgemaakt.")

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(auto_einde_dag, trigger="cron", hour=18, minute=0, id="einde_dag")
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    print("✅ APScheduler actief — automatisch vrijmaken om 18:00.")

except ImportError:
    print("⚠️  APScheduler niet beschikbaar. Installeer: pip install APScheduler")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)