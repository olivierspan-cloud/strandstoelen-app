import io, csv
from flask import (Blueprint, render_template, redirect, request,
                   session, flash, jsonify, Response)
from models import *
from datetime import datetime, date, timedelta

main_routes = Blueprint("main", __name__)

# ── Constants ──────────────────────────────────────────────
BROKEN_REASONS = [
    "Poot gebroken of los", "Stof gescheurd of beschadigd",
    "Frame verbogen", "Schroef of bout ontbreekt",
    "Klapstoel werkt niet", "Roestschade", "anders",
]

AVATARS = {
    "wave":"🌊","sun":"☀️","umbrella":"⛱️","surf":"🏄","shell":"🐚",
    "starfish":"⭐","crab":"🦀","fish":"🐠","dolphin":"🐬","coconut":"🥥",
    "anchor":"⚓","sailboat":"⛵","flamingo":"🦩","ice_cream":"🍦",
    "sunglasses":"😎","palm":"🌴","volleyball":"🏐","sandcastle":"🏖️",
}

TIME_SLOTS = [
    ("10:00–15:00", 12.50),
    ("15:00–18:00", 10.00),
]

# ── Helpers ────────────────────────────────────────────────
def logged_in(): return "user" in session
def is_admin():  return session.get("role") == "admin"

def get_price_and_slot():
    if is_always_open():
        h = datetime.now().hour
        return (10.0, "15:00–18:00") if h >= 15 else (12.5, "10:00–18:00")
    h = datetime.now().hour
    if h < 10 or h >= 18: return None, None
    return (10.0, "15:00–18:00") if h >= 15 else (12.5, "10:00–18:00")

def _notif_count():
    if not logged_in(): return 0
    try:
        return count_unread_notifications(session["user"])
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════

@main_routes.route("/register", methods=["GET","POST"])
def register():
    if logged_in(): return redirect("/")
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        c = request.form.get("confirm","")
        if len(u) < 3:           flash("Gebruikersnaam minimaal 3 tekens.", "error")
        elif len(p) < 4:         flash("Wachtwoord minimaal 4 tekens.", "error")
        elif p != c:             flash("Wachtwoorden komen niet overeen.", "error")
        elif username_exists(u): flash("Gebruikersnaam al in gebruik.", "error")
        else:
            create_user(u, p, "klant")
            user = get_user(u)
            session["user"]         = user["username"]
            session["role"]         = user["role"]
            session["avatar_emoji"] = "🌊"
            session["onboarding"]   = True   # trigger onboarding tour
            add_notification(u, "Welkom bij ZonneStrand! 🏖️ Klik op een vrije stoel om je eerste reservering te maken.", "info")
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
            session["user"]         = user["username"]
            session["role"]         = user["role"]
            session["avatar_emoji"] = AVATARS.get(get_avatar(user["username"]), "🌊")
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


# ══════════════════════════════════════════════════════════
# PROFIEL + AVATAR + WACHTWOORD (feature 5)
# ══════════════════════════════════════════════════════════

@main_routes.route("/profiel")
def profiel():
    if not logged_in():
        flash("Je moet ingelogd zijn.", "error"); return redirect("/login")
    username   = session["user"]
    stats      = get_user_stats(username)
    rentals    = get_user_rentals(username, limit=15)
    avatar     = get_avatar(username)
    reserv     = get_user_reservations(username, upcoming_only=True)
    notifs     = get_user_notifications(username)
    mark_notifications_read(username)
    return render_template("profiel.html",
        user=username, role=session.get("role"),
        stats=stats, rentals=rentals, avatar=avatar,
        avatars=AVATARS, reservations=reserv, notifications=notifs,
        notif_count=0)


@main_routes.route("/profiel/avatar", methods=["POST"])
def save_avatar():
    if not logged_in(): return jsonify({"error":"Niet ingelogd"}), 401
    choice = request.form.get("avatar","wave")
    if choice not in AVATARS: return jsonify({"error":"Ongeldig"}), 400
    update_avatar(session["user"], choice)
    emoji = AVATARS[choice]
    session["avatar_emoji"] = emoji
    return jsonify({"ok":True,"emoji":emoji,"key":choice})


