# StegaShield continuation brief for VS Code Codex

Continue developing this repository as a security-sensitive academic project.
Read `README.md`, the existing source, and tests before editing.

## Current checkpoint (2026-09-05)

Authentication, permission-checked DOCX downloads, private original Storage,
and audited forensic lookup are implemented. See `docs/DOCX_WORKFLOW.md` for
migration and manual testing instructions, conservative exact-file attribution,
and failure semantics. Old proof-of-concept endpoints are retired (410).
The new migration must be applied to the hosted development project before use.
Frontend and PDF remain gated on authenticated DOCX and forensic validation.

The DOCX gate passed 72 Python and 30 local PostgreSQL/RLS tests before frontend
development began. The React/TypeScript/Vite/Tailwind portal is now implemented
under `frontend`; see its README for startup, tests and deployment requirements.
It includes member downloads and admin upload/access/forensic/audit screens.
Hosted end-to-end demonstration still requires the migration and real test accounts.
PDF remains disabled pending its separate design and evaluation phase.

PDF adapter checkpoint (2026-09-06): the experimental non-rendering page-content
carrier now passes 33 adapter tests, including independent pixel comparisons;
the complete Python suite passes 112 tests. The signed codec is unchanged.
PDF API/storage/frontend integration is implemented but defaults to disabled.
The opt-in flag is `PDF_ENABLED`; apply the new PDF migration before enabling it.
Python tests pass 125 cases and local pgTAP tests pass 60 cases. See `PDF_VALIDATION.md`
for measured coverage, security limitations, and the next integration gate.

## Fixed decisions

Workspace upgrade checkpoint: refresh-safe tab-scoped sessions, individual plus
dynamic job-position grants, and protected-copy previews are implemented.
See `WORKSPACE_UPGRADES.md` for the new migration and security tradeoffs.

- Final formats: DOCX and PDF.
- DOCX is implemented and tested first.
- Every download gets a new random per-download UUID token.
- The signed anonymous token is embedded; personal data never enters the file.
- Original documents remain unchanged and protected copies are generated in memory.
- A missing or invalid watermark produces an inconclusive result, never guessed attribution.
- Do not claim screenshot or photographed-page support for zero-width watermarks.

## Next implementation order

1. Add Supabase SQL migrations for profiles, sessions, documents, document_permissions,
   download_events, and forensic_events with Row-Level Security.
2. Add Supabase JWT verification to FastAPI and enforce `user`/`admin` roles.
3. Replace the proof-of-concept embed endpoint with an authenticated document-download
   endpoint that creates the download event before returning the protected file.
4. Store original documents in a private Supabase Storage bucket.
5. Build the React + TypeScript + Vite + Tailwind user and admin portals.
6. Design and experimentally validate the PDF adapter. Keep it disabled until it
   passes extraction, invisibility, and corruption tests.
7. Add forensic lookup, audit logs, evaluation scripts, deployment configuration,
   and documentation.

## Security requirements

- Never trust a client-supplied user ID, role, token mapping, filename, or MIME type.
- Never expose the Supabase service-role key to the frontend.
- Verify JWT signature, issuer, audience, expiry, and role server-side.
- Use private storage and short-lived signed URLs only where required.
- Enforce authorization in both the API and database RLS policies.
- Use constant-time signature comparison and a secret of at least 32 random bytes.
- Do not log access tokens, secrets, watermark signatures, or document contents.
- Validate file size, extension, package structure, and supported format.
- Create forensic audit records for extraction attempts without persisting suspect
  documents unless a documented retention policy authorizes it.
- Preserve existing passing tests and add tests for each security boundary.

## Definition of done

The system is complete only when DOCX and PDF downloads can be attributed through
valid database records; ordinary users cannot access forensic data; non-watermarked
or modified files cannot cause false attribution; and the evaluation suite reports
uniqueness, invisibility, extraction, robustness, performance, RLS, attribution,
and false-positive metrics.
