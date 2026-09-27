STEGASHIELD GATEWAY — CHANGES FROM THE ORIGINAL PROPOSAL
Group 60 | Comparison prepared: 08 September 2026

PURPOSE AND SOURCES
===================
This document explains what was added, changed or specified more precisely during
development compared with ISP_Project_Proposal .pdf (August 2026). It also refers
to PROGRESS_REPORT.md and StegaShield_Group60_Progress_Report.pdf, particularly
Sections 2, 4–10 and 11, and the current dependency manifests and implementation.

This is a change inventory, not a claim that every proposal requirement is complete.
"Added" means not explicitly specified in the proposal. "Refined" means the
proposal already contained the general capability, but implementation introduced
the particular mechanism. Implemented locally does not prove deployed configuration.

1. WHAT HAS NOT CHANGED
======================
The main project purpose remains post-download attribution of digitally shared
documents through an authenticated browser gateway. The following were already
in the proposal and should NOT be presented as entirely new additions:

- React, Vite and Tailwind CSS frontend.
- Python/FastAPI backend.
- Supabase Auth, PostgreSQL, Row-Level Security and Supabase Storage.
- Anonymous identifiers rather than raw personal data inside the watermark.
- On-demand marking, in-memory protected copies and unchanged stored originals.
- Administrator-restricted forensic extraction and server-side identity mapping.
- Audit records associating documents, users, sessions and download events.
- Inconclusive outcomes when a valid identifier cannot be recovered.
- Evaluation of invisibility, extraction, robustness, performance and security.

The changes below extend or refine that foundation.

2. MAJOR DESIGN CHANGES
=======================

2.1 Signed per-download token instead of embedding the login Session ID
Proposal: Sections 2.2, 3.1 and 3.8 describe creating a Session ID at login and
embedding that Session ID into documents downloaded during the session.

Implementation:
- Every protected download receives a fresh random UUID.
- That token identifies one issued copy, not every file in a login session.
- The server records its user, document, timestamp and protected-file hash.
- A verified Supabase authentication session_id is linked when present.
- The embedded token is authenticated with a truncated HMAC-SHA256 tag.

Reason: several downloads in one login session remain distinguishable. The HMAC
also permits detection of altered or fabricated token frames without embedding
names, email addresses or IP addresses.

Qualification: this is a proposal refinement requiring clear terminology and
supervisor acknowledgement. It is a symmetric authentication tag, not encryption
or a public-key PDF digital signature. Do not weaken the signed per-download design.

2.2 Exact protected-file hash required for a positive forensic match
Proposal: recovering the Session ID and resolving its audit record is the main
described attribution mechanism.

Implementation adds two necessary checks:
1. Recover a valid signed token registered to an issued download.
2. Verify that the suspect file's SHA-256 equals that issued copy's stored hash.

Reason: a signed token can be copied into an unrelated file. A valid signature
alone authenticates the identifier, not all surrounding document content.

Tradeoff: an edited or re-saved file may retain a valid token but still be
inconclusive. The report must distinguish token-recovery success from positive
attribution success. A match identifies an issued copy/account record, not proof
of which human disclosed it or their intent.

2.3 DOCX-first implementation and separate PDF carrier
Proposal: selected text-based formats, with pikepdf and a custom zero-width encoder
listed in the technology table; PDF is already discussed in the proposal.

Implementation:
- DOCX was implemented and tested first using python-docx.
- DOCX embeds repeated zero-width frames in document text.
- PDF uses pypdf instead of pikepdf.
- PDF places the same signed frame in a non-rendering /StegaShield marked-content
  point (DP) in page content; it does not depend on invisible rendered PDF glyphs.
- Markers are repeated across up to five suitable locations/pages.
- PDF support is opt-in through PDF_ENABLED; the code default is false.
- Static PDF validation rejects encrypted and selected interactive, script-bearing,
  attached-file or digitally signed structures.

Qualification: PDF itself is not a wholly new project idea. The library choice,
carrier, implementation sequence and opt-in gate are the changes. PDF remains
experimental pending broader compatibility/resource evaluation.

