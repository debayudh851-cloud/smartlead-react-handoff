# Django API handoff and complete regression checklist

Prepared 1 October 2026. Covers all nine implemented REST endpoints and the functional, validation, authentication, recovery, and integration scenarios below. This is a test specification, not a claim that every manual scenario has been executed.

## 1. Server and Postman setup

**HTTP port: 8001.** Backend: `http://127.0.0.1:8001`. React origin: `http://localhost:5173`. Port 5173 is the frontend, not the API. Port 8000 works only if you deliberately start Django there and change every request/environment accordingly.

```powershell
cd D:\SDLC
.\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8001
```

Keep this terminal visible to read console emails. If another server already occupies 8001, use the existing process or stop it before starting yours. URLs typed in Chrome send GET; use Postman for POST.

In Postman open/import the project postman folder (v3 YAML in Local Mode), select SDLC Local, and set base_url to http://127.0.0.1:8001. For a manual request choose the method beside the URL, Body > raw > JSON, and Send. All JSON POSTs require Content-Type: application/json. Public endpoints use No Auth. The admin list uses Authorization > Bearer Token with an access token only.

## 2. Test fixtures and rules

Create a disposable active staff admin with createsuperuser. Register a fresh normal user. Use test mailboxes you control in deployed environments. Do not use real customer accounts. Never include actual credentials or JWTs in this shared document.

| Placeholder | Meaning |
|---|---|
| qa_member_01 / qa_member_01@example.com | Fresh nonstaff account; change suffix on repeat runs |
| admin / admin@example.com | Your disposable staff account; replace if different |
| CURRENT_USER_PASSWORD | Actual current password for the normal account |
| CURRENT_ADMIN_PASSWORD | Actual current password for the staff account |
| USER_ACCESS / ADMIN_ACCESS | Fresh access JWTs from login |
| USER_REFRESH / ADMIN_REFRESH | Refresh JWTs from login |
| USER_UID / USER_RESET_TOKEN | Values from the fresh user reset email |
| ADMIN_UID / ADMIN_RESET_TOKEN | Values from the fresh admin reset email |

Generate test passwords locally and keep them only in your private test environment.

All defined input fields are required: test missing, empty string, whitespace-only, and null separately. Email must be valid and contain exactly one @. Registration email duplicate checks are case-insensitive; username uniqueness follows Django rules. Extra registration privilege fields are ignored and cannot grant privileges.

Access JWT: 30 minutes; refresh JWT: one day; reset token: one hour. Password changes reject existing access and refresh JWTs. Failed validation does not consume the reset token. Rate limit: 100 anonymous requests/hour/IP across endpoints; large test runs may hit 429. Use independent local test runs/restart the local in-memory server between batches; do not disable deployment throttling.

## 3. APIs separated by audience

### User APIs

| Method | Full HTTP URL | Purpose / access |
|---|---|---|
| POST | `http://127.0.0.1:8001/api/user/register/` | Public registration |
| POST | `http://127.0.0.1:8001/api/user/forgot-password/` | Regular-user email |
| POST | `http://127.0.0.1:8001/api/user/reset-password/` | Regular-user UID and reset token |
| POST | `http://127.0.0.1:8001/api/user/forgot-username/` | Regular-user email |

### Admin APIs

| Method | Full HTTP URL | Purpose / access |
|---|---|---|
| GET | `http://127.0.0.1:8001/api/admin/users/` | Staff access JWT required |
| POST | `http://127.0.0.1:8001/api/admin/forgot-password/` | Admin email; public recovery request |
| POST | `http://127.0.0.1:8001/api/admin/reset-password/` | Admin UID and reset token |

### Shared Authentication APIs

| Method | Full HTTP URL | Purpose / access |
|---|---|---|
| POST | `http://127.0.0.1:8001/api/token/` | Username/password; both roles |
| POST | `http://127.0.0.1:8001/api/token/refresh/` | Refresh JWT; both roles |

