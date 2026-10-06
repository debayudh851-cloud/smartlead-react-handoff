# Employee admin access and role portals

Only regular users can sign up publicly at `/user/signup/`; they log in at `/user/`.
Company admins log in at `/admin-portal/`. There is no admin signup page or public admin registration API.
Superusers log in at `/superuser/`; create the initial superuser interactively with `python manage.py createsuperuser`.

## Employee accounts

The superuser creates an employee account by entering a unique login ID and work email in the superuser portal. The server generates a random temporary password and returns it once, without storing plaintext or sending it by email. The superuser shares it privately with the verified employee. The employee must replace it before accessing requirements. Password changes invalidate existing JWT access and refresh tokens; log in again afterwards.

## Forgotten credentials

An employee submits their work email and an optional message through the admin portal. The public response is the same whether the account exists or not. Repeated submissions share one pending request. Only a superuser can see requests, verify the employee through the company identity process, then issue a new temporary password or reject the request. The system does not automate identity verification. Resetting credentials also returns the login ID, invalidates existing tokens and requires a new password on next login. Superuser accounts cannot be reset through this employee flow; use Django's trusted management command for initial/bootstrap superuser recovery.

## API

- `POST /api/superuser/employees/`: superuser-only, body `{username, email}`. Returns `{id, username, temporary_password, must_change_password}` once. Responses use `Cache-Control: no-store`.
- `POST /api/admin/recovery-request/`: public, body `{email, reason?}`. Generic confirmation; no credentials or account details.
- `POST /api/admin/forgot-password/`: compatibility alias for the recovery-request flow; it no longer emails reset tokens.
- `GET /api/superuser/recovery-requests/`: superuser-only, paginated.
- `POST /api/superuser/recovery-requests/{id}/decision/`: superuser-only, body `{decision: RESET|REJECT}`. RESET returns new credentials once; REJECT returns null credentials. Already reviewed requests return 400.
- `GET /api/auth/profile/`: includes `must_change_password`.
- `POST /api/auth/password/change/`: accepts current_password, new_password and confirm_password; clears the temporary-password restriction atomically.
- Existing role-specific login, account lists, activation, requirements and lead APIs remain available.

Removed routes return 404: `/admin-portal/signup/`, `/api/admin/register/`, `/api/admin/reset-password/` and old admin-registration decision/list APIs. Existing regular user password recovery remains available. New React clients must discard credentials after private handoff and never store them in browser storage or logs.

## PostgreSQL

Apply `python manage.py migrate`. Migration `business.0003_employeeaccess_adminrecoveryrequest` creates `business_employeeaccess` (one-to-one auth_user, must_change_password, provisioned_by) and `business_adminrecoveryrequest` (employee user, reason, status, reviewed_by, timestamps). One pending recovery per employee is enforced by a conditional unique constraint. Employee creation and resets are atomic. Django hashes passwords in the shared auth_user table. Existing enquiry-to-user, lead-to-enquiry and assigned-admin foreign keys remain intact.

The legacy admin registration table is retained for history; its public routes and approval UI are retired. Existing staff remain valid; newly provisioned/reset employees receive the temporary-password restriction. This restriction applies to JWT-protected APIs and Django Admin session access.

## Local demo

With DEBUG=True, `python manage.py seed_demo` adds fictional ordinary-user requirements, follow-ups, reviews and model scores. It creates no employee privileges by default. New local credentials are saved only to ignored `backend/LOCAL_ACCESS.txt`. No credentials are shipped in GitHub or the ZIP.


## Private API documentation

The public header shows Only for admins, linking to `/superuser/`. API docs are available only after superuser login. Both `/api/docs/` and `/api/schema/` enforce superuser authorization, including direct URL requests. The superuser portal loads the schema with the in-memory JWT and renders endpoint/model documentation.