2.4 More specific session behaviour
Proposal: a new Session ID and audit association are created for every login.
Implementation: Supabase manages authentication sessions; the API validates the
session_id claim if supplied. Local application session rows are registered during
download recording, not every login, and a missing session_id is currently allowed.

This is a remaining alignment gap, not an implemented improvement. Decide whether
session claims must become mandatory and whether login-time session auditing is
required. The watermark token must remain separate from the login session ID.

3. ADDITIONAL USER-FACING FEATURES
=================================

3.1 Individual document permissions
- Administrators can select a member and grant or revoke document access.
- Permission expiry is supported by the schema and access checks; the current
  grant UI does not expose a general expiry editor.
- Members see permitted documents rather than an unrestricted shared catalogue.
The proposal required authenticated access, but did not explicitly specify this
per-document grant management workflow.

3.2 Dynamic job-position access
- Administrators can create job positions, such as Manager or Analyst.
- Administrators assign each member one current position or remove the assignment.
- Documents can be granted to a whole position.
- Current members and future assignments inherit that position's document grants.
- Changing a member's position affects future access across all affected documents.
- Members cannot assign themselves a position.
- Individual and position grants are independent OR conditions: revoking one does
  not remove access supplied by the other.
- Existing administrators retain access to active documents.
- Already issued copies cannot be recalled by revoking future access.

3.3 Refresh-safe login
- The initial implementation used memory-only sessions and logged out on refresh.
- The current portal uses Supabase session persistence with browser sessionStorage.
- Refresh in the same tab restores the session and verifies the application role.
- Explicit sign-out clears the local session; automatic token refresh is enabled.
- This is tab-scoped persistence, not a permanent "remember me" feature.
- It is not HttpOnly-cookie storage and remains subject to same-origin XSS risks.

3.4 Protected document preview
- Members/admins can open a document preview from the library.
- Preview invokes the authenticated protected-download endpoint.
- It issues and records a signed protected copy before showing bytes.
- Saving from that dialog saves the same copy; a separate Download issues another.
- DOCX is rendered using docx-preview in a sandboxed iframe with scripts disabled,
  HTML alt-chunks disabled and a restrictive Content Security Policy.
- PDF uses the browser PDF viewer and an in-memory object URL.
- Object URLs are revoked on preview closure.
- No public original links or third-party document-viewing service is introduced.
- DOCX layout may differ from Word; browser PDF rendering support can vary.
- Screenshots and copied preview text do not carry the exact-file attribution guarantee.

3.5 Portal usability and visual refinements
- Member/admin navigation based on the server-verified application role.
- Searchable document library, format badges and download preparation states.
- Original-upload forms with inline file validation and explicit failure messages.
- Separate individual and job-position access sections.
- Controls to create positions and manage assignments.
- Protected-preview modal, save-copy action and explanatory warnings.
- Clear matched/inconclusive forensic result panels.
- Recent forensic audit trail with started/completed status.
- Responsive layout, focus styles, improved spacing, panels and visual hierarchy.
- Browser-tested desktop and mobile scenarios.

These refine the proposed library/admin portal rather than replacing its purpose.
Lists are bounded, not fully paginated: typically 100 documents/users/positions,
1,000 memberships and 50 forensic audit entries.

4. ADDITIONAL SECURITY AND RELIABILITY MECHANISMS
================================================

4.1 Detailed JWT validation
- ES256/RS256 algorithm allowlist and signing-key lookup through JWKS.
- Verification of signature, configured issuer, audience and required claims.
- Rejection of anonymous users and malformed identity/session UUIDs.
- Application user/admin role resolved from trusted database profiles.
- Client request bodies or user-editable metadata cannot choose the acting role.
These operationalise the proposal's secure authentication requirement.

4.2 Transactional record-before-release workflow
- API checks access before retrieving an original.
- A server-only record_download database function repeats permission checks.
- It checks active document, individual/position grants and session ownership/state.
- Relevant rows are locked during the recording transaction.
- Only a valid recorded event ID permits a protected-file response.
- Failed or unacknowledged database recording does not return protected bytes.
This gives precise failure semantics beyond the proposal's general logging requirement.

