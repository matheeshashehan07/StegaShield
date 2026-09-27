import { useEffect, useRef, useState } from 'react'
import { type Api, dateLabel, errorMessage } from './api'
import { ProfileAvatar } from './ProfileAvatar'

type AccountProfile = { id: string; role: string; display_name: string | null; created_at: string | null }

export function UserProfile({ api, email, onClose, onSaved }: { api: Api; email: string; onClose: () => void; onSaved: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [profile, setProfile] = useState<AccountProfile | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [removePhoto, setRemovePhoto] = useState(false)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { dialog.current?.showModal() }, [])
  useEffect(() => {
    const controller = new AbortController()
    setError(''); setProfile(null)
    api.json<AccountProfile>('/auth/profile', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) { setProfile(value); setName(value.display_name || '') }
    }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [api, retry])
  async function save(event: React.FormEvent) {
    event.preventDefault(); setSaveError(''); setNotice('')
    if (!name.trim() || name.trim().length > 120) { setSaveError('Enter a display name between 1 and 120 characters.'); return }
    if (photo && (!photo.size || photo.size > 2 * 1024 * 1024)) { setSaveError('Choose a non-empty JPEG or PNG up to 2 MB.'); return }
    const form = new FormData(); form.append('display_name', name.trim())
    if (photo) form.append('photo', photo)
    if (removePhoto) form.append('remove_photo', 'true')
    setBusy(true)
    try {
      await api.request('/auth/profile', { method: 'POST', body: form })
      setEditing(false); setPhoto(null); setRemovePhoto(false); setRetry(n => n + 1)
      setNotice('Your profile has been updated.'); onSaved()
    } catch (e) { setSaveError(errorMessage(e)) }
    finally { setBusy(false) }
  }
  return <dialog ref={dialog} className="preview-dialog profile-dialog" aria-labelledby="profile-title" onCancel={event => { if (busy) event.preventDefault(); else onClose() }}>
    <header className="section-title"><div><span className="eyebrow">MY ACCOUNT</span><h2 id="profile-title">Your profile</h2></div><button autoFocus disabled={busy} onClick={onClose}>Close profile</button></header>
    <ProfileAvatar api={api} version={retry} name={profile?.display_name || email} large/>
    <p className="muted">You can change your display name and picture. Email, user ID and account role cannot be edited here.</p>
    {notice && <p role="status">{notice}</p>}
    {saveError && <p role="alert">{saveError}</p>}
    {error ? <div role="alert"><p>{error}</p><button onClick={() => setRetry(n => n + 1)}>Retry</button></div> : !profile ? <p role="status">Loading your profile...</p> :
      <><dl className="profile-details"><dt>Display name</dt><dd>{profile.display_name || 'Not set'}</dd>
        <dt>Email address</dt><dd>{email || 'Not available'}</dd>
        <dt>User ID</dt><dd><code>{profile.id}</code></dd>
        <dt>Account role</dt><dd>{profile.role === 'admin' ? 'Administrator' : 'Member'}</dd>
        <dt>Profile created</dt><dd>{profile.created_at ? dateLabel(profile.created_at) : 'Not available'}</dd>
      </dl>{editing ? <form onSubmit={save} className="profile-edit-form"><fieldset disabled={busy}>
        <label>Display name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} required autoComplete="nickname"/></label>
        <label>Profile picture<input type="file" accept="image/jpeg,image/png" onChange={e => { setPhoto(e.target.files?.[0] || null); setRemovePhoto(false) }}/></label>
        <p className="muted">Static JPEG or PNG, up to 2 MB and 4096 pixels per side. Pictures are resized and metadata is removed.</p>
        <label className="profile-remove"><input type="checkbox" checked={removePhoto} disabled={Boolean(photo)} onChange={e => setRemovePhoto(e.target.checked)}/>Remove current picture</label>
        <div className="actions"><button className="primary" type="submit">{busy ? 'Saving...' : 'Save profile'}</button><button type="button" onClick={() => { setEditing(false); setSaveError(''); setPhoto(null); setRemovePhoto(false); setName(profile.display_name || '') }}>Cancel editing</button></div>
      </fieldset></form> : <button className="primary" onClick={() => { setEditing(true); setNotice('') }}>Edit profile</button>}</>}
  </dialog>
}
