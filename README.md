# APL Competition Manager 🎱

**v4 development release**, for a local pool league of ~500 members. A FastAPI + PostgreSQL + React/TypeScript implementation inspired by the architecture of the [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template). **This is a standalone application, not an upstream template fork.**

## Features included

- Public pages for published and completed knockout competition brackets and frame scores, with no sign-in required.
- Committee login, multiple committee users, request-level CSRF checking and audit log.
- Four divisions and registered pub teams, with players assigned to a division and team.
- CSV import of players from LibreOffice Calc / Excel (save as UTF-8 CSV). Existing member IDs can be updated on reimport.
- Straight knockout: Singles, Doubles, Threes and Teams with automatic byes and random draws.
- Separate **Enforce same division** switch for Doubles and Threes (default ON), changeable before drawing. Players may be from different registered teams.
- Create entries, preview and regenerate a random draw, publish the draw, record frame scores and advance winners automatically.
- Prevents changing an earlier winner if a subsequent-round result already exists.

## Run on CachyOS using Docker Compose

Requires Docker Engine + Compose plugin, already running with permission for your user.

```bash
cp .env.example .env
openssl rand -hex 32   # use output for POSTGRES_PASSWORD
openssl rand -hex 32   # use DIFFERENT output for JWT_SECRET
nano .env              # fill both generated values, and ADMIN_EMAIL / ADMIN_PASSWORD

docker compose up --build -d
docker compose logs -f web
```

Open **http://127.0.0.1:8000**. Committee login: **http://127.0.0.1:8000/#/admin**.

The initial administrator is created only on first startup. `ADMIN_PASSWORD` must be at least 12 characters, and `JWT_SECRET` at least 32 characters. These variables do not reset an existing administrator.

To stop: `docker compose down`. The Postgres data persists in the named volume. **Never run `docker compose down -v` against important data.**

### Alternative: run without Docker (development)

You can use Python 3.12+ and Node 22+. SQLite is supported for local development by default, while Docker uses PostgreSQL.

**Backend (Fish shell on CachyOS)**

```fish
cd backend
python -m venv .venv
source .venv/bin/activate.fish
python -m pip install -r requirements.txt
set -x JWT_SECRET (python -c 'import secrets; print(secrets.token_hex(32))')
set -x ADMIN_EMAIL 'admin@example.org'
set -x ADMIN_PASSWORD 'choose-a-long-unique-password'
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend (second terminal)**

```fish
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. In development, Vite proxies `/api` to port 8000. Do not use the example email/password above for public hosting.

### Testing

```bash
cd backend && python -m pytest -q
cd ../frontend && npm install && npm run build
```

### CSV data

Provide headers `Name,Division,Team,Member ID`. First two required, other two optional. Values for Division can be `1`, `2`, `3`, `4`, or `Division 1` etc. Example: [`examples/example-members.csv`](examples/example-members.csv). Import from **Committee → Players & teams**. Max 2 MB / 2000 rows per upload. The importer upserts by Member ID; without one it skips exact name+division+team duplicates but cannot safely identify transfers. **Real member details should never be committed to GitHub.**

### Publish to an existing GitHub repository

For an existing repository `APL-comp`, run from the extracted project folder:

```bash
bash scripts/publish-to-github.sh https://github.com/YOUR-GITHUB-USERNAME/APL-comp.git
```

The script clones the remote, copies source (excluding local credentials, databases, CSVs except example data), commits, and pushes to the current branch. It never force-pushes or deletes the existing remote repository history. Your local Git must be authenticated to GitHub (SSH or HTTPS) and configured with `user.name` and `user.email`. If the repo is private, keep it that way while testing.

## Repository layout

```text
APL-comp/
├── backend/app/          # FastAPI endpoints, models, security, knockout engine
├── backend/tests/        # Automated Python tests
├── frontend/src/         # React public website and committee dashboard
├── examples/             # Dummy sample roster
├── .github/workflows/ci.yml
├── Dockerfile
├── compose.yml
├── .env.example
└── scripts/publish-to-github.sh
```

## Known development-release limitations

This is an **alpha build**, not a production-hardened public service. It uses a schema bootstrap (`create_all`) rather than Alembic migrations. Before internet deployment, add versioned migrations, DB backups/restores, TLS reverse proxy, `COOKIE_SECURE=true`, persistent multi-instance login rate limiting, admin password reset and account management, and privacy/retention policies. V3 SQLite data is **not automatically migrated**. It requires a separate data migration and verification. Entries are limited to 512 per knockout. Printable brackets, editing transferred players in the UI and full team rosters are future work.

**Licensing:** No open-source license has been granted or selected for this application. Choose a licence before publicly distributing or encouraging outside contributions.