4.3 Original integrity and storage protection
- Original size and SHA-256 are stored and checked before download generation.
- Object paths are server-generated as document UUID/original.docx or original.pdf.
- Storage writes disable upsert to avoid silent replacement.
- Immutable-original metadata triggers prevent changes to protected source fields.
- A restrictive Storage policy blocks client access to the originals bucket even
  if unrelated permissive policies exist elsewhere.
- Secret/service credentials remain server-side; caller JWTs scope metadata queries.

4.4 More detailed watermark validation
- SS1 payload marker, explicit frame delimiters and four zero-width symbols.
- Two bits encoded per symbol.
- 16-byte UUID and 16-byte truncated HMAC-SHA256 tag.
- Constant-time signature comparison.
- Repeated frames for recoverability within supported document structures.
- No guessed attribution when valid tokens conflict.
- Already watermarked originals rejected to prevent ambiguous source material.

4.5 File parsing boundaries
- Non-empty uploads, supported extension and size validation.
- Browser MIME declarations are not treated as proof of a valid format.
- DOCX package validation, archive-entry/expansion limits and rejection of selected
  encrypted or macro-bearing packages.
- PDF input/output, page-count, object traversal and page-content complexity limits.
- Generic client-facing storage/database errors rather than raw upstream internals.
These are not a complete malware scanner or hard operating-system resource sandbox.

4.6 Expanded forensic audit and failure handling
- An attempt-started record is appended before suspect parsing.
- A completed record includes outcome, reason and a shared attempt_id.
- A lookup interruption can leave an observable unfinished attempt.
- Audit failure blocks disclosure of a forensic result.
- Suspect bytes are not intentionally retained as uploaded evidence files.
- Download and forensic event records have append-only mutation protections.
- Database constraints link matched download IDs to the corresponding tokens.
These refine the original audit concept. They do not prevent database-superuser
tampering or provide external notarisation of evidence.

4.7 Browser/API hygiene
- Cache-Control: no-store on sensitive responses/configuration.
- No watermark-token response header exposed to download clients.
- Safe generated download filenames and nosniff headers.
- Frontend session identity checked before and after requests to discard responses
  belonging to a changed session.
- Unsafe POST requests are not automatically retried after network failures.
- Backend supplies an allowlisted public configuration response; no frontend .env
  containing service or watermark secrets is required.

5. DATABASE EXTENSIONS AND NEW IMPLEMENTATION FIELDS
===================================================
The proposal already described sessions, documents and download_events and audit
lookups. The implementation made the schema more explicit and added:

- profiles: application role and display name linked to Supabase auth users.
- document_permissions: individual document grants, grantor and optional expiry.
- job_positions: admin-managed position catalogue.
- position_memberships: trusted user-to-position assignment.
- document_position_permissions: document-to-position grants.
- forensic_events: explicit investigation attempts and outcomes.
- documents: original SHA-256, size, MIME type, private path and archive timestamp.
- download_events: per-download watermark_token and protected_sha256.
- forensic_events: attempt_id, completed, reason, valid_copies, matched event/token.
- Functions/triggers for trusted recording, admin checks, position access,
  original immutability and append-only event protection.

Important nuance: current RLS lets members read their own profile/session rows.
Token-to-download mappings and forensic records are administrator-only. This is
more specific than blanket "all identity data is administrator-only" wording.

Migrations implementing these stages:
  20260904000100_initial_security_schema.sql
  20260905000100_download_workflow.sql
  20260906000100_pdf_workflow.sql
  20260906000200_position_access.sql

6. TECHNOLOGIES AND TOOLS ADDED OR MADE EXPLICIT
===============================================
These tools were not explicitly listed in the original proposal's technology
table, or are replacements for its listed tools. Versions below are declarations
from requirements.txt/package.json, not a claim that every machine has identical
installed versions. Frontend ^ ranges resolve through package-lock.json.

