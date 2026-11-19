"""Common Room Booking — a small Flask + SQLite app for apartment residents.

Run:  .venv/bin/python app.py   then open http://127.0.0.1:5050
"""

import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask, abort, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "booking.db")
SECRET_PATH = os.path.join(BASE_DIR, ".secret_key")

# Booking rules
MAX_HOURS_PER_BOOKING = 3
MAX_DAYS_AHEAD = 14
MAX_ACTIVE_BOOKINGS = 5  # upcoming bookings per resident


def load_secret_key():
    if not os.path.exists(SECRET_PATH):
        with open(SECRET_PATH, "w") as f:
            f.write(secrets.token_hex(32))
    with open(SECRET_PATH) as f:
        return f.read().strip()


app = Flask(__name__)
app.config["SECRET_KEY"] = load_secret_key()


# ---------------------------------------------------------------- database

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    unit          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    capacity    INTEGER NOT NULL DEFAULT 1,
    open_hour   INTEGER NOT NULL DEFAULT 8,
    close_hour  INTEGER NOT NULL DEFAULT 22,
    active      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS bookings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,          -- YYYY-MM-DD
    start_hour INTEGER NOT NULL,       -- 0..23
    end_hour   INTEGER NOT NULL,       -- 1..24, exclusive
    purpose    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bookings_room_day ON bookings(room_id, day);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
