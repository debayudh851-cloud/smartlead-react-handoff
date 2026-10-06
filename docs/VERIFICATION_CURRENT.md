# Current verification

Verified locally on 6 October 2026 with Python 3.13, PostgreSQL 18 and requirements.txt.

- PostgreSQL connection verified; smartlead database created if absent.
- Built-in, business and JWT blacklist migrations applied successfully.
- Django check: no issues. Migration consistency check: no model changes detected.
- Full PostgreSQL regression run: 34 tests passed in 47.888 seconds against a temporary database.
- Coverage: authentication/recovery, permission boundaries, enquiry/lead transaction rollback, idempotent retries, lead transitions/assignment/history, wishlist/review ownership/moderation, profile privilege protection, logout/password-change revocation, reminder idempotency, unavailable prediction handling and prediction storage.
- OpenAPI generated and validated with no generation warnings/errors after annotations were added.
- pip check: no broken requirements. Frontend JavaScript syntax checked with Node.
- Browser public catalogue and service detail inspected. A full role-specific real-browser acceptance suite is not claimed.
- Kaggle demonstration model: 7,392 training rows and 1,848 holdout rows. ROC-AUC 0.80002955, average precision 0.71624171, Brier score 0.17183360, accuracy at .5 threshold 0.75757576.
- Actual trained artifact inference and PostgreSQL prediction persistence verified in a transaction that rolled back all smoke-test records.

Postman files are prepared, not proof of manual execution. SMTP inbox delivery, separate React integration, production hosting and real-domain ML performance remain unverified. Reminder scheduling is a deployment responsibility.

Source PDF and historical planning documents are retained; older test counts/layouts do not override this release record.
