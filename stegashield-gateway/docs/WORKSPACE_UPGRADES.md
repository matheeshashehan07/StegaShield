# Sessions, position access, and previews

## Activate

From `stegashield-gateway`, inspect `npx supabase db push --dry-run`, confirm the
linked project, then run `npx supabase db push`. This adds
`20260906000200_position_access.sql`. Restart the API and reload the portal.
Hosted migrations were not automatically applied by development testing.

## Using access controls

Open a document's **Access** panel. Individual member access continues to work.
Under **Job-position access**, expand **Manage job positions and member
assignments**, create a position, and assign a member. Each member has one job
position; these assignments affect all documents, not only the open document.
Then select that position and choose **Grant position access**.

Access is the union of active individual and position grants. Removing one does
not remove access supplied by the other. Future members inherit position grants;
changing/removing membership removes the old position's access to future requests.
Previously issued copies cannot be recalled. Administrators retain their existing
access to all active documents. Directory screens currently have bounded lists
(100 users/positions; 1,000 memberships); large deployments need pagination.

Position data is admin-managed under RLS, never inferred from user-editable JWT
metadata. The download RPC rechecks and locks the applicable membership/grant rows
before creating an event. Private storage and token mapping restrictions remain.

## Refresh and sign-out

Supabase persists the session in sessionStorage rather than only memory. Reloading
restores the session and verifies `/auth/me` again. Explicit sign-out clears the
local session. This is tab-scoped persistence, not a long-lived remember-me feature;
browser restore/duplicate-tab behaviour can vary. Sign out on shared devices.
Session storage remains accessible to same-origin JavaScript, unlike HttpOnly
cookies; production hardening still requires XSS controls and a considered cookie
session architecture if stronger isolation is required.

## Preview security and limitations

Opening Preview explicitly issues one signed protected copy through the existing
download API. The database event is committed before bytes are returned. Saving
from that dialog saves the same copy; a separate Download creates another event.
No original URLs, public buckets, or external document viewers are introduced.

DOCX rendering uses docx-preview in a sandboxed frame with scripts disabled,
HTML alt-chunks disabled, and a restrictive content security policy. DOCX layout
may differ from Word. PDF uses the browser PDF viewer; users without a compatible
viewer can save the protected copy instead. Object URLs are revoked when the
preview closes. Browser preview screenshots/copy-pasted text are not attributable;
the protected file's exact hash remains required for a forensic match.

UI changes preserve the established colours and navigation, with an accessible
modal preview, clearer access sections, responsive spacing, and focus states.
