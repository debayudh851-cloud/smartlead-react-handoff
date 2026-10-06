# SMARTLEAD React developer handoff

This folder supplies a framework-independent TypeScript API client. The separate handoff repository also includes the runnable PostgreSQL/Django backend, model integration, API contract, OpenAPI schema and Postman JSON collection so you can work independently.

Read `docs/SETUP.md`, `docs/API_CONTRACT.md` and `docs/IMPLEMENTATION_DECISIONS.md`. Start the backend locally, configure React's API base and CORS origin, then build the user/admin screens. No private credentials or API keys are supplied.

Required screens: service listing/details/search, registration/login/recovery, profile/password change, wishlist/reviews, enquiry history, notifications, staff lead list/detail/assignment/status/history/follow-ups, prediction view, service/category management, review moderation, SEO and dashboard analytics; super-admin account management must remain separate.

Use `client.ts` as a reference service layer or generate types from `docs/openapi.yaml`. Handle pagination, field-array errors, `detail` and legacy `error` messages, role denial, token expiry and model-unavailable responses. For image uploads use FormData rather than the JSON client helper. Use unique Idempotency-Key values for enquiry submissions and retain a key for a retry of the same payload.

The model is educational/demonstration-only; show is_demo and model_version wherever predictions are displayed. API prices are decimal strings; convert only for display. Follow-up datetimes require timezone-aware ISO 8601 values. Browser engagement is client-reported and must not be described as verified traffic analytics.

Do not copy backend secrets into Vite environment variables. Client-visible environment values may contain API origin, never Django/PostgreSQL credentials.


## User, admin and superuser portals

Separate interfaces are available at `/user/`, `/admin-portal/` and `/superuser/`. Admin registration requires superuser approval before requirement access. See `docs/ROLE_PORTALS.md` for PostgreSQL relationships, registration, role-specific login and API endpoints. Apply migrations when updating an existing installation.