BACKEND / RUNTIME
- Uvicorn [standard] 0.35.0: ASGI server for FastAPI and development reload.
- python-multipart 0.0.20: multipart document-upload parsing.
- python-docx 1.2.0: DOCX package/text manipulation and watermark carrier.
- pypdf 6.17.0: PDF parsing/writing; replaces the proposed pikepdf choice.
- PyJWT [crypto] 2.10.1: JWT signature/claim and JWKS verification.
- httpx 0.28.1: scoped Supabase HTTP transport and mockable integration testing.
- pydantic-settings 2.10.1: typed environment configuration and validation.
- python-dotenv 1.1.1: environment-file support in the dependency stack.
- Python standard-library uuid, hmac and hashlib: random token generation,
  HMAC-SHA256 authentication and SHA-256 file integrity. These are not separate
  commercial services or newly invented cryptographic algorithms.

FRONTEND / PREVIEW
- TypeScript (^5.8.0 development dependency): typed components/API models.
- @supabase/supabase-js (^2.49.0): browser login, refresh and session handling.
- docx-preview (^0.4.0): local browser DOCX preview rendering.
- React DOM (^19.0.0): browser mounting/rendering companion to the proposed React.
- @vitejs/plugin-react and @tailwindcss/vite: integration/build plugins.
- Browser sessionStorage, Blob/object URLs, iframe sandbox, CSP and native dialog:
  concrete platform mechanisms, not additional hosted products.
- Node.js/npm and package-lock.json: frontend tooling and reproducible dependencies.

TESTING / QUALITY ASSURANCE
- pytest 8.4.1: backend unit/API/security tests.
- pytest-cov 6.2.1: coverage tooling dependency; no coverage percentage is claimed.
- FastAPI/Starlette TestClient and httpx MockTransport: API/upstream test fixtures.
- pypdfium2 5.13.0: independent PDF rendering for pixel-comparison tests.
- pgTAP: executable PostgreSQL/RLS and trusted-RPC tests.
- Vitest (^3.2.0): frontend unit/component test runner.
- React Testing Library (^16.2.0), jest-dom (^6.6.0), jsdom (^26.0.0): component
  interaction, DOM assertions and test environment.
- Playwright (^1.51.0) with Microsoft Edge: browser workflow tests and screenshots.
- npm audit: dependency advisory checking; a clean run is not proof of security.
- Supabase CLI and Docker Desktop: local migration and database-policy verification.
  Docker is not required for normal operation against hosted Supabase.
- JSZip is used by the DOCX preview dependency chain and browser test fixtures;
  it is not a newly designed watermark algorithm.

DOCUMENTATION / DEVELOPMENT SUPPORT
- python-docx also generates the editable assessment report.
- Pillow renders the report's high-resolution diagrams and test-count chart.
  Pillow was already mentioned in the proposal, but it is NOT being used here
  to implement the proposed DCT visual watermarking. Its observed use is reporting.
- Playwright/Edge exports the report HTML to PDF.
- pypdf/pypdfium2 support PDF text review and visual document-quality checks.
- Markdown, HTML/CSS, Word and PDF artefacts, plus a ChatGPT handoff README.
- VS Code, PowerShell and Python virtual environments support local development;
  VS Code was already mentioned in the proposal's budget/tooling context.
- AI-assisted development/report preparation has been used in this workspace;
  disclose it according to institutional rules and verify personal contributions.
  ChatGPT is not a runtime service used by the StegaShield application.

7. PROPOSED TOOLS THAT ARE NOT IMPLEMENTED AS APPLICATION FEATURES
=================================================================
- pikepdf: replaced by pypdf in the current PDF adapter.
- OpenCV/NumPy DCT watermarking: no such application pipeline is implemented.
- Tesseract/pytesseract photo recovery: not implemented.
- Pillow-based visual watermarking: not implemented; documentation rendering use
  must not be presented as that research feature.

The proposal is internally inconsistent here: its abstract and Section 1.4 exclude
physical, printed and photographed copies, but Section 3.3 lists visual stego/OCR.
Supervisor clarification is required. OCR cannot recover zero-width characters
that are absent from the rendered pixels. Do not claim photo/print support.

8. ADDITIONAL VERIFICATION AND DOCUMENTATION DELIVERABLES
=======================================================
The following concrete artefacts go beyond the proposal's high-level testing plan:
- Automated signed-token tampering, unknown-token and conflict tests.
- Unique-copy and exact-hash forensic workflow tests.
- Failure checks for denied access, storage integrity and unacknowledged events.
- Local SQL tests for RLS, session ownership, immutable records, private originals
  and dynamic position membership.