Login and refresh are shared by user and admin screens. Staff permissions are checked separately on the admin list. Django /admin/ is a session-based browser interface, not a REST API. No API root, logout, user CRUD, or admin registration endpoint exists.

## 4. Test execution order and reset guidance

Register the normal user, login both roles and save JWTs, check admin permissions, request recovery emails, perform validation cases with fresh valid links, and run successful resets last. Update current passwords after success. Original test IDs are retained, so numbering is intentionally nonsequential within audience groups.

Reset UID is the encoded database ID, not the username. Reset tokens are not JWTs. Use an unexpired pre-reset JWT to prove password-change revocation. Recovery JSON must not expose account existence, username, UID or reset token; inspect console emails separately. Email links are frontend routes at localhost:5173.

## 5. User API tests

Registration, regular-user password and username recovery, and post-reset login/token checks. Admin-list rejection using user tokens is also included in Admin API tests.

### T001: Successful normal-user registration

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 201**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Expect {message, user: {id, username, email}, tokens: {refresh, access}}. IDs vary. No password/hash in response. Save normal-user tokens. Verify is_staff=false and is_superuser=false using staff listing/backend inspection.

Record actual status, relevant response, and PASS/FAIL.

### T002: Duplicate username only

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "different@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Existing username, fresh email; username error.

Record actual status, relevant response, and PASS/FAIL.

### T003: Duplicate email only, ignoring case

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "fresh_other",
  "email": "QA_MEMBER_01@EXAMPLE.COM",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Existing email, fresh username; email error.

Record actual status, relevant response, and PASS/FAIL.

### T004: Attempt privilege escalation

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 201**.

Body > raw > JSON:

```json
{
  "username": "qa_privilege_01",
  "email": "qa_privilege_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "is_staff": true,
  "is_superuser": true
}
```

Verify the account remains nonstaff; its token must get 403 on admin/users/.

Record actual status, relevant response, and PASS/FAIL.

### T005: Uppercase email normalization

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 201**.

Body > raw > JSON:

```json
{
  "username": "qa_case_01",
  "email": "QA_CASE_01@EXAMPLE.COM",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Stored/returned email is lowercase.

Record actual status, relevant response, and PASS/FAIL.

### T006: Invalid username characters

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "bad name!",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T007: Username longer than 150 characters

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T008: Registration username: missing

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T009: Registration username: empty

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T010: Registration username: whitespace

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "   ",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T011: Registration username: null

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": null,
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T012: Registration email: missing

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T013: Registration email: empty

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T014: Registration email: whitespace

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "   ",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T015: Registration email: null

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": null,
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T016: Registration password: missing

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T017: Registration password: empty

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": ""
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T018: Registration password: whitespace

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T019: Registration password: null

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": null
}
```

Check the named field error.

Record actual status, relevant response, and PASS/FAIL.

### T020: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "no-at.example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T021: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "a@@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T022: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "\"a@b\"@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T023: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "a@",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T024: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T025: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "a b@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T026: Reject malformed/overlength email

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use a fresh username to isolate email validation.

Record actual status, relevant response, and PASS/FAIL.

### T027: Reject invalid/common password: Ab1!x

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use fresh username/email; check password error rather than duplicate error.

Record actual status, relevant response, and PASS/FAIL.

### T028: Reject invalid/common password: OnlyLettersHere

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use fresh username/email; check password error rather than duplicate error.

Record actual status, relevant response, and PASS/FAIL.

### T029: Reject invalid/common password: 1234567890

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use fresh username/email; check password error rather than duplicate error.

Record actual status, relevant response, and PASS/FAIL.

### T030: Reject invalid/common password: !!!!!!!!

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use fresh username/email; check password error rather than duplicate error.

Record actual status, relevant response, and PASS/FAIL.

### T031: Reject invalid/common password: Password123

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "email": "qa_member_01@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Use fresh username/email; check password error rather than duplicate error.

Record actual status, relevant response, and PASS/FAIL.

### T032: Reject username-similar password

