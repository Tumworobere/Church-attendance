# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Church Register: a single-app Django 6 project (`config/` = project, `registry/` = the only app) for registering members and visitors and taking attendance at services. SQLite (`db.sqlite3`, gitignored, holds the live records — don't delete or reset it). No JS build step, no linter config, no frontend framework.

## Commands

```bash
source venv/bin/activate
python manage.py runserver                     # http://127.0.0.1:8000 (login required)
python manage.py test registry                 # all tests
python manage.py test registry.tests.RegisterTests.test_toggle_attendance   # one test
python manage.py makemigrations registry && python manage.py migrate
python manage.py createsuperuser               # there are no default credentials; a fresh DB has no users
python manage.py changepassword <username>     # passwords are hashed and can't be recovered, only reset
```

Env vars read in `config/settings.py`: `CHURCH_NAME` (header text, default Christ Heart Ministries International; exposed to all templates via `registry.context_processors.church`) and `TIME_ZONE` (defaults to `Africa/Kampala`; determines what `timezone.localdate()` treats as "today").

## Architecture

- **Every view is function-based and `@login_required`**; state-changing endpoints use `@require_POST`. Auth uses Django's built-in `LoginView`/`LogoutView` (`config/urls.py`) with `registration/login.html`.
- **Branches**: `Member`, `Visitor` and `Service` each have a required `branch` FK (`Ministry`/`ServiceType` are shared). `registry.middleware.BranchMiddleware` sets `request.branch` from the session (set by the header dropdown via `branch_switch`; falls back to the oldest branch, Kisaasi). **Every view must filter by `request.branch`** — lookups use `get_object_or_404(..., branch=request.branch)` so other branches' records 404 — and new records get `branch=request.branch` via `form.save(commit=False)`. `stats.absence_streaks` and `Importer.read`/`setup` take the branch. Branches are added in the admin.
- **Data model** (`registry/models.py`): `Service` is unique per (branch, date, `ServiceType`). `Attendance` links a service to *exactly one* of `member` or `visitor` (DB `CheckConstraint`), with partial unique constraints preventing double check-in. A `Visitor` can be converted to a `Member` via `Visitor.member` (OneToOne). Birthdays are stored as `Member.birth_day` + `birth_month` only (no year, by the church's choice; `Member.clean` rejects impossible days like 31 April, and `Member.birthday` formats "18 October"). Service total = member attendances + visitor attendances + `Service.extra_headcount` (unnamed people).
- **Seed data**: default service types and ministries are created by data migration `0002_default_data.py`; tests rely on it (e.g. `ServiceType.objects.get(name="Sunday Service")`). `0004_branch.py` creates "Kisaasi Branch" and assigns pre-existing records to it; tests use it as `self.branch`.
- **`registry/stats.py`** holds all attendance math shared by dashboard, member list and reports: `services_with_counts` (annotates `n_members`/`n_visitors` and sets `.total`), `member_rates` (only counts services on/after a member's `member_since`), `absence_streaks` (active members who missed the N most recent services), and `chart_bars` (precomputes geometry for the dashboard's inline-SVG stacked bar chart — there's no charting library).
- **Check-in flow**: `service_open` uses `get_or_create` so several ushers opening the same service land on the same record. `toggle_attendance` deletes-or-creates and swallows `IntegrityError` for concurrent check-ins. In `checkin.html`, forms with class `js-toggle` are submitted via `fetch` with header `x-requested-with: fetch`, and the view returns JSON (`present`, `counts`); without JS it falls back to a normal POST + redirect. Keep both paths working.
- **Query-string handoffs**: `visitor_new?service=<pk>` registers a visitor at a service (adds the `mark_present` field to `VisitorForm`, then redirects back to check-in); `member_new?from_visitor=<pk>` pre-fills a member from a visitor and marks the visitor `JOINED`.
- **Redirects from `next`** POST params are only followed if they start with `/` and not `//` (open-redirect guard) — reuse that pattern.
- **CSV upload** (`registry/importer.py`; `members/import/`, `visitors/import/`, each with a `template.csv`): an `Importer` subclass per model (`MEMBERS`, `VISITORS`) defines columns, the column guide shown on the shared `import.html` page, per-row normalisation (`prepare`: choice value-or-label, ministry by name, day-first dates, defaults) and the duplicate key (name + phone digits). Rows are validated through `MemberForm`/`VisitorForm`; any error means nothing is saved; duplicates are skipped. Columns match the exports (unknown columns like the visitors export's "Visits" are ignored; renamed headers stay accepted via `aliases`, e.g. "Household" → `Member.cell`), so an export can be re-uploaded.
- **CSV exports** go through `views._csv`, which writes a UTF-8 BOM (for Excel) and prefixes cells starting with `= + - @` with `'` to prevent formula injection.
- **Templates/CSS**: `registry/templates/registry/base.html` is the layout; `_form_fields.html` renders form fields generically. All styling is in `registry/static/registry/style.css` (purple/gold palette taken from the logo at `static/registry/img/logo.png`; the header band uses the `--brand*` tokens), using CSS custom properties on `:root` with a `prefers-color-scheme: dark` override — add colors as tokens in both blocks.

## Deployment notes (from README)

Before hosting publicly: set `DJANGO_SECRET_KEY` (settings falls back to a public dev-only key), set `DEBUG = False`, fill `ALLOWED_HOSTS`, run `collectstatic`. For ushers on local Wi-Fi: `runserver 0.0.0.0:8000` and add the machine's IP to `ALLOWED_HOSTS`. Ushers are plain Django users created in the admin (no staff status needed).
