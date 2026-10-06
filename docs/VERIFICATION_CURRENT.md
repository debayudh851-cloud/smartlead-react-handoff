# Current verification

Verified locally on 6 October 2026 with Python 3.13, PostgreSQL 18 and requirements.txt.

- PostgreSQL connection verified; smartlead database created if absent.
- Built-in, business and JWT blacklist migrations applied successfully.
- Django check: no issues. Migration consistency check: no model changes detected.
- Full PostgreSQL regression run: 39 tests passed in 87.165 seconds against a temporary database.
- Coverage: authentication/recovery, permission boundaries, enquiry/lead transaction rollback, idempotent retries, lead transitions/assignment/history, wishlist/review ownership/moderation, profile privilege protection, logout/password-change revocation, reminder idempotency, unavailable prediction handling and prediction storage.
- OpenAPI generated and validated with no generation warnings/errors after annotations were added.
- pip check: no broken requirements. Frontend JavaScript syntax checked with Node.
- Browser public catalogue and service detail inspected. A full role-specific real-browser acceptance suite is not claimed.
- Kaggle demonstration model: 7,392 training rows and 1,848 holdout rows. ROC-AUC 0.80002955, average precision 0.71624171, Brier score 0.17183360, accuracy at .5 threshold 0.75757576.
- Actual trained artifact inference and PostgreSQL prediction persistence verified in a transaction that rolled back all smoke-test records.

Postman files are prepared, not proof of manual execution. SMTP inbox delivery, separate React integration, production hosting and real-domain ML performance remain unverified. Reminder scheduling is a deployment responsibility.

Source PDF and historical planning documents are retained; older test counts/layouts do not override this release record.

## Three-interface update

Migration business.0002_adminregistration applied to local PostgreSQL. Role-specific login tests cover all nine user/admin/superuser combinations, public registration privilege injection, pending/approved/rejected admin applications, account filters, superuser-only decisions, approved admin requirement access and self-deactivation protection. Three signed-out portal pages inspected in the browser. Authenticated workflows were verified by API tests; no real user credentials were created for browser testing.


## Employee access release

Public admin registration and token-based admin reset retired. Employee provisioning and recovery tables migrated in PostgreSQL. Regression coverage verifies superuser-only provisioning/reset, hashed random credentials, temporary-password access blocking, password replacement and token revocation, duplicate recovery suppression, rejected/already-reviewed requests, retired routes, ordinary-user recovery and existing lead workflows. Browser inspected signed-out admin and superuser portals. Employee identity verification and private credential handoff remain the company superuser responsibility.
