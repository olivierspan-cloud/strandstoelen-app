from flask import Blueprint, render_template, redirect, request, session, flash, jsonify
from models import (
    get_user, check_user_password, create_user, username_exists,
    get_all_chairs, get_chair, update_status, add_rental,
    mark_broken, update_repair_status, free_all_chairs,
    get_active_rental, get_revenue_breakdown, get_recent_rentals,
    get_chair_stats, get_rentals_per_day, get_rentals_per_week,
    is_always_open, get_setting, set_setting
)
from datetime import datetime

main_routes = Blueprint("main", __name__)


# ── HELPERS ──────────────────────────────────────────────

def logged_in():
    return "user" in session

def is_admin():
    return session.get("role") == "admin"

def get_price_and_slot():
    """Return (price, slot) based on time, or (None, None) if closed."""
    if is_always_open():
        hour = datetime.now().hour
        return (10.0, "15:00–18:00") if hour >= 15 else (12.5, "10:00–18:00")
    hour = datetime.now().hour
    if hour < 10 or hour >= 18:
        return None, None
    return (10.0, "15:00–18:00") if hour >= 15 else (12.5, "10:00–18:00")


# ── REGISTER ─────────────────────────────────────────────

@main_routes.route("/register", methods=["GET", "POST"])
def register():
    if logged_in():
        return redirect("/")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if len(username) < 3:
            flash("Gebruikersnaam moet minimaal 3 tekens zijn.", "error")
        elif len(password) < 4:
            flash("Wachtwoord moet minimaal 4 tekens zijn.", "error")
        elif password != confirm:
            flash("Wachtwoorden komen niet overeen.", "error")
        elif username_exists(username):
            flash("Deze gebruikersnaam is al bezet.", "error")
        else:
            if create_user(username, password, role="klant"):
                user = get_user(username)
                session["user"] = user["username"]
                session["role"] = user["role"]
                flash(f"Welkom, {username}! Je account is aangemaakt. 🎉", "success")
                return redirect("/")
            else:
                flash("Er ging iets mis. Probeer opnieuw.", "error")

    return render_template("register.html")


# ── LOGIN ─────────────────────────────────────────────────