@main_routes.route("/profiel/wachtwoord", methods=["POST"])
def change_password_route():
    if not logged_in(): return redirect("/login")
    huidig = request.form.get("current_password","")
    nieuw  = request.form.get("new_password","").strip()
    bevestig = request.form.get("confirm_password","").strip()
    user = get_user(session["user"])
    if not check_user_password(user, huidig):
        flash("Huidig wachtwoord klopt niet.", "error")
    elif len(nieuw) < 4:
        flash("Nieuw wachtwoord minimaal 4 tekens.", "error")
    elif nieuw != bevestig:
        flash("Wachtwoorden komen niet overeen.", "error")
    else:
        change_password(session["user"], nieuw)
        flash("Wachtwoord succesvol gewijzigd. 🔒", "success")
    return redirect("/profiel")


# ══════════════════════════════════════════════════════════
# INDEX
# ══════════════════════════════════════════════════════════

@main_routes.route("/")
def index():
    chairs       = get_all_chairs()
    stats        = get_chair_stats()
    price, slot  = get_price_and_slot()
    renter_map   = {}
    for ch in chairs:
        if ch["status"] == "bezet":
            r = get_active_rental(ch["id"])
            if r: renter_map[ch["id"]] = r["rented_by"]

    # Search: filter by chair number
    search = request.args.get("q","").strip()

    show_onboarding = session.pop("onboarding", False)
    notif_count     = _notif_count()

    return render_template("index.html",
        chairs=chairs, stats=stats,
        user=session.get("user"), role=session.get("role"),
        current_price=price, current_slot=slot,
        always_open=is_always_open(),
        renter_map=renter_map,
        broken_reasons=BROKEN_REASONS,
        now=datetime.now(),
        search=search,
        show_onboarding=show_onboarding,
        notif_count=notif_count,
        time_slots=TIME_SLOTS)


# ══════════════════════════════════════════════════════════
# RESERVATIONS (feature 1)
# ══════════════════════════════════════════════════════════

@main_routes.route("/reserveer", methods=["GET","POST"])
def reserveer():
    if not logged_in():
        flash("Je moet ingelogd zijn.", "error"); return redirect("/login")

    chairs = get_all_chairs()
    today  = date.today().isoformat()

    # Build next 14 days
    days = [(date.today() + timedelta(days=i)).isoformat() for i in range(0, 14)]

    if request.method == "POST":
        chair_id  = int(request.form.get("chair_id", 0))
        res_date  = request.form.get("res_date","")
        slot_key  = request.form.get("time_slot","")

        # Validate
        if not chair_id or not res_date or not slot_key:
            flash("Vul alle velden in.", "error")
            return redirect("/reserveer")

        price = dict(TIME_SLOTS).get(slot_key)
        if price is None:
            flash("Ongeldig tijdslot.", "error"); return redirect("/reserveer")

        if res_date < today:
            flash("Je kunt niet reserveren in het verleden.", "error"); return redirect("/reserveer")

        if chair_reserved_on(chair_id, res_date, slot_key):
            flash(f"Stoel {chair_id} is al gereserveerd op {res_date} ({slot_key}).", "error")
            return redirect("/reserveer")

        add_reservation(chair_id, res_date, slot_key, price, session["user"])
        add_notification(session["user"],
            f"Reservering bevestigd: stoel {chair_id} op {res_date} ({slot_key}) voor €{price:.2f}.",
            "success")
        flash(f"Stoel {chair_id} gereserveerd voor {res_date} ({slot_key}) — €{price:.2f}! 🎉", "success")
        return redirect("/profiel")

    return render_template("reserveer.html",
        chairs=chairs, days=days, time_slots=TIME_SLOTS,
        user=session.get("user"), role=session.get("role"),
        notif_count=_notif_count())


