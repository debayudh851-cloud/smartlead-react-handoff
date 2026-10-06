# SDLC Django Project

## Scope and handoff compatibility

This standalone Django project implements all nine APIs documented in `SDLC_React_Handoff.zip`. It reuses the handoff's backend implementation, validators and regression tests, preserves API paths, HTTP methods and JSON shapes, and adds a simple Django-served account portal. The Django settings package is named `sdlc_django_project`. SQLite is the default database; Django's built-in User model handles accounts, password hashing and staff permissions. No original database, credentials or environment secrets are included.

The supplied source has no project-management, tasks, workflow or SDLC-stage APIs. Those are outside this handoff's scope.

## Start locally (Windows PowerShell)

Extract `sdlc_django_project.zip`, then enter its `sdlc_django_project` directory. Python 3.12 is recommended and was used for verification.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
# Put the generated value into DJANGO_SECRET_KEY in .env.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

Open http://127.0.0.1:8001/ for the simple account portal; `/admin/` provides Django's administrative interface. Admin API login uses JWT and is separate from Django admin's cookie session. Create your own administrator; public registration always creates a normal user even when privilege fields are submitted.

## Complete API map

All request bodies are JSON. Keep trailing slashes. Except for the staff user list, all endpoints are public. Both roles use the same token APIs.

| Method | Route | Request fields | Success |
|---|---|---|---|
| POST | `/api/user/register/` | `username`, `email`, `password` | 201: `message`, `user: {id, username, email}`, `tokens: {refresh, access}` |
| POST | `/api/token/` | `username`, `password` | 200: `refresh`, `access` |
| POST | `/api/token/refresh/` | `refresh` | 200: `access` |
| POST | `/api/user/forgot-password/` | `email` | 200: generic `message`; sends user reset email if eligible |
| POST | `/api/user/reset-password/` | `uid`, `token`, `new_password`, `confirm_password` | 200: `message` |
| POST | `/api/user/forgot-username/` | `email` | 200: generic `message`; sends username email if eligible |
| GET | `/api/admin/users/` | Header `Authorization: Bearer ACCESS_TOKEN` | 200: `count`, `users: [{id, username, email, is_staff, date_joined}]` |
| POST | `/api/admin/forgot-password/` | `email` | 200: generic `message`; sends staff reset email if eligible |
| POST | `/api/admin/reset-password/` | `uid`, `token`, `new_password`, `confirm_password` | 200: `message` |

Example registration:

```json
{"username":"new_member","email":"member@example.com","password":"TEST_PASSWORD_FROM_PRIVATE_ENV"}
```

Example password reset:

```json
{"uid":"COPY_FROM_EMAIL","token":"COPY_FROM_EMAIL","new_password":"TEST_PASSWORD_FROM_PRIVATE_ENV","confirm_password":"TEST_PASSWORD_FROM_PRIVATE_ENV"}
```

User recovery excludes staff accounts; admin recovery requires `is_staff=true`. Inactive accounts cannot recover or authenticate. The list includes all users, newest first, and has no pagination, filtering or modification endpoints. The API root `/api/` remains a 404, as documented in the original handoff.

## Validation, errors and authentication

- Registration requires username (maximum 150 characters using Django's username rules), valid email (maximum 254 characters and exactly one `@`), and password. Duplicate username and case-insensitive duplicate email return 400; email is normalized to lowercase.
- Passwords require at least eight characters with an ASCII letter and a digit, and must pass Django similarity, common-password and numeric-password checks. Reset requires matching confirmation and a password different from the current password.
- Missing, empty, whitespace-only, null, malformed and overlength fields are rejected. Field errors use arrays, for example `{"email":["Enter a valid email address."]}`. Reset token errors use an `error` string; confirmation mismatch may use a string field error. React should handle these shapes.
- Invalid credentials/JWTs return 401; a valid normal-user JWT on the staff list returns 403. Unsupported methods return 405, though authentication may be evaluated first. Invalid input/reset links return 400. Anonymous throttling returns 429 after 100 requests per hour per client IP.
- Access JWT lifetime is 30 minutes; refresh lifetime is one day. Reset links expire after one hour and cannot be reused after a successful password change. Changing a password revokes existing access and refresh JWTs. Deleted/inactive accounts cannot refresh.
- Recovery responses do not expose whether an email belongs to an account. A 200 recovery response does not guarantee delivery; check email service logs. Accounts sharing an email in an imported database may each receive eligible recovery messages.

## Simple browser interface

The home page provides sign-in, registration, user/admin password recovery, username recovery, password reset, JWT refresh, sign-out and staff user listing. Email reset links prefill role, UID and token. UI tokens are kept only in page memory; reload signs the page out. Sign-out clears local tokens and the displayed user list; there is no server-side logout endpoint in the handoff. JWTs remain valid until expiry or password change. Validation results are shown as JSON; user table cells are inserted as text.

The default `.env.example` uses `FRONTEND_URL=http://127.0.0.1:8001` so recovery links open this interface. Console email output is the local default; recovery links appear in the server terminal.

## React integration

Set `CORS_ALLOWED_ORIGINS` to the exact React origin(s), separated by commas. The default permits `http://localhost:5173`; `http://127.0.0.1:5173` is a different origin. Set `FRONTEND_URL` to the React app origin when React owns recovery pages. React must serve `/user/reset-password/:uid/:token/` and `/admin/reset-password/:uid/:token/`, and POST the extracted values to the matching API.

Use JSON with `Content-Type: application/json`. Attach `Authorization: Bearer <access>` only to protected calls. On expired access, refresh once and retry; failed refresh requires login. Preserve the refresh token when the refresh response contains only an access token. Registration nests tokens inside `tokens`; login returns them at the top level. Render generic recovery messages and backend field errors. Never offer public admin registration or derive permission solely from client-side state.

The included `React_API_Handoff.md` is the original detailed manual checklist, not evidence that every checklist case was rerun for this delivery. The original Postman YAML requests are under `postman/`; review them with the original handoff instructions rather than assuming they are a conventional Postman collection JSON.

## Configuration and deployment

`DJANGO_SECRET_KEY` is required; create a strong private value. `.env` is loaded from the project root. Configure `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL` and email settings through environment variables or `.env`.

For real email, set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and `DEFAULT_FROM_EMAIL`.

For deployment set debug false, use HTTPS, configure secure cookies/proxy behavior for your host, serve static assets after `manage.py collectstatic`, use a production WSGI/ASGI server, configure database backups, and run `manage.py check --deploy`. Django's development server and console email are local defaults. SQLite and process-local throttling need review for multi-worker/high-volume deployment; use a shared cache and suitable database. Registration email uniqueness is checked in the serializer, not constrained in Django's built-in User table, so concurrent duplicate-email registrations require a database-level design before strict uniqueness can be guaranteed.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
```

The existing tests cover registration, privilege prevention, validation, login/refresh, permissions, recovery email eligibility, reset expiry/reuse, password/JWT revocation, inactive/deleted accounts and CORS. Additional delivery tests cover portal/reset pages, static asset discovery and resolution of all nine API routes. See `VERIFICATION.md` for the results of this delivery. Real SMTP delivery and a separately developed React application are not tested here.
