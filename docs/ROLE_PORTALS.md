# Three SMARTLEAD interfaces

| Interface | Local URL | Access |
|---|---|---|
| User | http://127.0.0.1:8000/user/ | Register, log in, submit requirements, track own enquiries and profile |
| Admin | http://127.0.0.1:8000/admin-portal/ | Register, log in after approval, see user requirements and manage leads/follow-ups |
| Superuser | http://127.0.0.1:8000/superuser/ | Log in, view users and admins, approve/reject admin registrations, activate/deactivate accounts, oversee leads |

Create the initial superuser interactively from `backend` with `python manage.py createsuperuser`. No public superuser registration and no bundled login credentials. Django's existing management interface remains at `/admin/`.

## Admin registration

An admin signs up with username, email and password. The application starts as PENDING. Only a superuser can approve it. Approval grants the existing Django `is_staff` role; rejected or pending applications cannot access admin requirements. An applicant can sign in to the ordinary user portal while awaiting approval, with ordinary user permissions. Existing staff and superuser accounts remain valid.

Passwords are hashed by Django and never returned in account lists. Roles are checked by the server on every protected API request. A user cannot grant admin or superuser access through the public registration form.

## PostgreSQL relationships

Run `python manage.py migrate` on each installation. Migration `business.0002_adminregistration` creates `business_adminregistration`, linked one-to-one to `auth_user`, with status, review timestamps, and `reviewed_by_id` pointing to the approving superuser in `auth_user`.

The shared `auth_user` table stores all login identities. `is_staff` marks admins; `is_superuser` marks superusers. `business_profile.user_id` stores optional profile details. `business_enquiry.user_id` connects each requirement to its user and `service_id` connects it to a service. `business_lead.enquiry_id` connects a lead to its requirement; `assigned_to_id` connects an assignment to an admin. Foreign keys preserve these connections. Keep this shared identity table rather than maintaining separate password tables for each role.

Tables are created by versioned Django migrations; the superuser portal manages account records and approvals. PostgreSQL credentials remain in the ignored local `.env` file.

## API contract

- `POST /api/user/register/` creates an ordinary user.
- `POST /api/admin/register/` creates a pending admin application; returns a message and registration ID, without admin tokens.
- `POST /api/user/login/`, `/api/admin/login/`, `/api/superuser/login/` accept username/password and enforce the selected role. Wrong-role or pending admin login returns 401.
- `GET /api/admin/accounts/?role=user|admin|superuser` is superuser-only; omit role for all accounts. Response is paginated and includes role, email and activation flags.
- `GET /api/superuser/admin-registrations/` is superuser-only and paginated.
- `POST /api/superuser/admin-registrations/{id}/decision/` accepts `{"status":"APPROVED"}` or `{"status":"REJECTED"}`. A second decision returns 400. Review and role update commit atomically.
- `PATCH /api/admin/accounts/{id}/` lets superusers manage account activation and role flags. Self-demotion/deactivation is blocked.
- `GET /api/leads/` and existing lead operations require an active admin or superuser. Ordinary users use `/api/enquiries/` to see their own requirements.

Legacy generic JWT login remains for compatibility; it does not bypass protected API permissions. New React screens should use the role-specific login methods in `react-handoff/client.ts`.


## Fictional local demonstration

With DEBUG=True, run `python manage.py seed_demo` from backend. It adds ordinary demo accounts, a pending admin application, five fictional requirements across lead statuses, a follow-up, wishlist, approved sample review and scores from the actual demonstration model. Re-running leaves existing sample records unchanged. New random passwords are saved only in ignored `backend/LOCAL_ACCESS.txt`; do not publish this file.

For a local demonstration where you explicitly want privileged test accounts, run `python manage.py seed_demo --with-privileged-accounts`. This additionally creates demo_admin and demo_superuser with random local credentials. Default seeding creates no privileged accounts. The sample records are prefixed [DEMO] and emails use example.com.