**POST http://127.0.0.1:8001/api/user/register/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "SimilarityTest4826",
  "email": "similarity4826@example.com",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T078: user/forgot-password/ eligible

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "qa_member_01@example.com"
}
```

Expected JSON {"message": "If an eligible account exists, a password reset link has been sent."}. Console email must be generated; inspect recipient and content.

Record actual status, relevant response, and PASS/FAIL.

### T079: user/forgot-password/ case-insensitive

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "QA_MEMBER_01@EXAMPLE.COM"
}
```

Expected JSON {"message": "If an eligible account exists, a password reset link has been sent."}. Console email must be generated; inspect recipient and content.

Record actual status, relevant response, and PASS/FAIL.

### T080: user/forgot-password/ unknown

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "no-such-account-4826@example.com"
}
```

Expected JSON {"message": "If an eligible account exists, a password reset link has been sent."}. No email should be generated. Response must equal eligible response.

Record actual status, relevant response, and PASS/FAIL.

### T081: user/forgot-password/ wrong role

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "admin@example.com"
}
```

Expected JSON {"message": "If an eligible account exists, a password reset link has been sent."}. No email should be generated. Response must equal eligible response.

Record actual status, relevant response, and PASS/FAIL.

### T082: user/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{}
```

Record actual status, relevant response, and PASS/FAIL.

### T083: user/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T084: user/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "   "
}
```

Record actual status, relevant response, and PASS/FAIL.

### T085: user/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T086: user/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "invalid.example.com"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T087: user/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "a@@example.com"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T088: user/forgot-username/ eligible

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "qa_member_01@example.com"
}
```

Expected JSON {"message": "If an eligible account exists, a username reminder has been sent."}. Console email must be generated; inspect recipient and content.

Record actual status, relevant response, and PASS/FAIL.

### T089: user/forgot-username/ case-insensitive

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "QA_MEMBER_01@EXAMPLE.COM"
}
```

Expected JSON {"message": "If an eligible account exists, a username reminder has been sent."}. Console email must be generated; inspect recipient and content.

Record actual status, relevant response, and PASS/FAIL.

### T090: user/forgot-username/ unknown

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "no-such-account-4826@example.com"
}
```

Expected JSON {"message": "If an eligible account exists, a username reminder has been sent."}. No email should be generated. Response must equal eligible response.

Record actual status, relevant response, and PASS/FAIL.

### T091: user/forgot-username/ wrong role

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "admin@example.com"
}
```

Expected JSON {"message": "If an eligible account exists, a username reminder has been sent."}. No email should be generated. Response must equal eligible response.

Record actual status, relevant response, and PASS/FAIL.

### T092: user/forgot-username/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{}
```

Record actual status, relevant response, and PASS/FAIL.

### T093: user/forgot-username/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T094: user/forgot-username/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "   "
}
```

Record actual status, relevant response, and PASS/FAIL.

### T095: user/forgot-username/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T096: user/forgot-username/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "invalid.example.com"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T097: user/forgot-username/ email validation

**POST http://127.0.0.1:8001/api/user/forgot-username/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "a@@example.com"
}
```

Record actual status, relevant response, and PASS/FAIL.

Username email must contain the registered login username and go only to that registered mailbox; the API response must not contain it. Password-reset email links must use /admin/reset-password/<uid>/<token>/ or /user/reset-password/<uid>/<token>/ at the configured frontend origin. These React routes must be implemented by the frontend; Django does not supply those screens.

### T135: user reset uid missing

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T136: user reset uid empty

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T137: user reset uid whitespace

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "   ",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T138: user reset uid null

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": null,
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T139: user reset token missing

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T140: user reset token empty

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T141: user reset token whitespace

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "   ",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T142: user reset token null

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": null,
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T143: user reset new_password missing

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T144: user reset new_password empty

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T145: user reset new_password whitespace

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T146: user reset new_password null

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": null,
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T147: user reset confirm_password missing

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T148: user reset confirm_password empty

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T149: user reset confirm_password whitespace

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T150: user reset confirm_password null

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T151: user reset malformed UID

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "!!!!",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T152: user reset nonexistent user UID

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "OTk5OTk5OTk5",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T153: user reset invalid token

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "invalid",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T154: user reset confirmation mismatch

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T155: user reset overlength UID

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T156: user reset overlength token

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T157: user reset invalid password Ab1!x

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T158: user reset invalid password OnlyLettersHere

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T159: user reset invalid password 1234567890

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T160: user reset invalid password !!!!!!!!

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T161: user reset invalid password Password123

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T162: user reject current password

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "CURRENT_USER_PASSWORD",
  "confirm_password": "CURRENT_USER_PASSWORD"
}
```