@main_routes.route("/login", methods=["GET", "POST"])
def login():
    if logged_in():
        return redirect("/")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user(username)
        if user and check_user_password(user, password):
            session["user"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welkom terug, {user['username']}! 👋", "success")
            return redirect("/")
        flash("Onjuiste gebruikersnaam of wachtwoord.", "error")
    return render_template("login.html")


@main_routes.route("/logout")
def logout():
    name = session.get("user", "")
    session.clear()
    flash(f"Tot ziens, {name}! 👋", "info")
    return redirect("/")


# ── INDEX ─────────────────────────────────────────────────

@main_routes.route("/")
def index():
    chairs       = get_all_chairs()
    stats        = get_chair_stats()
    price, slot  = get_price_and_slot()
    always_open  = is_always_open()

    # Build renter map: chair_id → username
    renter_map = {}
    for chair in chairs:
        if chair["status"] == "bezet":
            rental = get_active_rental(chair["id"])
            if rental:
                renter_map[chair["id"]] = rental["rented_by"]

    return render_template(
        "index.html",
        chairs=chairs,
        stats=stats,
        user=session.get("user"),
        role=session.get("role"),
        current_price=price,
        current_slot=slot,
        always_open=always_open,
        renter_map=renter_map,
        now=datetime.now(),
    )


# ── RENT ─────────────────────────────────────────────────

@main_routes.route("/rent/<int:id>")
def rent_chair(id):
    if not logged_in():
        flash("Je moet ingelogd zijn om een stoel te huren.", "error")
        return redirect("/login")

    chair = get_chair(id)
    if not chair or chair["status"] != "vrij":
        flash(f"Stoel {id} is niet beschikbaar.", "error")
        return redirect("/")

    price, slot = get_price_and_slot()
    if price is None:
        flash("Verhuur is alleen mogelijk tussen 10:00 en 18:00.", "error")
        return redirect("/")

    update_status(id, "bezet")
    add_rental(id, price, slot, rented_by=session["user"])
    flash(f"Stoel {id} succesvol verhuurd voor €{price:.2f} ({slot}). ✅", "success")
    return redirect("/")


# ── FREE (renter or admin) ────────────────────────────────

@main_routes.route("/free/<int:id>")
def free_chair(id):
    if not logged_in():
        flash("Je moet ingelogd zijn.", "error")
        return redirect("/login")

    chair = get_chair(id)
    if not chair or chair["status"] != "bezet":
        flash("Deze stoel is niet bezet.", "error")
        return redirect("/")

    rental = get_active_rental(id)
    renter = rental["rented_by"] if rental else None

    if not is_admin() and session["user"] != renter:
        flash("Je kunt alleen je eigen gehuurde stoel terugbrengen.", "error")
        return redirect("/")

    update_status(id, "vrij")
    flash(f"Stoel {id} teruggebracht. 🪑", "success")
    return redirect("/")


# ── MARK BROKEN (any logged-in user) ─────────────────────

@main_routes.route("/broken/<int:id>", methods=["POST"])
def broken_chair(id):
    if not logged_in():
        flash("Je moet ingelogd zijn.", "error")
        return redirect("/login")

    chair = get_chair(id)
    if not chair:
        flash("Stoel niet gevonden.", "error")
        return redirect("/")
    if chair["status"] == "bezet":
        flash("Stoel is bezet — eerst terugbrengen.", "error")
        return redirect("/")
    if chair["status"] in ("kapot", "in_reparatie"):
        flash("Stoel is al als kapot gemarkeerd.", "error")
        return redirect("/")

    reason = request.form.get("reason", "").strip() or "Geen reden opgegeven"
    mark_broken(id, reason)
    flash(f"Stoel {id} als kapot gemeld: '{reason}'. 🔧", "info")
    return redirect("/")


# ── REPAIR STATUS (admin only) ────────────────────────────

@main_routes.route("/repair-status/<int:id>", methods=["POST"])
def repair_status(id):
    if not is_admin():
        flash("Alleen de beheerder kan de reparatiestatus aanpassen.", "error")
        return redirect("/")

    new_status = request.form.get("repair_status")
    if new_status not in ("kapot", "in_reparatie", "gerepareerd"):
        flash("Ongeldige reparatiestatus.", "error")
        return redirect("/beheer")

    update_repair_status(id, new_status)
    label = {"kapot": "Kapot", "in_reparatie": "In reparatie", "gerepareerd": "Gerepareerd ✅"}
    flash(f"Stoel {id}: reparatiestatus → {label[new_status]}", "success")
    return redirect("/beheer")


# ── FREE ALL (admin only) ─────────────────────────────────

@main_routes.route("/free-all")
def free_all():
    if not is_admin():
        flash("Geen toegang.", "error")
        return redirect("/")
    free_all_chairs()
    flash("Alle bezette stoelen zijn vrijgemaakt (einde dag). 🌅", "info")
    return redirect("/")


# ── TOGGLE ALWAYS OPEN (admin only) ──────────────────────

@main_routes.route("/toggle-always-open", methods=["POST"])
def toggle_always_open():
    if not is_admin():
        return jsonify({"error": "Geen toegang"}), 403
    current = get_setting("always_open") == "true"
    new_val = "false" if current else "true"
    set_setting("always_open", new_val)
    return jsonify({"always_open": new_val == "true"})


# ── BEHEER (admin only) ───────────────────────────────────

@main_routes.route("/beheer")
def beheer():
    if not is_admin():
        flash("Alleen beheerders hebben toegang.", "error")
        return redirect("/")

    chairs      = get_all_chairs()
    revenue     = get_revenue_breakdown()
    recent      = get_recent_rentals(20)
    stats       = get_chair_stats()
    day_data    = get_rentals_per_day(7)
    week_data   = get_rentals_per_week(8)
    always_open = is_always_open()

    # Broken chairs needing attention
    broken_chairs = [c for c in chairs if c["status"] in ("kapot", "in_reparatie")]

    return render_template(
        "beheer.html",
        revenue=revenue,
        recent=recent,
        stats=stats,
        day_data=day_data,
        week_data=week_data,
        always_open=always_open,
        broken_chairs=broken_chairs,
        user=session.get("user"),
    )


# ── JSON API ─────────────────────────────────────────────

@main_routes.route("/api/chairs")
def api_chairs():
    chairs = get_all_chairs()
    return jsonify([{"id": c["id"], "status": c["status"]} for c in chairs])

@main_routes.route("/api/stats")
def api_stats():
    return jsonify(get_chair_stats())

@main_routes.route("/api/settings")
def api_settings():
    return jsonify({"always_open": is_always_open()})