@main_routes.route("/reserveer/annuleer/<int:res_id>", methods=["POST"])
def annuleer_reservering(res_id):
    if not logged_in(): return redirect("/login")
    cancel_reservation(res_id, session["user"], is_admin=is_admin())
    flash("Reservering geannuleerd.", "info")
    return redirect("/profiel")


# ══════════════════════════════════════════════════════════
# CHECKOUT (today's rental)
# ══════════════════════════════════════════════════════════

@main_routes.route("/checkout/<int:id>")
def checkout(id):
    if not logged_in():
        flash("Je moet ingelogd zijn.", "error"); return redirect("/login")
    chair = get_chair(id)
    if not chair or chair["status"] != "vrij":
        flash("Stoel niet beschikbaar.", "error"); return redirect("/")
    price, slot = get_price_and_slot()
    if price is None:
        flash("Verhuur alleen mogelijk tussen 10:00 en 18:00.", "error"); return redirect("/")
    return render_template("checkout.html",
        chair_id=id, price=float(price), slot=str(slot),
        user=session.get("user"), role=session.get("role"),
        notif_count=_notif_count())


@main_routes.route("/confirm-rent/<int:id>", methods=["POST"])
def confirm_rent(id):
    if not logged_in(): return redirect("/login")
    chair = get_chair(id)
    if not chair or chair["status"] != "vrij":
        flash("Stoel niet meer beschikbaar.", "error"); return redirect("/")
    try:
        price = float(request.form.get("price_hidden") or 0)
        slot  = str(request.form.get("slot_hidden") or "").strip()
        if price not in (10.0, 12.5) or not slot: raise ValueError
    except Exception:
        price, slot = get_price_and_slot()
        if price is None:
            flash("Verhuur buiten openingstijden.", "error"); return redirect("/")

    card_name   = request.form.get("card_name","").strip()
    card_number = request.form.get("card_number","").strip().replace(" ","")
    card_expiry = request.form.get("card_expiry","").strip()
    card_cvv    = request.form.get("card_cvv","").strip()
    errors = []
    if not card_name:          errors.append("Naam op kaart")
    if len(card_number) < 12:  errors.append("Kaartnummer")
    if not card_expiry:        errors.append("Vervaldatum")
    if len(card_cvv) < 3:      errors.append("CVV")
    if errors:
        flash("Vul correct in: " + ", ".join(errors), "error")
        return redirect(f"/checkout/{id}")

    update_status(id, "bezet")
    add_rental(id, float(price), slot, session["user"])
    add_notification(session["user"],
        f"Stoel {id} verhuurd voor €{float(price):.2f} ({slot}). Geniet! ☀️", "success")
    flash(f"Stoel {id} verhuurd voor €{float(price):.2f} ({slot}). Geniet van je dag! ☀️", "success")
    return redirect("/")


# ══════════════════════════════════════════════════════════
# CHAIR ACTIONS
# ══════════════════════════════════════════════════════════

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
    add_notification(session["user"], f"Stoel {id} succesvol teruggebracht. 🪑", "info")
    flash(f"Stoel {id} teruggebracht. 🪑", "success")
    return redirect("/")


@main_routes.route("/broken/<int:id>", methods=["POST"])
def broken_chair(id):
    if not logged_in(): return redirect("/login")
    chair = get_chair(id)
    if not chair:
        flash("Stoel niet gevonden.", "error"); return redirect("/")
    if chair["status"] == "bezet":
        flash("Stoel bezet — eerst terugbrengen.", "error"); return redirect("/")
    if chair["status"] in ("kapot","in_reparatie"):
        flash("Al als kapot gemarkeerd.", "error"); return redirect("/")
    rc = request.form.get("reason_choice","").strip()
    cr = request.form.get("custom_reason","").strip()
    reason = cr if rc == "anders" else rc
    if not reason: reason = "Geen reden opgegeven"
    mark_broken(id, reason)
    flash(f"Stoel {id} als kapot gemeld: '{reason}'. 🔧", "info")
    return redirect("/")