Must specifically contain new_password: ["New password must be different from your current password."]. Invalid/expired-token errors do not prove this rule. Confirm password unchanged; the same valid link can still be used with a different password.

Record actual status, relevant response, and PASS/FAIL.

### T163: user reject expired reset link

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "EXPIRED_USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Obtain a link and wait beyond one hour, or use the automated expiry fixture; assert invalid/expired token error.

Record actual status, relevant response, and PASS/FAIL.

### T164: user reject wrong role account

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T165: user reject token paired with another UID

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "OTHER_USER_ACCOUNT_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Prepare two eligible accounts of the same role; pair first UID with second token.

Record actual status, relevant response, and PASS/FAIL.

### T166: user successful reset

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Expected {"message":"Password reset successfully."}. Password hashed, role flags unchanged, no password/hash in response. Update saved current password.

Record actual status, relevant response, and PASS/FAIL.

### T167: user reject reused reset token

**POST http://127.0.0.1:8001/api/user/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Immediately resend exact successful request; token is now invalid.

Record actual status, relevant response, and PASS/FAIL.

### T168: user old password login rejected

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": "PRE_RESET_USER_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T169: user new password login succeeds

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Save the fresh JWT pair. Staff gets 200 on users list; normal user gets 403.

Record actual status, relevant response, and PASS/FAIL.

### T170: user old access revoked

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer PRE_RESET_USER_ACCESS. Expected: **HTTP 401**.

No request body.

Use the token saved immediately before reset while it is still within its 30-minute lifetime. An expired token cannot isolate password-change revocation.

Record actual status, relevant response, and PASS/FAIL.

### T171: user old refresh revoked

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "PRE_RESET_USER_REFRESH"
}
```

Use a still-unexpired pre-reset refresh JWT; expect revocation failure rather than expiry.

Record actual status, relevant response, and PASS/FAIL.

## 6. Admin API tests

Staff-only listing, missing/invalid/normal-user JWT rejection, admin recovery and post-reset checks.

### T061: Staff access succeeds

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer ADMIN_ACCESS. Expected: **HTTP 200**.

No request body.

Expect {count, users}. Count equals array length; each entry has id, username, email, is_staff, date_joined. All accounts including admins are included, newest first. No passwords/hashes. Unpaginated.

Record actual status, relevant response, and PASS/FAIL.

### T062: Normal user denied

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer USER_ACCESS. Expected: **HTTP 403**.

No request body.

Response detail indicates insufficient permission.

Record actual status, relevant response, and PASS/FAIL.

### T063: Missing Authorization denied

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: No Auth. Expected: **HTTP 401**.

No request body.

Record actual status, relevant response, and PASS/FAIL.

### T064: Invalid/expired/wrong-type bearer rejected

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer invalid. Expected: **HTTP 401**.

No request body.

Record actual status, relevant response, and PASS/FAIL.

### T065: Invalid/expired/wrong-type bearer rejected

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer TAMPERED_ACCESS. Expected: **HTTP 401**.

No request body.

Record actual status, relevant response, and PASS/FAIL.

### T066: Invalid/expired/wrong-type bearer rejected

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer EXPIRED_ACCESS. Expected: **HTTP 401**.

No request body.

Record actual status, relevant response, and PASS/FAIL.

### T067: Invalid/expired/wrong-type bearer rejected

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer ADMIN_REFRESH. Expected: **HTTP 401**.

No request body.

Record actual status, relevant response, and PASS/FAIL.

### T068: admin/forgot-password/ eligible

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "admin@example.com"
}
```

