# Common Rooms — apartment room booking

A small web app for residents to book the building's common rooms (study room, dance studio, function room, music room). Runs only on your own machine.

**Stack:** Python + Flask, SQLite database (a single file, `booking.db`, created automatically), server-rendered HTML.

## Run it

First time only:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Every time:

```bash
.venv/bin/python app.py
```

Then open http://127.0.0.1:5050. Stop the server with `Ctrl+C`.

## Demo accounts

Created automatically the first time the database is set up:

| Role | Email | Password |
|---|---|---|
| Admin | admin@building.local | admin123 |
| Resident | resident@building.local | resident123 |

Residents can also create their own account from the login page.

## What it does

- **Login / register** — passwords stored as salted hashes; sessions via signed cookies.
- **Availability grid** — rooms × hours for any day in the next 14 days. Click a free slot to book it.
- **Bookings (CRUD)** — create, view (My bookings), edit, and cancel your own bookings.
- **Admin** — add, edit, hide or delete rooms; see and cancel anyone's upcoming booking; list residents.

### Booking rules (change them at the top of `app.py`)

- Max 3 hours per booking
- Book up to 14 days ahead, never in the past
- Max 5 upcoming bookings per resident
- Must fall within the room's opening hours, and can't overlap another booking

## Files

```
app.py              routes, database schema, booking rules
templates/          HTML pages (Jinja)
static/style.css    styling (follows light/dark mode)
booking.db          the database (created on first run; delete it to reset)
```

## Reset everything

Stop the server, delete `booking.db`, start it again. Rooms and demo accounts are recreated.