- Independent 144-DPI PDF pixel comparisons for generated text/image/rotation/
  crop fixtures; this is not universal visual validation of all documents.
- Browser tests for role navigation, uploads, refresh/sign-out, position grants,
  protected DOCX preview and mobile layout.
- Setup/security documentation: AUTHENTICATION.md, DOCX_WORKFLOW.md,
  PDF_VALIDATION.md and WORKSPACE_UPGRADES.md.
- CODEX_CONTINUATION.md describing development gates and fixed design decisions.
- A 27-page progress report, editable Word/HTML/Markdown, six figures, and a
  handoff prompt explaining completed work and remaining requirements.

Recorded checkpoint: 136 backend tests, 70 local database tests, 12 frontend tests,
seven browser scenarios, and successful frontend build. The progress report
records when these were run. This comparison did not rerun those suites.
Counts are not research accuracy, line coverage, production certification or
the percentage of the project completed. Browser fixtures are not hosted proof.

9. REMAINING DIFFERENCES — NOT COMPLETED ADDITIONS
================================================
- The forensic result currently shows download ID, user ID, document ID and time,
  but not the session ID/IP fields requested in the proposal. Those need an
  administrator-only implementation with disclosure tests.
- Mandatory session claims and login-time session auditing are unresolved.
- The proposed controlled 30–50-document study and eight research metrics are
  not complete. Distinguish transformation token survival from exact attribution.
- Broader real DOCX/PDF compatibility and performance evidence is still needed.
- Production resource-isolated parsing, rate limits, trusted proxy/IP handling,
  historical signing-key rotation and backup/restore evidence remain.
- Grant and membership changes do not yet have dedicated append-only audit history.
- Self-registration/password recovery UI and full pagination are not implemented.
- Accessibility and cross-browser evaluation are not complete certifications.
- Proposal-change approval, reference verification and truthful individual
  logbooks are required before describing the project as finalised.

10. SUGGESTED WORDING FOR THE ASSESSMENT
=======================================
"During development, StegaShield was refined from a login-session watermarking
concept into a session-linked, signed per-download attribution gateway. We added
individual and dynamic job-position access, refresh-safe browser sessions,
recorded protected-copy previews, transactional record-before-release checks,
original and protected-file integrity checks, and detailed forensic attempt
auditing. The implementation uses python-docx for DOCX and pypdf for an
experimental non-rendering PDF carrier. These additions improve copy-level
traceability and operational control while retaining private server-side identity
mapping. Exact-file attribution, limited transformation robustness, unresolved
session semantics and unfinished research evaluation remain explicit limitations."

11. WHERE TO FIND IMPLEMENTATION EVIDENCE
========================================
Paths below are relative to stegashield-gateway:
- backend/app/watermarking/codec.py: signed payload and symbol encoding.
- backend/app/watermarking/docx_adapter.py and pdf_adapter.py: format carriers.
- backend/app/core/auth.py: JWT validation and principal/session handling.
- backend/app/core/config.py: settings and PDF feature flag.
- backend/app/services/gateway.py: scoped transport, original validation paths,
  permissions and trusted event recording.
- backend/app/api/v1/documents.py: upload/download and forensic workflow.
- backend/app/api/v1/positions.py: position/membership/grant endpoints.
- supabase/migrations/: schema, security and feature changes.
- supabase/tests/: executable database/security cases.
- frontend/src/App.tsx: portal, authentication persistence and workflows.
- frontend/src/PositionAccess.tsx: position grants and assignments.
- frontend/src/DocumentPreview.tsx: recorded-copy preview and renderer isolation.
- frontend/src/api.ts: authenticated requests and session-change checks.
- frontend/src/workspace-upgrades.css: preview/access styling refinements.
- tests/, frontend/src/*.test.*, frontend/e2e/: verification evidence.
- docs/assessment/PROGRESS_REPORT.md: proposal alignment, limitations and plan.

No application code, credentials or hosted configuration was changed to prepare
this comparison. This readme is an evidence-based documentation supplement, not
approval to change the original academic scope.
