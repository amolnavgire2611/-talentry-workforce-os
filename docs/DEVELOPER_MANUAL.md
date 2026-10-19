# NEXORA Workforce OS — Developer Manual

Step-by-step guide for setting up, running, testing, and extending the NEXORA
Workforce OS locally.

## 1. Prerequisites

| Component | Version |
|-----------|---------|
| Python | 3.12+ |
| Node.js | 20.19+ or 22.12+ (required by the installed Vite) |
| npm | bundled with Node |

Verify:
```sh
python3 --version
node --version
npm --version
```

## 2. Project layout

```
login-app/
├── backend/              # FastAPI + SQLAlchemy + Alembic API
│   ├── main.py           # app entry point
│   ├── application.py    # app factory, routes, services
│   ├── models.py         # SQLAlchemy models
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── config.py         # pydantic-settings configuration
│   ├── security.py       # password hashing, JWT, CSRF, refresh sessions
│   ├── bootstrap_admin.py# first Super Admin bootstrap utility
│   ├── alembic.ini       # Alembic config
│   ├── migrations/       # database migrations
│   ├── requirements.txt  # Python dependencies
│   ├── .env / .env.example
│   ├── users.db          # SQLite dev database
│   └── tests/            # backend pytest suite
├── frontend/             # React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── WorkforceApp.tsx      # app shell, sidebar, module routing
│   │   ├── main.tsx
│   │   ├── index.css / WorkforceApp.css
│   │   ├── lib/api.ts            # bearer-auth API client with refresh
│   │   ├── features/auth/        # AuthScreen, SessionManager
## 3. Backend setup (step by step)

```sh
# 1. Enter the backend folder
cd backend

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
#    Linux/macOS:
source .venv/bin/activate
#    Windows:
#    .venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy the environment template and set a secret key
cp .env.example .env
# Edit backend/.env and set NEXORA_SECRET_KEY to a private random value (32+ chars).
# Also set CORS_ORIGINS to match the frontend origin (default http://127.0.0.1:8000 / :5173).

# 6. Apply database migrations (additive; preserves legacy data)
alembic upgrade head

# 7. Run the API
uvicorn main:app --reload

# The API is available at http://127.0.0.1:8000
# Interactive docs: http://127.0.0.1:8000/docs
# Health probe: http://127.0.0.1:8000/health
```

### First Super Admin

The UI does not allow public self-registration for privileged roles. To create the first
Super Admin:

1. Set a private random `ADMIN_BOOTSTRAP_TOKEN` (32+ chars) in `backend/.env` and restart the API.
2. Open the sign-in screen; the **Create administrator** option appears only while no Super Admin exists.
3. Enter the setup key, name, email, and a password (at least 12 chars), then create the administrator.
4. Remove `ADMIN_BOOTSTRAP_TOKEN` from the environment after setup.

Alternatively, bootstrap from a trusted terminal:
```sh
python -m bootstrap_admin
```

## 4. Frontend setup (step by step)

```sh
# 1. Enter the frontend folder
cd frontend

# 2. Install dependencies
npm ci

# 3. (Optional) Override the API origin
#    Create frontend/.env with: VITE_API_BASE_URL=http://127.0.0.1:8000

# 4. Run the dev server
npm run dev
# The app is available at http://localhost:5173 (default Vite port)
```

│   │   ├── features/employees/   # EmployeeProfilePanel
│   │   └── features/organization/# OrganizationStructure
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── README.md             # quick start + scope/limitations
├── USER_MANUAL.md        # end-user feature guide
├── TODO.md               # current task tracking
└── docs/                 # ARCHITECTURE, DESIGN_SYSTEM, ROLE_PERMISSION_MATRIX, etc.
```
## 5. Running the test suites

### Backend
```sh
cd backend
source .venv/bin/activate
python -m pytest -q
```
Expected: all tests pass (34 tests). Two pre-existing warnings are non-fatal:
- Starlette/httpx TestClient deprecation warning
- SQLAlchemy reflection warnings for expression-based indexes in migrations

### Frontend
```sh
cd frontend
npm test          # vitest run (14 tests)
npm run lint      # ESLint
npm run build     # tsc -b + vite build (production)
```
Expected: all tests pass, lint clean, production build clean.

## 6. Code quality checks (CI-style)

Run all of the following before pushing changes:

```sh
# backend
cd backend && source .venv/bin/activate && python -m pytest -q

# frontend
cd frontend && npm test && npm run lint && npm run build
```

## 7. How the left navigation menu works (relevant to "show for all users")

The sidebar (`frontend/src/WorkforceApp.tsx`, `<aside className="app-sidebar">`) renders for **every
authenticated user**, regardless of role. The visible menu items are the modules returned by
`GET /api/my-permissions` that are also in the user's `accessible_modules`.

- Role-based module access is **server-enforced** (backend `application.py`, `/api/my-permissions` and
  `require_module` dependency). The frontend only hides navigation; the API still rejects unauthorized calls.
- Default seeded permissions give every role — including `Employee` — access to Overview, My Profile /
  Employees, Attendance, Leave, Settings, Notifications, and more (see `docs/ROLE_PERMISSION_MATRIX.md`).
- When a user signs out, changes their password, or ends their current session, the module cache is reset so
  the next account never inherits the previous user's menu.

## 8. Adding a new module (developer reference)

1. Add an entry to `DEFAULT_MODULES` in `backend/application.py` with `module_key`, `name`, `description`,
   and `default_granted` roles.
2. Add a matching label/icon to `MODULE_LABELS` in `frontend/src/WorkforceApp.tsx`.
3. Add the section key to the `Section` type and a description to `sectionDescription()`.
4. Add the frontend UI branch under `{active === "<key>" && ...}` and a loading block in `useEffect`.
5. Add backend route(s) protected by `require_module("<key>")` and `require_roles(...)` as needed.
6. Run `alembic revision --autogenerate -m "..."` and `alembic upgrade head` if the schema changes.

## 9. Environment variables

Backend (`backend/.env`):
- `DATABASE_URL` — SQLAlchemy URL (default SQLite `users.db`)
- `NEXORA_SECRET_KEY` — required signing key (32+ chars; rejected in production if it is the dev default)
- `CORS_ORIGINS` — allowed frontend origins
- `ADMIN_BOOTSTRAP_TOKEN` — one-time first Super Admin setup key (remove after setup)

Frontend (`frontend/.env`):
- `VITE_API_BASE_URL` — API origin (default `http://127.0.0.1:8000`)

## 10. Useful references

- `README.md` — quick start, scope, and known limitations
- `USER_MANUAL.md` — end-user feature guide
- `docs/ARCHITECTURE.md`, `docs/DESIGN_SYSTEM.md`, `docs/ROLE_PERMISSION_MATRIX.md`
- `docs/IMPLEMENTATION_PLAN.md` — stage status and scope
- `docs/TRACEABILITY.md` — acceptance evidence

