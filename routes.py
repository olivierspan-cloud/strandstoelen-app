from flask import Blueprint, render_template, redirect, request, session, flash, jsonify
from models import *
from datetime import datetime

main_routes = Blueprint("main", __name__)

BROKEN_REASONS = [
    "Poot gebroken of los",
    "Stof gescheurd of beschadigd",
    "Frame verbogen",
    "Schroef of bout ontbreekt",
    "Klapstoel werkt niet",
    "Roestschade",
    "anders",
]

def logged_in():  return "user" in session
def is_admin():   return session.get("role") == "admin"

def get_price_and_slot():
    if is_always_open():
        h = datetime.now().hour
        return (10.0, "15:00–18:00") if h >= 15 else (12.5, "10:00–18:00")
    h = datetime.now().hour
    if h < 10 or h >= 18: return None, None
    return (10.0, "15:00–18:00") if h >= 15 else (12.5, "10:00–18:00")

# ── AUTH ──────────────────────────────────────────────────

@main_routes.route("/register", methods=["GET","POST"])
def register():
    if logged_in(): return redirect("/")
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        c = request.form.get("confirm","")
        if len(u) < 3:          flash("Gebruikersnaam minimaal 3 tekens.", "error")
        elif len(p) < 4:        flash("Wachtwoord minimaal 4 tekens.", "error")
        elif p != c:            flash("Wachtwoorden komen niet overeen.", "error")
        elif username_exists(u): flash("Gebruikersnaam al in gebruik.", "error")
        else:
            create_user(u, p, "klant")
            user = get_user(u)
            session["user"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welkom, {u}! Account aangemaakt. 🎉", "success")
            return redirect("/")
    return render_template("register.html")

@main_routes.route("/login", methods=["GET","POST"])
def login():
    if logged_in(): return redirect("/")
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        user = get_user(u)
        if user and check_user_password(user, p):
            session["user"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welkom terug, {user['username']}! 👋", "success")
            return redirect("/")
        flash("Onjuiste inloggegevens.", "error")
    return render_template("login.html")

@main_routes.route("/logout")
def logout():
    name = session.get("user","")
    session.clear()
    flash(f"Tot ziens, {name}! 👋", "info")
    return redirect("/")

# ── INDEX ─────────────────────────────────────────────────

@main_routes.route("/")
def index():
    chairs = get_all_chairs()
    stats  = get_chair_stats()
    price, slot = get_price_and_slot()
    renter_map = {}
    for ch in chairs:
        if ch["status"] == "bezet":
            r = get_active_rental(ch["id"])
            if r: renter_map[ch["id"]] = r["rented_by"]
    return render_template("index.html",
        chairs=chairs, stats=stats,
        user=session.get("user"), role=session.get("role"),
        current_price=price, current_slot=slot,
        always_open=is_always_open(),
        renter_map=renter_map,
        broken_reasons=BROKEN_REASONS,
        now=datetime.now())

# ── CHECKOUT FLOW ─────────────────────────────────────────

@main_routes.route("/checkout/<int:id>")
def checkout(id):
    """Show the payment screen before confirming rental."""
    if not logged_in():
        flash("Je moet ingelogd zijn om een stoel te huren.", "error")
        return redirect("/login")
    chair = get_chair(id)
    if not chair or chair["status"] != "vrij":
        flash("Stoel niet beschikbaar.", "error")
        return redirect("/")
    price, slot = get_price_and_slot()
    if price is None:
        flash("Verhuur alleen mogelijk tussen 10:00 en 18:00.", "error")
        return redirect("/")
    # Ensure they are the right Python types before passing to template
    price = float(price)
    slot  = str(slot)
    return render_template("checkout.html",
        chair_id=id,
        price=price,
        slot=slot,
        user=session.get("user"),
        role=session.get("role"))

@main_routes.route("/confirm-rent/<int:id>", methods=["POST"])
def confirm_rent(id):
    """Process the checkout form and complete the rental."""
    if not logged_in():
        return redirect("/login")

    chair = get_chair(id)
    if not chair or chair["status"] != "vrij":
        flash("Stoel niet meer beschikbaar.", "error")
        return redirect("/")

    # Retrieve price/slot from hidden fields; always cast to correct types
    try:
        price = float(request.form.get("price_hidden") or 0)
        slot  = str(request.form.get("slot_hidden") or "").strip()
        # Sanity-check: only allow the two valid prices
        if price not in (10.0, 12.5):
            raise ValueError(f"Unexpected price: {price}")
        if not slot:
            raise ValueError("Empty slot")
    except Exception:
        # Hidden fields missing/corrupt — recalculate from current time
        price, slot = get_price_and_slot()
        if price is None:
            flash("Verhuur buiten openingstijden (voor 10:00 of na 18:00).", "error")
            return redirect("/")

    # Validate card fields (all fake, just check non-empty & length)
    card_name   = request.form.get("card_name",   "").strip()
    card_number = request.form.get("card_number",  "").strip().replace(" ", "")
    card_expiry = request.form.get("card_expiry",  "").strip()
    card_cvv    = request.form.get("card_cvv",     "").strip()

    errors = []
    if not card_name:                errors.append("Naam op kaart")
    if len(card_number) < 12:        errors.append("Kaartnummer (min. 12 cijfers)")
    if not card_expiry:              errors.append("Vervaldatum")
    if len(card_cvv) < 3:            errors.append("CVV (min. 3 cijfers)")

    if errors:
        flash("Vul de volgende velden correct in: " + ", ".join(errors), "error")
        return redirect(f"/checkout/{id}")

    # All good — commit the rental
    update_status(id, "bezet")
    add_rental(id, float(price), slot, session["user"])

    flash(f"Stoel {id} succesvol gehuurd voor €{float(price):.2f} ({slot}). Geniet van je dag! ☀️", "success")
    return redirect("/")

# ── CHAIR ACTIONS ─────────────────────────────────────────

@main_routes.route("/free/<int:id>")
def free_chair(id):
    if not logged_in(): return redirect("/login")
    chair = get_chair(id)
    if not chair or chair["status"] != "bezet":
        flash("Stoel is niet bezet.", "error"); return redirect("/")
    rental = get_active_rental(id)
    renter = rental["rented_by"] if rental else None
    if not is_admin() and session["user"] != renter:
        flash("Je kunt alleen je eigen stoel terugbrengen.", "error"); return redirect("/")
    update_status(id, "vrij")
    flash(f"Stoel {id} succesvol teruggebracht. 🪑", "success")
    return redirect("/")

@main_routes.route("/broken/<int:id>", methods=["POST"])
def broken_chair(id):
    if not logged_in(): return redirect("/login")
    chair = get_chair(id)
    if not chair:
        flash("Stoel niet gevonden.", "error"); return redirect("/")
    if chair["status"] in ("bezet",):
        flash("Stoel is bezet — eerst terugbrengen.", "error"); return redirect("/")
    if chair["status"] in ("kapot","in_reparatie"):
        flash("Stoel al gemarkeerd als kapot.", "error"); return redirect("/")
    reason_choice = request.form.get("reason_choice","").strip()
    custom_reason = request.form.get("custom_reason","").strip()
    reason = custom_reason if reason_choice == "anders" else reason_choice
    if not reason: reason = "Geen reden opgegeven"
    mark_broken(id, reason)
    flash(f"Stoel {id} als kapot gemeld: '{reason}'. 🔧", "info")
    return redirect("/")

@main_routes.route("/repair-status/<int:id>", methods=["POST"])
def repair_status(id):
    if not is_admin():
        return jsonify({"error": "Geen toegang"}), 403
    s = request.form.get("repair_status")
    if s not in ("kapot","in_reparatie","gerepareerd"):
        return jsonify({"error": "Ongeldige status"}), 400
    update_repair_status(id, s)
    labels = {"kapot":"Kapot","in_reparatie":"In reparatie","gerepareerd":"Gerepareerd ✅"}
    # Check if AJAX request
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        chair = get_chair(id)
        return jsonify({
            "ok": True,
            "label": labels[s],
            "repair_status": s,
            "chair_status": chair["status"] if chair else "vrij",
        })
    # Fallback: normal form post redirect
    flash(f"Stoel {id}: {labels[s]}", "success")
    return redirect("/beheer")

@main_routes.route("/free-all")
def free_all():
    if not is_admin(): flash("Geen toegang.", "error"); return redirect("/")
    free_all_chairs()
    flash("Alle bezette stoelen vrijgemaakt (einde dag). 🌅", "info")
    return redirect("/")

@main_routes.route("/toggle-always-open", methods=["POST"])
def toggle_always_open():
    if not is_admin(): return jsonify({"error":"Geen toegang"}), 403
    new = "false" if is_always_open() else "true"
    set_setting("always_open", new)
    return jsonify({"always_open": new == "true"})

# ── BEHEER ────────────────────────────────────────────────

@main_routes.route("/beheer")
def beheer():
    if not is_admin(): flash("Geen toegang.", "error"); return redirect("/")
    chairs = get_all_chairs()
    return render_template("beheer.html",
        revenue=get_revenue_breakdown(),
        recent=get_recent_rentals(25),
        stats=get_chair_stats(),
        day_data=get_rentals_per_day(7),
        week_data=get_rentals_per_week(8),
        always_open=is_always_open(),
        broken_chairs=[c for c in chairs if c["status"] in ("kapot","in_reparatie")],
        user=session.get("user"))

# ── API ───────────────────────────────────────────────────

@main_routes.route("/api/chairs")
def api_chairs():
    return jsonify([{"id":c["id"],"status":c["status"]} for c in get_all_chairs()])

@main_routes.route("/api/stats")
def api_stats():
    return jsonify(get_chair_stats())