Expected JSON {"message": "If an eligible admin account exists, a password reset link has been sent."}. Console email must be generated; inspect recipient and content.

Record actual status, relevant response, and PASS/FAIL.

### T069: admin/forgot-password/ case-insensitive

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "ADMIN@EXAMPLE.COM"
}
```

Expected JSON {"message": "If an eligible admin account exists, a password reset link has been sent."}. Console email must be generated; inspect recipient and content.

Record actual status, relevant response, and PASS/FAIL.

### T070: admin/forgot-password/ unknown

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "no-such-account-4826@example.com"
}
```

Expected JSON {"message": "If an eligible admin account exists, a password reset link has been sent."}. No email should be generated. Response must equal eligible response.

Record actual status, relevant response, and PASS/FAIL.

### T071: admin/forgot-password/ wrong role

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "email": "qa_member_01@example.com"
}
```

Expected JSON {"message": "If an eligible admin account exists, a password reset link has been sent."}. No email should be generated. Response must equal eligible response.

Record actual status, relevant response, and PASS/FAIL.

### T072: admin/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{}
```

Record actual status, relevant response, and PASS/FAIL.

### T073: admin/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T074: admin/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "   "
}
```

Record actual status, relevant response, and PASS/FAIL.

### T075: admin/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T076: admin/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "invalid.example.com"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T077: admin/forgot-password/ email validation

**POST http://127.0.0.1:8001/api/admin/forgot-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "email": "a@@example.com"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T098: admin reset uid missing

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T099: admin reset uid empty

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T100: admin reset uid whitespace

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "   ",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T101: admin reset uid null

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": null,
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T102: admin reset token missing

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T103: admin reset token empty

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T104: admin reset token whitespace

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "   ",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T105: admin reset token null

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": null,
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T106: admin reset new_password missing

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T107: admin reset new_password empty

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T108: admin reset new_password whitespace

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T109: admin reset new_password null

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": null,
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T110: admin reset confirm_password missing

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T111: admin reset confirm_password empty

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T112: admin reset confirm_password whitespace

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T113: admin reset confirm_password null

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T114: admin reset malformed UID

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "!!!!",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T115: admin reset nonexistent user UID

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "OTk5OTk5OTk5",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T116: admin reset invalid token

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "invalid",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T117: admin reset confirmation mismatch

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T118: admin reset overlength UID

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T119: admin reset overlength token

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T120: admin reset invalid password Ab1!x

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T121: admin reset invalid password OnlyLettersHere

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T122: admin reset invalid password 1234567890

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T123: admin reset invalid password !!!!!!!!

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T124: admin reset invalid password Password123

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Inspect new_password errors with a valid reset token.

Record actual status, relevant response, and PASS/FAIL.

### T125: admin reject current password

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "CURRENT_ADMIN_PASSWORD",
  "confirm_password": "CURRENT_ADMIN_PASSWORD"
}
```

Must specifically contain new_password: ["New password must be different from your current password."]. Invalid/expired-token errors do not prove this rule. Confirm password unchanged; the same valid link can still be used with a different password.

Record actual status, relevant response, and PASS/FAIL.

### T126: admin reject expired reset link

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "EXPIRED_ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Obtain a link and wait beyond one hour, or use the automated expiry fixture; assert invalid/expired token error.

Record actual status, relevant response, and PASS/FAIL.

### T127: admin reject wrong role account

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "USER_UID",
  "token": "USER_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T128: admin reject token paired with another UID

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "OTHER_ADMIN_ACCOUNT_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Prepare two eligible accounts of the same role; pair first UID with second token.

Record actual status, relevant response, and PASS/FAIL.

### T129: admin successful reset

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Expected {"message":"Password reset successfully."}. Password hashed, role flags unchanged, no password/hash in response. Update saved current password.

