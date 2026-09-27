# Experimental PDF adapter

## Status (2026-09-06)

The adapter and authenticated PDF workflow are implemented. PDF is opt-in through
`PDF_ENABLED=true`; the default is false. The portal reads supported formats from
the backend. The signed codec, private storage policy, and exact-file attribution
checks are unchanged. A new migration extends the bucket MIME allowlist and
download RPC formats without relaxing its permission or session checks.

## Enable for a controlled development demo

1. From `stegashield-gateway`, run `npx supabase db push --dry-run` and confirm the
   linked project and pending migrations, then `npx supabase db push` to apply them.
   The PDF migration is `20260906000100_pdf_workflow.sql`. Local migration/testing
   does not apply it to hosted Supabase.
2. Add `PDF_ENABLED=true` to the outer workspace `.env`; keep existing secrets.
3. Restart FastAPI and reload the portal (sign in again).
4. As admin, upload a static PDF and grant a member access.
5. As the member, download it twice. Open both copies and check their appearance.
6. As admin, submit an unchanged downloaded copy to Forensic lookup. Expect a
   match to that download. The unmarked original must be inconclusive.

The API uses the existing document routes and `POST /api/v1/forensics/pdf`.
Set `PDF_ENABLED=false` and restart to disable PDF again; DOCX stays available.

Run from the outer workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest stegashield-gateway/tests/test_pdf_adapter.py -q
.\.venv\Scripts\python.exe -m pytest stegashield-gateway/tests -q
```

Install the pinned root requirements first. `pypdf` handles PDF structures;
`pypdfium2` is an independent renderer used only by the validation tests.

## Carrier decision

The PDF adapter reuses the unchanged signed per-download UUID codec. It embeds
the encoded frame in a `/StegaShield` marked-content point (`DP`) in page content,
repeated across up to five pages. These points do not paint text or graphics.
See Adobe's [marked-content documentation](https://opensource.adobe.com/dc-acrobat-sdk-docs/library/pdfmark/pdfmark_Basic.html).

This is PDF page-content metadata, not invisible rendered glyphs, encryption, or
a PDF digital signature. No user details are embedded. This differs from the
DOCX carrier while retaining its token and signature design. If the assessment
proposal requires a particular PDF carrier, reconcile it before integration;
the proposal was not available for verification.

## Evidence and limits

- Signed extraction and ten independently generated tokens are tested.
- Independent 144-DPI PDFium render comparisons are pixel-identical for generated
  fixtures containing text, vector shapes, images, rotations, and crop boxes.
  Extracted text and page count also remain unchanged.
- Wrong keys, altered signatures, conflicting tokens, and malformed markers
  cannot return an attribution token. Already marked originals are rejected.
- Corrupt, truncated, encrypted, and selected interactive/script-bearing,
  attached-file, or signed PDF structures are rejected.
- Input/output size, page count, object traversal, expanded page content, and
  content-operation limits constrain accepted documents.

These are generated fixtures, not a representative real-world compatibility
corpus or a malware scan. Expansion and parsing limits are checked in-process;
they are not hard memory/CPU isolation and do not bound every decompressed stream.
Untrusted public PDF processing needs separate worker resource limits before
production exposure. Active-content detection is conservative, not a complete
PDF sanitizer.

Markers may be removed by rewriting, optimization, printing, or screenshots.
A valid token can be transplanted: integration must retain the DOCX workflow's
exact protected-file SHA-256 check and server-side download record before
returning any identity. A match identifies a download record, not proof of who
disclosed a file. No robustness to editing or print/screenshot recovery is claimed.

## Remaining production gate

Evaluate representative real PDFs and record performance/resource behaviour.
Add isolated workers with hard resource limits before accepting arbitrary public
PDFs. Complete the hosted manual workflow above; automated API/browser fixtures
do not substitute for testing the deployed Supabase project.

Do not manually relax bucket access policies to enable PDF uploads.
