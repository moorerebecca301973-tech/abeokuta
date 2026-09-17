# Abeokuta Smart Tourism Guide System — API

FastAPI + SQLAlchemy + SQLite backend for the Abeokuta Smart Tourism Guide
System React client. Runs in Docker locally and deploys to Render as a Docker
service.

---

## Quick start

```bash
cp .env.example .env          # optional for Docker; compose sets its own vars
docker compose up --build
```

Then open:

| URL | What it is |
| --- | --- |
| http://localhost:8000/docs | Interactive API documentation |
| http://localhost:8000/api/v1/health | Health check |
| http://localhost:8000/api/v1/attractions | All 14 landmarks |

The container creates the schema and seeds reference data on every start. Both
steps are idempotent, so restarting never duplicates rows and never overwrites
content you have edited.

### Demo account

Seeded from your `DEMO_USER` so the app has something to sign into:

```
email:    adeola@tourist.ng
password: abeokuta2026          # override with DEMO_USER_PASSWORD
```

`POST /api/v1/auth/demo` signs in as this account with no credentials, which is
what `quickDemoLogin()` in `TourismContext` becomes.

### Try it

```bash
# Sign in
curl -s -X POST localhost:8000/api/v1/auth/demo | python3 -m json.tool

# Search and sort, the way SearchPage does
curl -s "localhost:8000/api/v1/attractions?q=adire&sort=rating_desc"

# Nearby, ranked by real distance from the Olumo Rock gate
curl -s "localhost:8000/api/v1/attractions/nearby?lat=7.1552&lng=3.3482&radius_km=5"

# Price a visit without booking it
curl -s -X POST localhost:8000/api/v1/bookings/quote \
  -H 'Content-Type: application/json' \
  -d '{"attraction_id":"olumo-rock","adults_count":2,"children_count":1,
       "addon_ids":["historian-guide"]}'
```

---

## Running without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

The suite runs against an in-memory SQLite database with `StaticPool`, so it
never touches your development data. It covers the parts with real logic:
pricing fallbacks, booking validation and slot capacity, haversine distance,
badge unlocking, and that no response ever carries a password hash.

---

## Architecture

```
app/
├── main.py            app factory, CORS, logging, error handlers
├── core/              config, password hashing and JWT, dependencies, limiter
├── db/                engine + PRAGMAs, schema creation, idempotent seeder
├── models/            17 SQLAlchemy tables
├── schemas/           Pydantic request and response models
├── api/v1/endpoints/  one module per resource
├── services/          pricing, geo, booking rules, badge engine, serializers
└── seed_data/         JSON exported from the React app's TypeScript data
```

Logic that the client used to own now lives in `services/`, where it can be
unit-tested without HTTP:

- **`pricing.py`** — the only place a total is computed. `POST /bookings/quote`
  and `POST /bookings` call the same function, so the price shown and the price
  charged cannot drift.
- **`booking.py`** — date bounds, valid tour slots, group size, add-on
  existence, and seat capacity per slot. Also generates `ABK-2026-0001` from a
  per-year counter table rather than `Math.random()`, which would collide.
- **`geo.py`** — haversine rounded to one decimal to match the client's
  `calculateHaversineDistance`, plus a bounding-box prefilter so no SQL
  trigonometry is needed.
- **`badges.py`** — unlock rules stored as JSON in the `badges` table, so adding
  a badge is a seed-data edit rather than a code change.

### Why one worker

SQLite serialises writes on a single file lock. Multiple uvicorn workers against
one file produce `database is locked` under concurrent writes, so the Dockerfile
pins `--workers 1`. WAL mode (set per connection in `db/session.py`) keeps
readers from blocking the writer, which is what actually matters here.

### Why `def`, not `async def`

`aiosqlite` buys nothing when writes serialise anyway. Plain `def` handlers run
in FastAPI's threadpool, which keeps `Session` semantics simple and avoids
async/sync colour problems in the service layer.

---

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/abeokuta.db` | Four slashes for an absolute path: `sqlite:////data/abeokuta.db` |
| `SECRET_KEY` | dev placeholder | Must be a long random string in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh tokens are stored hashed and rotate on use |
| `CORS_ORIGINS` | localhost:3000, localhost:5173 | Comma separated, explicit origins only |
| `SEED_ON_STARTUP` | `true` | |
| `DEMO_USER_PASSWORD` | `abeokuta2026` | |
| `DEFAULT_SLOT_CAPACITY` | `40` | Seats per tour time |
| `DOCS_ENABLED` | `true` | Set false to hide `/docs` in production |

---

## Deploying to Render

**Render's free tier has an ephemeral filesystem.** Your SQLite file is
destroyed on every deploy, every restart, and every wake from the 15-minute idle
spin-down — registrations and bookings included. Persistent storage is a paid
feature. Three honest options:

1. **Persistent disk (recommended).** Starter instance (~$7/month) plus a 1 GB
   disk at `/var/data` or `/data`. `render.yaml` in this repo is already set up
   for it. Data survives deploys, and there is no cold start during a demo.
2. **Free tier, re-seed on boot.** Keep `SEED_ON_STARTUP=true` and accept that
   accounts and bookings reset. Fine for a code walkthrough.
3. **Render PostgreSQL.** Change `DATABASE_URL`, add `psycopg[binary]`, and the
   PRAGMA listener in `db/session.py` skips itself automatically because it
   checks the dialect. Everything else is unchanged.

Deploy with the blueprint:

```bash
git push                      # Render picks up render.yaml
```

Set `CORS_ORIGINS` to your deployed frontend origin before the first request
from the browser, or every call fails preflight.

---

## Connecting the React app

Point the client at the API and keep the `useTourism()` signature identical, so
no component file has to change:

```bash
# frontend .env
VITE_API_URL=http://localhost:8000/api/v1
```

| `TourismContext` today | Becomes |
| --- | --- |
| `attractions` static import | `GET /attractions?page_size=100` |
| `login(email)` | `POST /auth/login` (now takes a password and can fail) |
| `signup(...)` | `POST /auth/register` |
| `quickDemoLogin()` | `POST /auth/demo` |
| `updateUser(data)` | `PATCH /users/me` |
| `bookings` | `GET /bookings` |
| `createBooking(data)` | `POST /bookings` — drop `totalAmount` from the payload |
| `cancelBooking(id)` | `POST /bookings/{id}/cancel` |
| `toggleFavorite(id)` | `POST` / `DELETE /favorites/{id}` |
| `badges` | `GET /badges` |
| `getDistanceFromUser()` | **Keep client-side** — pure maths on data you hold, and it must stay instant while the map pans |

`POST /bookings` returns `newly_unlocked_badges` alongside the booking, so the
success modal can celebrate a badge in the same moment as the confetti.

---

## Schema changes later

Tables are created with `Base.metadata.create_all`, which adds new tables but
never alters existing ones. When you need to change a column without dropping
data, add Alembic:

```bash
pip install alembic
alembic init alembic
# point alembic/env.py at app.db.base:Base.metadata and settings.database_url
alembic revision --autogenerate -m "add column"
alembic upgrade head
```

Then replace `python -m app.db.init_db` in `entrypoint.sh` with
`alembic upgrade head && python -m app.db.seed`.