Record actual status, relevant response, and PASS/FAIL.

### T130: admin reject reused reset token

**POST http://127.0.0.1:8001/api/admin/reset-password/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "uid": "ADMIN_UID",
  "token": "ADMIN_RESET_TOKEN",
  "new_password": "TEST_PASSWORD_FROM_PRIVATE_ENV",
  "confirm_password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Immediately resend exact successful request; token is now invalid.

Record actual status, relevant response, and PASS/FAIL.

### T131: admin old password login rejected

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "username": "admin",
  "password": "PRE_RESET_ADMIN_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T132: admin new password login succeeds

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "username": "admin",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Save the fresh JWT pair. Staff gets 200 on users list; normal user gets 403.

Record actual status, relevant response, and PASS/FAIL.

### T133: admin old access revoked

**GET http://127.0.0.1:8001/api/admin/users/**

Authorization: Bearer PRE_RESET_ADMIN_ACCESS. Expected: **HTTP 401**.

No request body.

Use the token saved immediately before reset while it is still within its 30-minute lifetime. An expired token cannot isolate password-change revocation.

Record actual status, relevant response, and PASS/FAIL.

### T134: admin old refresh revoked

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "PRE_RESET_ADMIN_REFRESH"
}
```

Use a still-unexpired pre-reset refresh JWT; expect revocation failure rather than expiry.

Record actual status, relevant response, and PASS/FAIL.

## 7. Shared authentication API tests

Login and refresh are used by both roles. Successful login never grants staff privileges to a normal user.

### T033: USER valid login

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": "CURRENT_USER_PASSWORD"
}
```

Response {access, refresh}; save both. No password in response.

Record actual status, relevant response, and PASS/FAIL.

### T034: USER incorrect password

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T035: USER login username missing

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "password": "CURRENT_USER_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T036: USER login username empty

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "",
  "password": "CURRENT_USER_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T037: USER login username null

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": null,
  "password": "CURRENT_USER_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T038: USER login password missing

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T039: USER login password empty

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T040: USER login password null

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "qa_member_01",
  "password": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T041: USER valid refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "refresh": "USER_REFRESH"
}
```

Response {access}. Verify the new JWT is usable; normal user still gets 403 and staff gets 200 on the admin list.

Record actual status, relevant response, and PASS/FAIL.

### T042: USER expired refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "EXPIRED_USER_REFRESH"
}
```

Wait over one day or use a backend-generated expired fixture. Never fabricate a JWT signature manually.

Record actual status, relevant response, and PASS/FAIL.

### T043: ADMIN valid login

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "username": "admin",
  "password": "CURRENT_ADMIN_PASSWORD"
}
```

Response {access, refresh}; save both. No password in response.

Record actual status, relevant response, and PASS/FAIL.

### T044: ADMIN incorrect password

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "username": "admin",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T045: ADMIN login username missing

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "password": "CURRENT_ADMIN_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T046: ADMIN login username empty

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "",
  "password": "CURRENT_ADMIN_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T047: ADMIN login username null

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": null,
  "password": "CURRENT_ADMIN_PASSWORD"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T048: ADMIN login password missing

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "admin"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T049: ADMIN login password empty

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "admin",
  "password": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T050: ADMIN login password null

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "username": "admin",
  "password": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T051: ADMIN valid refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 200**.

Body > raw > JSON:

```json
{
  "refresh": "ADMIN_REFRESH"
}
```

Response {access}. Verify the new JWT is usable; normal user still gets 403 and staff gets 200 on the admin list.

Record actual status, relevant response, and PASS/FAIL.

### T052: ADMIN expired refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "EXPIRED_ADMIN_REFRESH"
}
```

Wait over one day or use a backend-generated expired fixture. Never fabricate a JWT signature manually.

Record actual status, relevant response, and PASS/FAIL.

### T053: Unknown username login

