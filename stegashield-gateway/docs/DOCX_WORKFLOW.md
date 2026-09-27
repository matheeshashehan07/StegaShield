# Authenticated DOCX workflow

## Setup

Run the API from the outer workspace so it reads the existing root `.env`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

The gateway uses `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
`SUPABASE_SECRET_KEY`, `SUPABASE_JWT_ISSUER`, and `WATERMARK_SECRET`.
The server key is used only for private originals and append-only audit writes.
User metadata and permission queries retain the caller's JWT and database RLS.
Real secrets belong in `.env`; example files contain placeholders.

Apply the new migration to your linked development project from
`stegashield-gateway` after reviewing the dry run:

```powershell
npx supabase db push --dry-run
npx supabase db push
```

`20260905000100_download_workflow.sql` creates the private
`stegashield-originals` bucket, the permission-checking download RPC, immutable
audit records, protected-file hashes, and forensic attempt tracking.
Do not create a public bucket or add client access policies for originals.
This development work does not automatically apply migrations to your hosted project.

## Try it in Swagger

1. Open `http://127.0.0.1:8000/docs` and authorize using an admin access token.
2. Call `POST /api/v1/documents` with a title and an original DOCX containing text.
   Save the returned document `id`. File metadata is derived server-side;
   originals already containing watermark frames are rejected.
3. Call `POST /api/v1/documents/{document_id}/permissions` with the document ID
   and `{"user_id": "NORMAL_USER_UUID"}`. The admin selects the recipient;
   download callers cannot supply their identity or watermark token.
4. Authorize with that normal user's access token. `GET /api/v1/documents`
   lists up to 100 allowed active DOCX documents.
5. Execute `POST /api/v1/documents/{document_id}/download` and save the returned file.
   Repeat to produce a different protected copy and a new database event.
6. Authorize as admin again and upload that protected file to
   `POST /api/v1/forensics/docx`. Expect `matched`, `exact_copy: true`, and the
   recorded user/document/event identifiers.
7. An original, edited copy, forged watermark, unknown token, or file containing
   conflicting valid tokens must produce `inconclusive`, without a user mapping.
8. As admin, revoke access using
   `DELETE /api/v1/documents/{document_id}/permissions/{user_id}`.
   That user's subsequent downloads should return 404.

The old `/watermarks/docx/embed` and `/watermarks/docx/extract` endpoints now return
410 for admins. They cannot produce untracked protected copies or unaudited results.
The DOCX round-trip tests now cover the replacement endpoints; the codec's existing
signature tests remain unchanged.

## Security and interpretation

- Authorization is checked in the API and again inside the server-only database
  RPC immediately before the event is inserted. Expired/revoked permissions,
  archived documents, and mismatched sessions are rejected. Auth session UUIDs
  come from verified JWT claims; application sessions begin at first recorded download.
- Protected copies are generated in memory. A confirmed database event ID must
  arrive before any response bytes are returned. A timeout can leave an unused
  event, but cannot release an unrecorded file. An event means a copy was issued
  for response, not that the network transfer completed or the user read it.
- Every authorized forensic attempt first appends a start audit row and then a
  completion row with the same `attempt_id`. A crash or dependency outage can
  leave only the start row. Suspect bytes, login tokens, and watermark signatures
  are not persisted. Invalid uploads are audited; authentication denials do not
  start a forensic operation.
- A signature authenticates a token; it does not bind that token to arbitrary
  surrounding content. This phase also requires the exact protected-file SHA-256
  to match before returning an identity mapping. Even harmless re-saving in Word
  may therefore yield inconclusive. This conservative rule prevents copied tokens
  from attributing a different document. The signed per-download token format is
  unchanged. Partial-copy/content-normalization attribution needs separate design
  and evaluation before it can safely return identities.
- A match identifies a previously issued copy, not proof of who leaked it.
  Screenshots and photographed pages remain unsupported.
- Uploading storage bytes and inserting metadata span separate services. If the
  metadata request fails or times out, an inaccessible orphan object may remain.
  It cannot appear in downloads without a catalogue record. No automatic deletion
  runs after an ambiguous commit; cleanup requires checking both services first.
- File extension, actual DOCX package, expanded ZIP size, stored size, and original
  SHA-256 are checked. The client MIME header is ignored. This is not a malware
  scanner. Limits after multipart parsing do not replace a deployment request-body
  limit. Configure that limit at the reverse proxy and keep Uvicorn's trusted
  proxy settings restricted; the app does not parse forwarded IP headers itself.

## Verification

From the outer workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

To run real PostgreSQL/RLS tests, start Docker and run from `stegashield-gateway`:

```powershell
npx supabase db start
npx supabase test db
```

The pgTAP suite in `supabase/tests/workflow_rls.test.sql` creates disposable
fixtures inside a rolled-back transaction. It checks multiple users, role
escalation, denied RPC calls, expired permissions, archive enforcement, immutable
audit mappings, token uniqueness, and private Storage isolation.

Frontend and PDF remain gated on authenticated DOCX and forensic testing.
