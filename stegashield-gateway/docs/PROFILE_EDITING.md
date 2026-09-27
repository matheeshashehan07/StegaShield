# Profile editing

Use **View profile > Edit profile** to change your display name, upload a JPEG/PNG,
or remove the current picture. Email, user ID, application role and job position
are not editable here. Names are read from profiles throughout the portal; the
sidebar updates after saving and access/member lists reload the current name.
Pictures appear in the user's own profile and sidebar, not a public directory.

## Deployment

1. Install root requirements (Pillow is now a runtime dependency).
2. From `stegashield-gateway`, inspect `npx supabase db push --dry-run`, confirm the
   linked project, and apply `npx supabase db push`.
3. Restart FastAPI and reload the portal.

The new migration is `20260909000100_profile_editing.sql`. Hosted migration and
configuration changes are not automatically performed by local development.

## Security/storage decision

Avatars are small private database records under RLS, not public Storage URLs.
This permits atomic display-name/picture replacement in one trusted RPC and avoids
orphaned storage objects when a write fails. The API supplies only the verified
principal's ID. Ordinary clients cannot execute the trusted RPC or write raw
photo rows. Only self/admin reads are allowed by database RLS; the current photo
HTTP route exposes only the signed-in user's picture.

Input must be a static JPEG/PNG up to 2 MB, with each dimension at most 4096 pixels.
The server decodes it, applies orientation, fits it within 256x256, composites
transparency onto white and re-encodes a fresh JPEG without source metadata. The
encoded JPEG is at most 100 KB. The original upload is not retained. Replacement
overwrites the user's database photo; removal deletes that current row. Normal
database backup retention still applies; no claim of immediate backup erasure.

Only display_name, photo and remove_photo are accepted by the update endpoint.
Unknown fields and conflicting remove/replace requests are rejected. Responses
are no-store; pictures use image/jpeg and nosniff. Browser object URLs are revoked
on unmount/replacement. Name/photo update acknowledgement is required before the
UI reports success. Like other profile changes, this does not yet have a separate
append-only history. Privileged database/service credentials remain trusted.