"""

SEED_ROOMS = [
    ("Study Room", "Quiet room with desks, whiteboard and Wi-Fi.", 6, 7, 23),
    ("Dance Studio", "Mirrored wall, sprung floor and a Bluetooth speaker.", 10, 8, 22),
    ("Function Room", "Tables, chairs and a pantry for gatherings.", 30, 9, 22),
    ("Music Room", "Upright piano and soundproofing.", 4, 9, 21),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO rooms (name, description, capacity, open_hour, close_hour)"
            " VALUES (?, ?, ?, ?, ?)",
            SEED_ROOMS,
        )
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        # Demo accounts for local testing (also listed in README.md).
        db.execute(
            "INSERT INTO users (name, unit, email, password_hash, is_admin) VALUES (?,?,?,?,1)",
            ("Building Admin", "Mgmt Office", "admin@building.local",
             generate_password_hash("admin123")),
        )
        db.execute(
            "INSERT INTO users (name, unit, email, password_hash) VALUES (?,?,?,?)",
            ("Demo Resident", "#05-12", "resident@building.local",
             generate_password_hash("resident123")),
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------- auth helpers

@app.before_request
def load_user():
    g.user = None
    uid = session.get("user_id")
    if uid is not None:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not g.user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# Minimal CSRF protection for all POST forms.
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("csrf_token")
        if not token or token != request.form.get("csrf_token"):
            abort(400, "Invalid or missing form token. Please reload the page and try again.")


@app.context_processor
def inject_globals():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return {"csrf_token": session["csrf_token"], "fmt_hour": fmt_hour, "today": date.today()}


def fmt_hour(h):
    h = int(h)
    if h in (0, 24):
        return "12 AM"
    if h == 12:
        return "12 PM"
    return f"{h % 12} {'AM' if h < 12 else 'PM'}"


# ---------------------------------------------------------------- auth routes

@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    form = {"name": "", "unit": "", "email": ""}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        error = None
        if not all(form.values()):
            error = "Please fill in every field."
        elif "@" not in form["email"]:
            error = "Please enter a valid email."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords don't match."
        else:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (name, unit, email, password_hash) VALUES (?,?,?,?)",
                    (form["name"], form["unit"], form["email"], generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "An account with that email already exists."
            else:
                session.clear()
                session["user_id"] = cur.lastrowid
                flash(f"Welcome, {form['name']}! Your account is ready.", "success")
                return redirect(url_for("index"))
        flash(error, "error")
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
        flash("Incorrect email or password.", "error")
    return render_template("login.html", email=email)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You've been logged out.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------- booking logic

def parse_day(value, default=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def validate_booking(db, room, day, start, end, user_id, exclude_id=None):
    """Return an error message, or None if the booking is allowed."""
    if room is None or not room["active"]:
        return "That room isn't available."
    if day is None:
        return "Please choose a valid date."
    today = date.today()
    if day < today:
        return "You can't book a date in the past."
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        return f"Bookings open up to {MAX_DAYS_AHEAD} days ahead."
    if start is None or end is None or end <= start:
        return "End time must be after start time."
    if start < room["open_hour"] or end > room["close_hour"]:
        return (f"{room['name']} is open {fmt_hour(room['open_hour'])}"
                f" – {fmt_hour(room['close_hour'])}.")
    if end - start > MAX_HOURS_PER_BOOKING:
        return f"A booking can be at most {MAX_HOURS_PER_BOOKING} hours."
    if day == today and start <= datetime.now().hour:
        return "That time slot has already started or passed."

    clash = db.execute(
        "SELECT 1 FROM bookings WHERE room_id = ? AND day = ? AND id != ?"
        " AND start_hour < ? AND end_hour > ?",
        (room["id"], day.isoformat(), exclude_id or -1, end, start),
    ).fetchone()
    if clash:
        return "Sorry, part of that time is already booked."

    if exclude_id is None:
        active = db.execute(
            "SELECT COUNT(*) FROM bookings WHERE user_id = ? AND day >= ?",
            (user_id, today.isoformat()),
        ).fetchone()[0]
        if active >= MAX_ACTIVE_BOOKINGS:
            return (f"You already have {MAX_ACTIVE_BOOKINGS} upcoming bookings. "
                    "Cancel one to make another.")
    return None


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- pages

@app.route("/")
@login_required
def index():
    """Availability grid: rooms x hours for a chosen day."""
    today = date.today()
    day = parse_day(request.args.get("day"), today)
    day = min(max(day, today), today + timedelta(days=MAX_DAYS_AHEAD))
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms WHERE active = 1 ORDER BY name").fetchall()
    rows = db.execute(
        "SELECT b.*, u.name AS user_name, u.unit AS user_unit FROM bookings b"
        " JOIN users u ON u.id = b.user_id WHERE b.day = ?",
        (day.isoformat(),),
    ).fetchall()

    # Build {room_id: {hour: booking}}
    taken = {}
    for b in rows:
        for h in range(b["start_hour"], b["end_hour"]):
            taken.setdefault(b["room_id"], {})[h] = b

    first = min((r["open_hour"] for r in rooms), default=8)
    last = max((r["close_hour"] for r in rooms), default=22)
    now_hour = datetime.now().hour if day == today else -1

    days = [today + timedelta(days=i) for i in range(MAX_DAYS_AHEAD + 1)]
    return render_template(
        "index.html", rooms=rooms, hours=range(first, last), taken=taken,
        day=day, days=days, now_hour=now_hour,
    )


@app.route("/book", methods=["GET", "POST"])
@login_required
def book():
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms WHERE active = 1 ORDER BY name").fetchall()
    src = request.form if request.method == "POST" else request.args
    form = {
        "room_id": to_int(src.get("room_id")),
        "day": src.get("day", date.today().isoformat()),
        "start_hour": to_int(src.get("start_hour")),
        "end_hour": to_int(src.get("end_hour")),
        "purpose": src.get("purpose", "").strip()[:200],
    }
    if form["start_hour"] is not None and form["end_hour"] is None:
        form["end_hour"] = form["start_hour"] + 1

    if request.method == "POST":
        room = db.execute("SELECT * FROM rooms WHERE id = ?", (form["room_id"],)).fetchone()
        day = parse_day(form["day"])
        error = validate_booking(db, room, day, form["start_hour"], form["end_hour"], g.user["id"])
        if error is None:
            db.execute(
                "INSERT INTO bookings (room_id, user_id, day, start_hour, end_hour, purpose)"
                " VALUES (?,?,?,?,?,?)",
                (room["id"], g.user["id"], day.isoformat(), form["start_hour"],
                 form["end_hour"], form["purpose"]),
            )
            db.commit()
            flash(f"Booked {room['name']} on {day:%a %d %b}, "
                  f"{fmt_hour(form['start_hour'])} – {fmt_hour(form['end_hour'])}.", "success")
            return redirect(url_for("index", day=day.isoformat()))
        flash(error, "error")

    return render_template("booking_form.html", rooms=rooms, form=form, booking=None,
                           max_hours=MAX_HOURS_PER_BOOKING, max_days=MAX_DAYS_AHEAD)


def get_own_booking(booking_id):
    b = get_db().execute(
        "SELECT b.*, r.name AS room_name FROM bookings b JOIN rooms r ON r.id = b.room_id"
        " WHERE b.id = ?", (booking_id,),
    ).fetchone()
    if b is None:
        abort(404)
    if b["user_id"] != g.user["id"] and not g.user["is_admin"]:
        abort(403)
    return b


@app.route("/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
@login_required
def edit_booking(booking_id):
    db = get_db()
    b = get_own_booking(booking_id)
    if b["day"] < date.today().isoformat():
        flash("Past bookings can't be changed.", "error")
        return redirect(url_for("my_bookings"))
    rooms = db.execute("SELECT * FROM rooms WHERE active = 1 ORDER BY name").fetchall()
    form = {k: b[k] for k in ("room_id", "day", "start_hour", "end_hour", "purpose")}

    if request.method == "POST":
        form = {
            "room_id": to_int(request.form.get("room_id")),
            "day": request.form.get("day", ""),
            "start_hour": to_int(request.form.get("start_hour")),
            "end_hour": to_int(request.form.get("end_hour")),
            "purpose": request.form.get("purpose", "").strip()[:200],
        }
        room = db.execute("SELECT * FROM rooms WHERE id = ?", (form["room_id"],)).fetchone()
        day = parse_day(form["day"])
        error = validate_booking(db, room, day, form["start_hour"], form["end_hour"],
                                 b["user_id"], exclude_id=b["id"])
        if error is None:
            db.execute(
                "UPDATE bookings SET room_id=?, day=?, start_hour=?, end_hour=?, purpose=?"
                " WHERE id=?",
                (room["id"], day.isoformat(), form["start_hour"], form["end_hour"],
                 form["purpose"], b["id"]),
            )
            db.commit()
            flash("Booking updated.", "success")
            return redirect(url_for("my_bookings"))
        flash(error, "error")

    return render_template("booking_form.html", rooms=rooms, form=form, booking=b,
                           max_hours=MAX_HOURS_PER_BOOKING, max_days=MAX_DAYS_AHEAD)


@app.route("/bookings/<int:booking_id>/delete", methods=["POST"])
@login_required
def delete_booking(booking_id):
    b = get_own_booking(booking_id)
    db = get_db()
    db.execute("DELETE FROM bookings WHERE id = ?", (b["id"],))
    db.commit()
    flash(f"Cancelled your {b['room_name']} booking on {b['day']}.", "success")
    back = request.form.get("back", "")
    return redirect(back if back.startswith("/") and not back.startswith("//") else url_for("my_bookings"))


@app.route("/my-bookings")
@login_required
def my_bookings():
    db = get_db()
    today = date.today().isoformat()
    q = ("SELECT b.*, r.name AS room_name FROM bookings b JOIN rooms r ON r.id = b.room_id"
         " WHERE b.user_id = ? AND b.day {} ? ORDER BY b.day {}, b.start_hour {}")
    upcoming = db.execute(q.format(">=", "ASC", "ASC"), (g.user["id"], today)).fetchall()
    past = db.execute(q.format("<", "DESC", "DESC") + " LIMIT 20", (g.user["id"], today)).fetchall()
    return render_template("my_bookings.html", upcoming=upcoming, past=past,
                           max_active=MAX_ACTIVE_BOOKINGS)


# ---------------------------------------------------------------- admin

@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms ORDER BY active DESC, name").fetchall()
    bookings = db.execute(
        "SELECT b.*, r.name AS room_name, u.name AS user_name, u.unit AS user_unit"
        " FROM bookings b JOIN rooms r ON r.id = b.room_id JOIN users u ON u.id = b.user_id"
        " WHERE b.day >= ? ORDER BY b.day, b.start_hour",
        (date.today().isoformat(),),
    ).fetchall()
    users = db.execute(
        "SELECT u.*, (SELECT COUNT(*) FROM bookings WHERE user_id = u.id) AS n"
        " FROM users u ORDER BY u.name"
    ).fetchall()
    return render_template("admin.html", rooms=rooms, bookings=bookings, users=users)


def room_form_values():
    f = request.form
    vals = {
        "name": f.get("name", "").strip(),
        "description": f.get("description", "").strip(),
        "capacity": to_int(f.get("capacity")),
        "open_hour": to_int(f.get("open_hour")),
        "close_hour": to_int(f.get("close_hour")),
        "active": 1 if f.get("active") else 0,
    }
    error = None
    if not vals["name"]:
        error = "Room name is required."
    elif not vals["capacity"] or vals["capacity"] < 1:
        error = "Capacity must be at least 1."
    elif (vals["open_hour"] is None or vals["close_hour"] is None
          or not 0 <= vals["open_hour"] < vals["close_hour"] <= 24):
        error = "Opening hours must be between 0 and 24, with closing after opening."
    return vals, error


@app.route("/admin/rooms/new", methods=["GET", "POST"])
@admin_required
def new_room():
    room = {"name": "", "description": "", "capacity": 4, "open_hour": 8,
            "close_hour": 22, "active": 1}
    if request.method == "POST":
        room, error = room_form_values()
        if error is None:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO rooms (name, description, capacity, open_hour, close_hour, active)"
                    " VALUES (:name, :description, :capacity, :open_hour, :close_hour, :active)",
                    room,
                )
                db.commit()
                flash(f"Added {room['name']}.", "success")
                return redirect(url_for("admin"))
            except sqlite3.IntegrityError:
                error = "A room with that name already exists."
        flash(error, "error")
    return render_template("room_form.html", room=room, editing=False)


@app.route("/admin/rooms/<int:room_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_room(room_id):
    db = get_db()
    existing = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if existing is None:
        abort(404)
    room = dict(existing)
    if request.method == "POST":
        room, error = room_form_values()
        if error is None:
            try:
                db.execute(
                    "UPDATE rooms SET name=:name, description=:description, capacity=:capacity,"
                    " open_hour=:open_hour, close_hour=:close_hour, active=:active WHERE id=:id",
                    {**room, "id": room_id},
                )
                db.commit()
                flash(f"Saved {room['name']}.", "success")
                return redirect(url_for("admin"))
            except sqlite3.IntegrityError:
                error = "A room with that name already exists."
        flash(error, "error")
    room["id"] = room_id
    return render_template("room_form.html", room=room, editing=True)


@app.route("/admin/rooms/<int:room_id>/delete", methods=["POST"])
@admin_required
def delete_room(room_id):
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if room is None:
        abort(404)
    db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    db.commit()
    flash(f"Deleted {room['name']} and its bookings.", "success")
    return redirect(url_for("admin"))


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, message="You don't have access to that page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="We couldn't find that page."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message=e.description), 400


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
