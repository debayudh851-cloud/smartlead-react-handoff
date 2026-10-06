# SMARTLEAD React API contract

Version 1.0.0. The authoritative field-level contract is `openapi.yaml`, generated from this backend. Interactive reference: `/api/docs/`; downloadable schema: `/api/schema/`.

## Connection and authentication

Development API base: `http://127.0.0.1:8000/api`. The simple Django frontend is served at `/`; recovery portal at `/accounts/`. React normally runs on `http://localhost:5173`; configure CORS_ALLOWED_ORIGINS and FRONTEND_URL for its actual origin/reset routes.

Use trailing slashes. Send `Content-Type: application/json` except image uploads (multipart/form-data) and bodyless requests. Protected APIs require `Authorization: Bearer <access>`. There is no shared API key, and React must never receive the Django secret or database password.

Roles: GENERAL_USER (nonstaff), ADMIN (staff), SUPER_ADMIN (superuser). Staff operates all leads in this version. Only super-admins manage accounts. Public read access does not imply write access.

Login returns `{access, refresh}`. Registration returns `{message, user: {id, username, email}, tokens: {access, refresh}}`. Access lifetime is 30 minutes; refresh lifetime one day. Logout blacklists the submitted refresh token; existing access tokens expire normally. Password change/reset rejects previously issued tokens. A browser should clear its token state after logout/change/reset and sign in again when refresh fails.

## Endpoint inventory

Lists return `{count, next, previous, results}` with page size 20. Action arrays and the legacy user list are exceptions noted below. IDs are integers.

| Methods | Path relative to /api/ | Access | Purpose / input |
|---|---|---|---|
| POST | auth/register/ | Public | username, email, password |
| POST | auth/login/ | Public | username, password |
| POST | auth/refresh/ | Public with refresh token | refresh |
| POST | auth/logout/ | Authenticated | Own refresh token; success 204 |
| GET, PUT, PATCH | auth/profile/ | Owner | first_name, last_name, phone editable; id/username/email/role read-only |
| POST | auth/password/change/ | Authenticated | current_password, new_password, confirm_password |
| POST | user/forgot-password/ | Public | email; neutral response |
| POST | user/reset-password/ | Public | uid, token, new_password, confirm_password |
| POST | user/forgot-username/ | Public | email; username emailed, not returned |
| POST | admin/forgot-password/ | Public | Staff recovery email; neutral response |
| POST | admin/reset-password/ | Public | Staff uid/token and new password confirmation |
| GET | admin/users/ | Super-admin | Legacy `{count, users}` response, unpaginated |
| GET | admin/accounts/ | Super-admin | Paginated account list |
| GET, PATCH | admin/accounts/{id}/ | Super-admin | is_active, is_staff, is_superuser; self-demotion blocked |
| GET, POST | categories/ | Public read / Staff write | name, slug, description, is_active |
| GET, PUT, PATCH, DELETE | categories/{id}/ | Public read / Staff write | DELETE archives category |
| GET, POST | services/ | Public read / Staff write | category, name, slug, description, features[], starting_price, is_active |
| GET, PUT, PATCH, DELETE | services/{id}/ | Public read / Staff write | Details include images, packages and SEO; DELETE archives |
| GET | services/{id}/related/ | Public | Up to five same-category services; array |
| GET, POST | admin/images/ | Staff | service, image upload, alt_text; max 5 MB JPEG/PNG/WEBP |
| GET, PUT, PATCH, DELETE | admin/images/{id}/ | Staff | Manage image record |
| GET, POST | admin/packages/ | Staff | service, name, description, price, features[] |
| GET, PUT, PATCH, DELETE | admin/packages/{id}/ | Staff | Manage package |
| GET, POST | admin/seo/ | Staff | service, title, meta_description, keywords[], content |
| GET, PUT, PATCH, DELETE | admin/seo/{id}/ | Staff | Manage service metadata |
| GET, POST | wishlist/ | Authenticated owner | service; duplicate returns 400 |
| GET, DELETE | wishlist/{id}/ | Owner | Remove saved service |
| GET, POST | enquiries/ | Owner / Staff visibility | Create service enquiry and linked lead |
| GET | enquiries/{id}/ | Owner / Staff | Includes lead_id and current status |
| GET | leads/ | Staff | List/search/filter operational leads |
| GET, PATCH | leads/{id}/ | Staff | status, assigned_to; assignee must be active staff |
| GET, POST | leads/{id}/followup/ | Staff | GET array; POST notes, follow_up_date (future ISO datetime) |
| GET | leads/{id}/history/ | Staff | Audit changes array |
| GET | leads/{id}/predictions/ | Staff | Prediction history array |
| GET | followups/ | Staff | Paginated scheduled follow-ups |
| GET, PATCH | followups/{id}/ | Staff | notes, follow_up_date, completed; rescheduling resets reminder state |
| GET, POST | reviews/ | Public approved read / Authenticated create | service, rating 1-5, comment; own pending reviews visible while signed in |
| GET, PATCH, DELETE | reviews/{id}/ | Public approved read / Owner mutation | Editing resets moderation; service must be active |
| GET | admin/reviews/ | Staff | Moderation list |
| GET, PATCH | admin/reviews/{id}/ | Staff | is_approved; self-approval forbidden |
| GET | notifications/ | Owner | In-app notifications |
| GET, PATCH | notifications/{id}/ | Owner | is_read editable |
| POST | ml/predict/ | Staff | lead_id; returns 201 with prediction |
| GET | analytics/summary/ | Staff | Cohort totals, sources/services/statuses, due follow-ups, high demo predictions and approved-review average |
| GET | admin/dashboard/ | Staff | Same analytics response |