**POST http://127.0.0.1:8001/api/token/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "username": "no_such_account_4826",
  "password": "TEST_PASSWORD_FROM_PRIVATE_ENV"
}
```

Record actual status, relevant response, and PASS/FAIL.

### T054: Missing/blank/null refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{}
```

Record actual status, relevant response, and PASS/FAIL.

### T055: Missing/blank/null refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "refresh": ""
}
```

Record actual status, relevant response, and PASS/FAIL.

### T056: Missing/blank/null refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 400**.

Body > raw > JSON:

```json
{
  "refresh": null
}
```

Record actual status, relevant response, and PASS/FAIL.

### T057: Invalid or wrong-type refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "invalid"
}
```

Replace symbolic JWT fixtures with actual token values. USER_ACCESS means an access JWT, which is not a refresh JWT.

Record actual status, relevant response, and PASS/FAIL.

### T058: Invalid or wrong-type refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "   "
}
```

Replace symbolic JWT fixtures with actual token values. USER_ACCESS means an access JWT, which is not a refresh JWT.

Record actual status, relevant response, and PASS/FAIL.

### T059: Invalid or wrong-type refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "USER_ACCESS"
}
```

Replace symbolic JWT fixtures with actual token values. USER_ACCESS means an access JWT, which is not a refresh JWT.

Record actual status, relevant response, and PASS/FAIL.

### T060: Invalid or wrong-type refresh

**POST http://127.0.0.1:8001/api/token/refresh/**

Authorization: No Auth. Expected: **HTTP 401**.

Body > raw > JSON:

```json
{
  "refresh": "TAMPERED_REFRESH"
}
```

Replace symbolic JWT fixtures with actual token values. USER_ACCESS means an access JWT, which is not a refresh JWT.

Record actual status, relevant response, and PASS/FAIL.

## 9. State-dependent backend tests

Use disposable accounts and Django admin /admin/ or backend fixtures to prepare states; do not mutate production accounts. Every row is a separate test for both roles where applicable.

| Scenario | HTTP request/body | Expected |
|---|---|---|
| Inactive account login | POST http://127.0.0.1:8001/api/token/; {"username":"INACTIVE_USERNAME","password":"CURRENT_PASSWORD"} | 401 |
| Inactive account refresh | POST http://127.0.0.1:8001/api/token/refresh/; {"refresh":"TOKEN_ISSUED_BEFORE_DEACTIVATION"} | 401 |
| Deleted account refresh | Same refresh request after deleting disposable account | 401, no server error |
| Inactive account access | GET http://127.0.0.1:8001/api/admin/users/ with access issued before deactivation | 401 |
| Staff demoted after JWT issuance | Same GET with still-valid staff token after is_staff=false | 403 |
| Inactive recovery | POST matching forgot-password/forgot-username endpoint; {"email":"INACTIVE_ACCOUNT_EMAIL"} | Generic 200, no email |
| Unusable-password account recovery | Same request after setting unusable password in fixture | Generic 200, no email |
| Inactive reset | POST matching reset endpoint using token issued while active | 400, password unchanged |
| Failed same-password reset | Use valid link/current password then valid link/different password | 400 then 200; rejected attempt did not consume token |
| Case-insensitive email lookup | Uppercase eligible email | 200 and correct recipient |

Run inactive/deleted/cross-role and reset-expiry checks through the Django suite when manual state setup is inconvenient. They are not substitutes for claiming manual Postman completion.

## 10. HTTP protocol, browser CORS, throttling