@main_routes.route("/repair-status/<int:id>", methods=["POST"])
def repair_status(id):
    if not is_admin():
        return jsonify({"error":"Geen toegang"}), 403
    s = request.form.get("repair_status")
    if s not in ("kapot","in_reparatie","gerepareerd"):
        return jsonify({"error":"Ongeldige status"}), 400
    update_repair_status(id, s)
    labels = {"kapot":"Kapot","in_reparatie":"In reparatie","gerepareerd":"Gerepareerd ✅"}
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        chair = get_chair(id)
        return jsonify({"ok":True,"label":labels[s],"repair_status":s,
                        "chair_status": chair["status"] if chair else "vrij"})
    flash(f"Stoel {id}: {labels[s]}", "success")
    return redirect("/beheer")


@main_routes.route("/free-all")
def free_all():
    if not is_admin(): flash("Geen toegang.", "error"); return redirect("/")
    free_all_chairs()
    flash("Alle bezette stoelen vrijgemaakt. 🌅", "info")
    return redirect("/")


@main_routes.route("/toggle-always-open", methods=["POST"])
def toggle_always_open():
    if not is_admin(): return jsonify({"error":"Geen toegang"}), 403
    new = "false" if is_always_open() else "true"
    set_setting("always_open", new)
    return jsonify({"always_open": new == "true"})


# ══════════════════════════════════════════════════════════
# BEHEER DASHBOARD
# ══════════════════════════════════════════════════════════

@main_routes.route("/beheer")
def beheer():
    if not is_admin(): flash("Geen toegang.", "error"); return redirect("/")
    try:
        chairs = get_all_chairs()
        return render_template("beheer.html",
            revenue=get_revenue_breakdown(),
            recent=get_recent_rentals(25),
            stats=get_chair_stats(),
            day_data=get_rentals_per_day(7),
            week_data=get_rentals_per_week(8),
            always_open=is_always_open(),
            broken_chairs=[c for c in chairs if c["status"] in ("kapot","in_reparatie")],
            all_reservations=get_all_reservations(30),
            week_reservations=get_week_reservations(),
            heatmap=get_hourly_heatmap(),
            user=session.get("user"),
            notif_count=_notif_count())
    except Exception as e:
        flash(f"Dashboard fout: {str(e)}", "error")
        return redirect("/")


# ══════════════════════════════════════════════════════════
# CSV EXPORT (feature 3)
# ══════════════════════════════════════════════════════════

@main_routes.route("/beheer/export-csv")
def export_csv():
    if not is_admin(): flash("Geen toegang.", "error"); return redirect("/")
    rows = get_revenue_csv()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id","chair_id","rented_by","time_slot","price","date"])
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    today = date.today().isoformat()
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=verhuren_{today}.csv"}
    )


# ══════════════════════════════════════════════════════════
# NOTIFICATIONS API (feature 9)
# ══════════════════════════════════════════════════════════

@main_routes.route("/api/notifications")
def api_notifications():
    if not logged_in(): return jsonify([])
    notifs = get_user_notifications(session["user"])
    mark_notifications_read(session["user"])
    return jsonify([{
        "id":      n["id"],
        "message": n["message"],
        "type":    n["type"],
        "time":    n["created_at"][:16],
        "read":    bool(n["is_read"]),
    } for n in notifs])


@main_routes.route("/api/notif-count")
def api_notif_count():
    if not logged_in(): return jsonify({"count": 0})
    return jsonify({"count": count_unread_notifications(session["user"])})


# ══════════════════════════════════════════════════════════
# JSON API
# ══════════════════════════════════════════════════════════

@main_routes.route("/api/chairs")
def api_chairs():
    return jsonify([{"id":c["id"],"status":c["status"]} for c in get_all_chairs()])

@main_routes.route("/api/stats")
def api_stats():
    return jsonify(get_chair_stats())

@main_routes.route("/api/heatmap")
def api_heatmap():
    if not is_admin(): return jsonify([])
    return jsonify(get_hourly_heatmap())