Legacy `user/register/`, `token/` and `token/refresh/` remain aliases for compatibility. `GET /api/` is now a router index, not the historical 404.

## Queries

- Lists: `page=2`.
- Categories: `search`, `ordering=name` or `-created_at`.
- Services: `search`, `category=<id>`, `min_price`, `max_price`, `ordering=name`, `starting_price`, `-starting_price` or `created_at`.
- Leads: `search`, `status`, `service=<id>`, `source=<exact source>`, `assigned_to=<id>`, `date_from=YYYY-MM-DD`, `date_to=YYYY-MM-DD`, `ordering=created_at`, `updated_at`, `status` (prefix `-` for descending).
- Reviews: `service=<id>`.
- Analytics: `date_from`, `date_to`, using lead creation date. Conversion rate = converted / closed; null if no closed leads.

## Enquiry example

```http
POST /api/enquiries/
Authorization: Bearer <access>
Content-Type: application/json
Idempotency-Key: a-client-generated-unique-request-id
```

```json
{
  "service": 1,
  "requirement": "Responsive business website",
  "contact_email": "customer@example.com",
  "contact_phone": "",
  "budget": "50000.00",
  "traffic_source": "Google",
  "keyword": "web development services",
  "total_visits": 3,
  "page_views_per_visit": 2.0,
  "time_on_website": 500
}
```

Required: service, requirement, contact_email, budget, traffic_source. Optional: contact_phone, keyword, landing_page, campaign and engagement inputs (default zero). previous_enquiries is server-derived. Prices/budgets are decimal strings in responses; engagement values are client estimates and must not be mistaken for verified analytics.

Successful creation returns the enquiry representation with id, lead_id, status=NEW and timestamps. Both records are transactional. Identical idempotent retries return the same enquiry with 200; conflicting payload returns 400. Keys are scoped to the authenticated user and contain 1-100 characters.

## Lead transitions and predictions

NEW -> CONTACTED or NOT_CONVERTED. CONTACTED -> FOLLOW_UP, QUALIFIED, CONVERTED or NOT_CONVERTED. FOLLOW_UP -> CONTACTED, QUALIFIED, CONVERTED or NOT_CONVERTED. QUALIFIED -> FOLLOW_UP, CONVERTED or NOT_CONVERTED. Terminal outcomes cannot be reopened.

Prediction response includes id, lead, probability (0-1), probability_band, model_version, features, is_demo=true and predicted_at. Defaults: HIGH >= .7, MEDIUM >= .4. The model is trained on education leads and is not validated for digital-service customers. Missing/invalid model artifact returns 503 without deleting the enquiry/lead.

## Responses and error handling

Success: 200 reads/updates/authentication, 201 creates, 204 delete/logout. Errors: 400 field/input validation, 401 missing/expired credentials, 403 role denial, 404 inaccessible/missing object, 405 unsupported method, 415 unsupported body format, 429 anonymous rate limit, 503 unavailable predictor. Anonymous limit is 100/hour/IP; the default cache is local process memory.

Validation errors follow DRF field arrays, e.g. `{"budget":["Ensure this value is greater than or equal to 0."]}`. Auth/permission errors use `{"detail":"..."}`; existing recovery reset errors use `{"error":"..."}`. Handle all three formats. Unexpected production failures must show a generic frontend message; do not expose tracebacks. DEBUG must be false in deployment.

For each endpoint test valid input, missing fields, bad values, missing authentication, insufficient role, missing object and response structure. Existing Postman YAML is historical; use the generated current JSON collection for this release. Do not mark manual Postman execution complete until actually performed.