| Test | Request | Expected |
|---|---|---|
| POST endpoint wrong method | GET each listed POST URL with No Auth | 405 |
| Admin list wrong method | POST http://127.0.0.1:8001/api/admin/users/ with valid admin Bearer and {} | 405; missing auth may return 401 first |
| Malformed JSON | POST registration with Content-Type application/json and raw body { | 400 JSON parse error |
| Unsupported body format | POST registration with Content-Type text/plain and nonempty text | 415 |
| Unknown route/API root | GET http://127.0.0.1:8001/api/ | 404; no API landing page exists |
| Throttle | Send >100 anonymous requests from one IP within one hour | 429 with Retry-After once budget exhausted; prior requests in the hour count |
| Allowed CORS | OPTIONS registration, Origin http://localhost:5173, Access-Control-Request-Method POST, Access-Control-Request-Headers content-type | 200; Access-Control-Allow-Origin matches origin; POST and content-type allowed |
| Disallowed CORS | Same OPTIONS with Origin https://untrusted.example | No Access-Control-Allow-Origin for that origin; browser blocks cross-origin response |

OPTIONS has no JSON body. Also test the React browser itself: registration/login/reset fetch calls, Authorization header on protected calls, and permitted preflight. Postman does not enforce CORS. Only http://localhost:5173 is allowed by default; http://127.0.0.1:5173 is a different origin. Missing trailing slashes on POST can cause redirects/errors; use the exact URLs.

## 11. Error formats and React behavior

```json
{
  "email": [
    "Enter a valid email address."
  ]
}
```

```json
{
  "confirm_password": [
    "Passwords do not match."
  ]
}
```

```json
{
  "new_password": [
    "New password must be different from your current password."
  ]
}
```

```json
{
  "error": "Invalid or expired password reset token."
}
```

```json
{
  "detail": "You do not have permission to perform this action."
}
```

Exact framework wording may vary; assert status, relevant error field/code, and meaning. React handles 201 registration, 200 success, 400 field errors, 401 login/refresh, 403 insufficient role, 429 retry delay, and unexpected errors. Do not blindly treat all 401s as a permission failure.

## 12. Verification record and known limits

Latest completed Django suite: 21 test methods passed, with multiple parameterized subcases. Earlier live HTTP report: 16 checks for original API scope. Later targeted HTTP recovery/validation checks were performed separately. This checklist adds manual scenarios not all executed yet; leave results Pending until tested.

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py test api --verbosity 2
.\.venv\Scripts\python.exe -m pip check
```

All test methods mapped to this checklist:
- `test_registration`
- `test_registration_validation`
- `test_permissions`
- `test_login_refresh`
- `test_forgot_password`
- `test_reset_revokes_tokens`
- `test_invalid_reset`
- `test_reset_expiry`
- `test_expired_jwts`
- `test_inactive_deleted_refresh`
- `test_cors`
- `test_user_forgot_password_email`
- `test_user_reset_and_jwt_revocation`
- `test_user_reset_rejects_admin_and_invalid_requests`
- `test_username_recovery`
- `test_inactive_user_recovery`
- `test_required_registration_fields`
- `test_email_and_recovery_required_fields`
- `test_password_letters_numbers_and_length`
- `test_reset_current_password_rejected_without_consuming_token`
- `test_reset_required_fields`

Password hashes require backend inspection; HTTP responses alone cannot prove storage hashing. Email failure/privacy tests use mocked email delivery where necessary: delivery failures should log an error and keep a generic 200 without leaking account existence. Duplicate database emails are possible with built-in User; recovery emails every eligible match, with separate account-specific links/reminders. Application-level duplicate email checks do not guarantee uniqueness under concurrent registrations. The user list is unpaginated. Email ownership verification, password history, cross-account password uniqueness, and account recovery without email access are not implemented.

For each case record: Test ID, fixture/account, timestamp, expected status, actual status, response assertion, email assertion where needed, PASS/FAIL/Pending, and evidence reference. Do not save real passwords or tokens in shared evidence.

## 13. React handoff checklist

- Configure base_url and allowed frontend origin; localhost on another computer refers to that computer.
- Implement registration/login/admin list/user and admin reset screens plus user username reminder.
- Keep admin and user UID/token variables separate.
- Use neutral recovery messages; never infer account existence from generic 200.
- Use SMTP for real inbox delivery; console backend only prints emails locally.
- Use actual deployed HTTP(S) base URL and deployment configuration when publishing.
- Re-run this checklist after backend changes and record results independently from automated tests.
