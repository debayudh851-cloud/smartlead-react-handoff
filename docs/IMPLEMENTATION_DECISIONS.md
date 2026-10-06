# Implemented decisions

These decisions make version 1 concrete. They can be revised with reviewed migrations/API changes.

- PostgreSQL is the only application database. The previous SQLite file is not used or shipped.
- Built-in Django User is retained, with a Profile for phone. GENERAL_USER means nonstaff; ADMIN means active staff; SUPER_ADMIN means superuser. Active staff can operate all leads; superusers manage accounts/roles. Public registration never grants privileges.
- Enquiries require authentication. Each enquiry creates exactly one Lead in a transaction. Optional Idempotency-Key is scoped to a user; matching retries return 200, new submissions return 201, conflicting payloads return 400.
- Lead statuses: NEW, CONTACTED, FOLLOW_UP, QUALIFIED, CONVERTED, NOT_CONVERTED. Terminal statuses cannot be reopened in version 1. NEW can become CONTACTED or NOT_CONVERTED. CONTACTED/FOLLOW_UP/QUALIFIED can progress through the documented operational states or close. See business/operations.py for the complete transition table.
- Services/categories are archived on DELETE, preserving enquiry relationships. Public catalogues hide archived items and inactive categories.
- One wishlist and one review per user/service. Reviews require moderation; edited reviews become unapproved. Users cannot approve their own reviews.
- In-app notifications are transactional. A scheduled management command creates due reminders idempotently. Recovery email uses console email locally; SMTP is configurable. A production scheduler and real inbox delivery are deployment responsibilities.
- Audit-sensitive models in Django Admin are read-only. Staff update leads through the operational API/simple workspace so status/assignment history and notifications cannot be bypassed. Catalogues/SEO are editable in Admin with assigned Django permissions.
- Prices/budgets are INR in this demonstration. Follow-up times use ISO 8601 with timezone; storage is UTC.
- Conversion rate is converted / closed leads; date filtering uses lead creation dates. This is cohort reporting, not outcome-date revenue reporting. Website traffic totals cannot be inferred from enquiry counts.
- Logout blacklists the supplied refresh token; issued access JWTs expire after 30 minutes. Password changes/reset invalidate existing JWTs. Profile email and privilege changes are not editable by general users.
- Simple frontend tokens stay in memory, requiring sign-in after reload. Browser engagement fields are session estimates, not independently verified analytics.
- Pagination: 20 records per page for business lists. Related services return at most five; per-lead history/follow-up/prediction actions return arrays. Legacy super-admin user list remains unpaginated for compatibility.
- ML model is a demonstration Logistic Regression model trained on X Education. Four genuine dataset inputs are used. No invented service/budget features are supplied. Prediction requests return is_demo=true.
- Demonstration band thresholds: HIGH >= 0.7, MEDIUM >= 0.4, LOW otherwise. Both thresholds are environment-configurable and are not approved production calibration.
- The raw Kaggle dataset is kept locally and excluded from public repositories/ZIP distribution. The downloader, source attribution, model metrics and training code are supplied. Dataset redistribution rights were not established from its generic Other license label.

Deployment still requires approved origins, SMTP, TLS hosting, media storage, database backup/least-privilege roles, reminder scheduling, and real-domain model evaluation. This version is a working development handoff, not a deployed production service.

## Employee admin access

Only users can sign up. Company admin accounts and credential recovery are managed by the superuser, with temporary passwords that must be replaced before requirement access. See `docs/ROLE_PORTALS.md` (or `ROLE_PORTALS.md` from this docs folder) for the current API and PostgreSQL relationships. Public admin signup, token-based admin reset and old admin-registration approval routes have been retired. Apply migrations before running this version.
