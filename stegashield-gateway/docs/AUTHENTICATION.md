# Authentication checkpoint

Run from the outer workspace with its `.env` and virtual environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The backend reads these settings from `.env` or environment variables:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_JWT_ISSUER=https://YOUR_PROJECT_REF.supabase.co/auth/v1
```

The issuer defaults to the configured project URL plus `/auth/v1` if omitted.
Keep actual credentials out of `.env.example` and source control. The server
secret key is not used for authentication/profile queries: these requests carry
the user's JWT so database RLS remains effective.

Sign in through Supabase Auth to obtain a user **access token**. An API key is
not a user access token. In `/docs`, click Authorize and enter the access token.
Then call `GET /api/v1/auth/me` to see the authenticated user ID and database role.
`GET /api/v1/auth/admin-check` returns 403 for ordinary users.

JWT verification uses the configured project's JWKS endpoint, accepts ES256 and
RS256 only, and checks signature, issuer, audience, expiry, issued-at, UUID subject,
and the Supabase `authenticated` role. Anonymous accounts are rejected. Application
roles come from `profiles`, never `user_metadata`. Legacy HS256 projects require
a separately implemented verification path or migration to asymmetric signing
keys; there is deliberately no unverified-token fallback.

The proof-of-concept routes now return 410. Their replacements implement document
downloads and audited forensic lookup using private original-document storage.
See `docs/DOCX_WORKFLOW.md` for setup and validation. Frontend and PDF remain gated
on successful authenticated DOCX and forensic tests.

Python authentication tests use locally generated signing keys and mocked profile
responses; they do not log into or mutate a hosted project. Real PostgreSQL policy
tests are available under `supabase/tests` and are run separately with
`npx supabase test db`. The Phase 1 SQL text tests alone do not prove RLS behavior.
