# NEXORA Workforce OS — TODO

## Done (this session)
- [x] Fixed frontend lint errors: removed unused imports in `frontend/src/WorkforceApp.test.tsx`
- [x] Fixed frontend ESLint error: `setState` called synchronously inside a `useEffect` in `frontend/src/WorkforceApp.tsx` (moved module reset out of the effect body into `loadModules` failure path)
- [x] Verified frontend: 14/14 vitest tests pass, ESLint clean, TypeScript/Vite production build clean
- [x] Verified backend: 34/34 pytest tests pass
- [x] Confirmed left navigation sidebar renders for every authenticated user (all roles); modules are gated by the role's granted permissions (intentional, server-enforced, and covered by tests)
- [x] Backend default module seeding already grants the `Employee` role: Overview, My Profile/Employees, Attendance, Leave, Payroll, Performance, Learning, Notifications, Settings
- [x] Unified all branding to "Talentry Workforce OS": login page (`AuthScreen.tsx`, `index.html`), post-login sidebar (`WorkforceApp.tsx` brand + footer), mobile brand — removed all "NEXORA WORKFORCE OS" and "Workforce Portal" references
- [x] Started backend API (port 8000) and confirmed login flow works end-to-end (health 200, login 200 with access token)
- [x] Created Developer Manual — `docs/DEVELOPER_MANUAL.md`
- [x] Created TODO tracking — `TODO.md`

## In progress / next
- [ ] Premium attractive UI refresh (design direction needed; current UI is functional)
- [ ] Optional: browser end-to-end / accessibility tests (noted as outstanding in README)
- [ ] Upload project to GitHub (see guidance below)

## Background / known scope
- Backend: FastAPI + SQLAlchemy + Alembic, SQLite dev default
- Frontend: React 19 + TypeScript + Vite
- See README.md quick start for backend/frontend run commands
