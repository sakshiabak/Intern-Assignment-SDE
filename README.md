# Aereo Survey API

A backend for managing **drone survey projects** and their **GeoJSON footprints**, modelled on the kind of work Aereo Cloud does (mining, infrastructure, energy, utilities).

Built with **FastAPI + SQLAlchemy 2.0 + JWT auth**. Runs on SQLite out of the box and on PostgreSQL via Docker Compose.

## Features

- **Auth**: register / login (OAuth2 password flow) / `me`. Passwords hashed with PBKDF2-SHA256 (per-user salt), JWT access tokens.
- **Projects**: full CRUD, scoped to the owner. Other users get `404`, so project IDs don't leak.
- **Surveys** (one drone flight over an area): full CRUD under `/projects/{id}/surveys`.
  - Validates GeoJSON Polygons (closed ring, valid lon/lat ranges).
  - Computes area in km² on the server.
  - Filters: `status`, spatial `bbox` intersection, `limit`/`offset` pagination.
  - `/surveys/geojson` returns a `FeatureCollection` ready for Leaflet or Mapbox.
- **Stats**: `/projects/{id}/stats` aggregates survey count, area, images and status breakdown in SQL.
- **Tests**: 13 pytest tests (auth, isolation between users, validation, GIS, pagination).
- **Docker**: `Dockerfile` + `docker-compose.yml` (API + Postgres).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for interactive Swagger UI (use the *Authorize* button after logging in).

### With Docker (Postgres)

```bash
docker compose up --build
```

### Run tests

```bash
pytest -q
```

## Example flow

```bash
# 1. register + login
curl -X POST localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"password123"}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -d 'username=me@example.com&password=password123' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2. create a project
curl -X POST localhost:8000/projects -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"name":"Open Pit A","industry":"mining"}'

# 3. add a survey footprint
curl -X POST localhost:8000/projects/1/surveys -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{
    "name":"Flight 1","image_count":120,
    "area":{"type":"Polygon","coordinates":[[[77.59,12.97],[77.599,12.97],[77.599,12.979],[77.59,12.979],[77.59,12.97]]]}
  }'

# 4. query by bounding box
curl "localhost:8000/projects/1/surveys?bbox=77.5,12.9,77.7,13.0" -H "Authorization: Bearer $TOKEN"
```

## Project layout

```
app/
  main.py        app + router wiring
  config.py      env-based settings
  database.py    engine / session
  models.py      User, Project, Survey
  schemas.py     Pydantic request/response models
  security.py    password hashing + JWT
  deps.py        auth + ownership dependencies
  geo.py         polygon validation, bbox, area
  routers/       auth, projects, surveys
tests/           pytest suite (in-memory SQLite)
```

## Design decisions

- **Ownership as a dependency** (`get_owned_project`): every project/survey route reuses one check, so no endpoint can forget it.
- **Bounding box stored per survey**: spatial filtering is a plain indexed SQL query. In production on Postgres I'd move to PostGIS (`geometry(Polygon, 4326)` + GiST index) and `ST_Intersects`.
- **Area computed server-side** with a spherical approximation, accurate for survey-sized polygons.
- **No external hashing deps**: stdlib PBKDF2; `bcrypt`/`argon2` would be the next step.

## Possible next steps

Alembic migrations, refresh tokens, file upload for orthomosaics to S3, Redis caching for stats, background processing with a task queue, React + Leaflet frontend.
