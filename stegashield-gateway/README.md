# StegaShield Gateway

StegaShield is a forensic document-download gateway. Every authorized download
receives a unique, signed, invisible watermark token. If a copy is leaked, an
administrator can extract that token and resolve it to the original download
event without embedding personal data in the document.

For complete installation on a new Windows computer, including Supabase,
environment variables, tests, startup commands, and troubleshooting, see the
[fresh desktop setup guide](../FRESH_DESKTOP_SETUP.md).

## Delivery scope

- Phase 1: DOCX watermarking and extraction
- Phase 2: authenticated download and audit API
- Phase 3: React user and administrator portals
- Phase 4: PDF watermarking and extraction
- Phase 5: evaluation, deployment and dissertation evidence

## Repository structure

```text
stegashield/
├── backend/       FastAPI API and watermarking engine
├── frontend/      React application (added in the UI phase)
├── docs/          Architecture, requirements and evaluation material
└── tests/         Automated backend tests
```

## Important design rule

The embedded value is a random **per-download token**, not a reusable login
session identifier. The database links this anonymous token to the user,
document, session, IP address and timestamp.

## Run the authenticated DOCX backend

Run these commands from the outer workspace directory containing `requirements.txt`
and `.env`, not from inside `backend`. Keep an existing `.env` when upgrading.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
pytest
uvicorn backend.app.main:app --reload
```

For anything beyond local testing, replace `WATERMARK_SECRET` in `.env` with a
random value. In PowerShell you can generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `http://127.0.0.1:8000/docs` to use the interactive API documentation.

See [the DOCX workflow guide](docs/DOCX_WORKFLOW.md) for the new database migration,
Supabase settings, upload/permission/download endpoints, and audited forensic lookup.
The old proof-of-concept watermark endpoints are retired. A match requires both
a valid per-download signature and the exact protected file's stored SHA-256;
edited or re-saved files are currently inconclusive.

The starter intentionally completes DOCX first. PDF uses the same adapter
contract and remains gated on the DOCX workflow; unsupported PDF requests fail
explicitly rather than returning a damaged file.
