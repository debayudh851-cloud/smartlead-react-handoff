# Setup and execution

Requires Python 3.13 (tested), PostgreSQL (tested on local PostgreSQL 18), and a fresh virtual environment. No credentials are shipped.

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally: generate a random DJANGO_SECRET_KEY, set POSTGRES_DB/USER/PASSWORD/HOST/PORT, and use the real frontend URL/origin. Create the database with PostgreSQL administration tools. Use a dedicated database role with suitable migration permissions; the local development setup used the postgres administrative account, not a recommended production role. Never commit `.env`.

Generate a secret with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

Then:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_services
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/` for the simple Django frontend, `/accounts/` for registration/recovery, `/admin/` for Django Admin, and `/api/docs/` for API reference. The superuser login works in the staff workspace and Admin. General users can register themselves.

Create operational staff through Django Admin or the super-admin account API. Staff can use operational REST APIs; grant only the necessary catalog/content model permissions for Django Admin access. Staff cannot manage users through the API.

The configured FRONTEND_URL must match the actual reset screen. For the bundled frontend at default port 8000 set `FRONTEND_URL=http://127.0.0.1:8000`; for React use its origin and implement the documented reset routes.

## ML

The repository includes the trusted model artifact trained by this project and its metrics. Only load artifacts from trusted project administrators: joblib files can execute code. To reproduce training:

```powershell
# From repository root, after reviewing Kaggle's applicable usage terms
backend\.venv\Scripts\python.exe scripts\download_dataset.py
backend\.venv\Scripts\python.exe ml\train.py
```

Dataset rows are never inserted into the customer/lead tables. The four mapped prediction inputs are Lead Source, TotalVisits, Total Time Spent on Website and Page Views Per Visit. Budget, selected service and previous enquiries are stored in the business system but are not inputs to this demonstration model.

## Reminders and tests

Schedule `manage.py send_followup_reminders` externally (for example Windows Task Scheduler) at an agreed interval. It creates in-app reminders idempotently; it does not start a worker or send operational email alerts. SMTP configuration applies to account recovery.

```powershell
.\.venv\Scripts\python.exe manage.py test api business --noinput
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py spectacular --file ..\docs\openapi.yaml --validate
.\.venv\Scripts\python.exe -m pip check
```

The test database role needs permission to create/drop the temporary PostgreSQL test database. Local .env and SQLite data from the old project are not included in releases. This project uses PostgreSQL exclusively.

## Deployment

Use a supported production WSGI/ASGI server, TLS, DEBUG=false, exact hosts/origins, secure cookies, SMTP, persistent media storage, backups and a shared throttle cache. Configure reminder scheduling and protect staff accounts. Swagger UI uses CDN assets and may require network access. No cloud deployment has been performed.

## Employee admin access

Only users can sign up. Company admin accounts and credential recovery are managed by the superuser, with temporary passwords that must be replaced before requirement access. See `docs/ROLE_PORTALS.md` (or `ROLE_PORTALS.md` from this docs folder) for the current API and PostgreSQL relationships. Public admin signup, token-based admin reset and old admin-registration approval routes have been retired. Apply migrations before running this version.
