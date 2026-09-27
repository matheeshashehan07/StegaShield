# StegaShield portal

React, TypeScript, Vite, and Tailwind user/admin interface for the existing DOCX gateway.

## Run locally

Keep the backend running from the outer workspace (the folder containing `.env`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

In a second terminal:

```powershell
cd stegashield-gateway/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` and sign in with a Supabase test user's email/password.
No frontend environment file is necessary: `/api/v1/auth/config` supplies only
the project's URL and publishable key. Vite proxies `/api` to port 8000.
Never copy the backend `.env` or its server/watermark secrets into this folder.

Apply the backend's `20260905000100_download_workflow.sql` migration to the hosted
development project before trying uploads/downloads there. See
`../docs/DOCX_WORKFLOW.md` for the full setup.

## Available workflows

- View profile: use the sidebar button to view your own user ID, display name,
  email, application role and profile creation date. Edit profile allows only
  display-name and profile-picture changes. The sidebar refreshes after saving;
  member/position selection lists read the updated display names from profiles.
  `/api/v1/auth/profile` uses the authenticated principal and caller RLS context;
  it does not accept a target account ID or expose tokens. Apply
  `20260909000100_profile_editing.sql` before using edits or pictures.

- Members: sign in, search permitted documents, download protected copies, sign out.
- Administrators: upload original DOCX files, select recipients from existing
  profiles, grant/revoke access, perform forensic lookups, and review recent audit entries.
- Matching requires a signed registered token and the exact returned file hash.
  Edited or re-saved files are inconclusive and display no user mapping.
- Login tokens use tab-scoped sessionStorage with automatic refresh; reloading
  keeps the session. Explicit sign-out clears it. Role decisions still come from
  the backend's `/auth/me`, not browser metadata. Always sign out on shared devices.
- Document lists show at most 100 records and the audit trail the latest 50 entries.
  Account creation/password recovery are not included. PDF is opt-in via the backend.
- Document Access supports individual and job-position grants; administrators can
  create positions and assign members there. Apply `20260906000200_position_access.sql`.
- Previews issue a protected download through the same authenticated endpoint.
  DOCX renders in an isolated frame; PDF uses the browser viewer. Neither uses
  public original links or third-party document services.

## Verify

```powershell
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Alternatively, use an installed Microsoft Edge for browser tests in PowerShell:

```powershell
$env:PLAYWRIGHT_CHANNEL = 'msedge'
npm run test:e2e
```

Latest verification: 11 frontend unit tests, 3 headless Edge browser tests, and
the production build pass. The backend suite passes 79 tests. These browser tests
use HTTP fixtures; hosted account/file verification is a separate manual check.

Browser tests run the real UI with explicit mocked HTTP fixtures. They cover
admin workflows, member-only navigation, downloads, logout, result clearing, and
mobile layout. They do not substitute for signing into your hosted project and
testing actual DOCX files. Backend Python/pgTAP suites test JWTs, files and RLS.

## Deployment

`npm run build` produces `dist/`. A production web server must serve it and proxy
`/api` to FastAPI over HTTPS. Vite's proxy only handles local development/preview.
Apply appropriate response security headers and request-body limits at that proxy.
The Supabase endpoint must remain reachable from the browser for authentication.
