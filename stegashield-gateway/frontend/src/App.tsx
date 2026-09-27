import { createContext, useContext, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { createClient, type Session, type SupabaseClient } from '@supabase/supabase-js'
import { checkResponse, createApi, dateLabel, errorMessage, validateDocx, type Api, type Audit, type DocumentRow, type ForensicResult, type Identity, type Permission, type Profile } from './api'

import { DocumentPreview } from './DocumentPreview'
import { ProfileAvatar } from './ProfileAvatar'
import { UserProfile } from './UserProfile'
import { PositionAccess } from './PositionAccess'
import './workspace-upgrades.css'

const PdfEnabled = createContext(false)

function Icon({ name = 'shield', size = 20 }: { name?: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    shield: <><path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7Z"/><path d="m8 12 3 3 5-6"/></>,
    file: <><path d="M14 2H5v20h14V7Z"/><path d="M14 2v6h5M8 12h8M8 16h6"/></>,
    search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></>,
    history: <><path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2"/></>,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
    upload: <><path d="M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5"/></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></>,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
    logout: <><path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3 21v-4a6 6 0 0 1 12 0v4M16 5a3 3 0 0 1 0 6M18 15c2 0 3 2 3 4v2"/></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.shield}</svg>
}

function Brand() { return <div className="brand"><span className="brand-icon"><Icon size={25}/></span><span>Stega<span className="brand-light">Shield</span><small>DOCUMENT SECURITY</small></span></div> }
export function Notice({ children, success = false }: { children: ReactNode; success?: boolean }) {
  return children ? <div className={`notice ${success ? 'success' : ''}`} role={success ? 'status' : 'alert'}>{children}</div> : null
}
function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty-icon"><Icon name="file" size={28}/></span><h3>{title}</h3><p>{children}</p></div>
}

export default function App() {
  const [pdfEnabled, setPdfEnabled] = useState(false)
  const [auth, setAuth] = useState<SupabaseClient | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/auth/config', { signal: controller.signal, cache: 'no-store' })
      .then(checkResponse).then(r => r.json()).then(config => {
        if (!controller.signal.aborted) setPdfEnabled(config.supportedFormats?.includes('pdf') === true)
        if (!controller.signal.aborted) setAuth(createClient(config.url, config.publishableKey, {
          auth: { persistSession: true, storage: window.sessionStorage, autoRefreshToken: true, detectSessionInUrl: false },
        }))
      }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [])
  if (!auth) return <div className="boot"><Brand/><h1>{error ? 'Let’s get connected.' : 'Opening your secure workspace…'}</h1><Notice>{error}</Notice>{error && <><p>Start the FastAPI backend on port 8000, then reload this page.</p><button onClick={() => location.reload()}>Try again</button></>}</div>
  return <PdfEnabled.Provider value={pdfEnabled}><AuthenticatedApp auth={auth}/></PdfEnabled.Provider>
}

function AuthenticatedApp({ auth }: { auth: SupabaseClient }) {
  const [session, setSession] = useState<Session | null>(null)
  const [restoring, setRestoring] = useState(true)
  useEffect(() => {
    const { data } = auth.auth.onAuthStateChange((_event, value) => { setSession(value); setRestoring(false) })
    return () => data.subscription.unsubscribe()
  }, [auth])
  if (restoring) return <div className="boot" role="status">Restoring your session...</div>
  if (!session) return <Login auth={auth}/>
  return <IdentityGate key={session.user.id} auth={auth} session={session}/>
}

function Login({ auth }: { auth: SupabaseClient }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true)
    const form = new FormData(event.currentTarget)
    try {
      const { error } = await auth.auth.signInWithPassword({ email: String(form.get('email')).trim(), password: String(form.get('password')) })
      if (error) throw error
    } catch (e) { setError(errorMessage(e)) }
    finally { setBusy(false) }
  }
  return <main className="login-layout"><section className="login-story"><Brand/><div className="story-content"><span className="eyebrow">CONTROL ACCESS. TRACE COPIES.</span><h1>Your documents.<br/>A clearer chain<br/>of accountability.</h1><p>A protected copy for every download.<br/>A secure place to understand its history.</p><div className="story-line"/><div className="story-points"><span><Icon name="lock"/>Private originals</span><span><Icon/>Verified downloads</span><span><Icon name="search"/>Audited investigations</span></div></div><small className="story-footer">StegaShield Gateway · DOCX workspace</small></section><section className="login-form-side"><div className="login-card"><span className="eyebrow">WELCOME BACK</span><h2>Sign in to your workspace</h2><p>Use the account provided by your administrator.</p><form onSubmit={login}><label>Email address<input name="email" type="email" placeholder="you@organization.com" autoComplete="username" required disabled={busy}/></label><label>Password<input name="password" type="password" placeholder="Enter your password" autoComplete="current-password" required disabled={busy}/></label><Notice>{error}</Notice><button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<Icon name="arrow"/></button></form><div className="login-note"><Icon name="lock" size={16}/><span>Your session survives refresh in this tab. Sign out when using a shared device.</span></div><p className="help-text">Need access? Contact your project administrator.</p></div></section></main>
}

function IdentityGate({ auth, session }: { auth: SupabaseClient; session: Session }) {
  const api = useMemo(() => createApi(auth, session.user.id), [auth, session.user.id])
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    api.json<Identity>('/auth/me', { signal: controller.signal }).then(value => {
      if (value.id !== session.user.id || !['user', 'admin'].includes(value.role)) throw new Error('Unable to verify your application profile.')
      setIdentity(value)
    }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [api, retry, session.user.id])
  if (!identity) return <div className="boot"><Brand/><h1>Verifying your access</h1><Notice>{error}</Notice>{error && <div className="actions"><button onClick={() => { setError(''); setRetry(n => n + 1) }}>Retry</button><button onClick={() => void auth.auth.signOut({ scope: 'local' })}>Sign out</button></div>}</div>
  return <Workspace api={api} identity={identity} auth={auth} email={session.user.email || ''}/>
}

type Page = 'documents' | 'upload' | 'forensics' | 'audit'
function Workspace({ api, identity, auth, email }: { api: Api; identity: Identity; auth: SupabaseClient; email: string }) {
  const [page, setPage] = useState<Page>('documents')
  const [profileOpen, setProfileOpen] = useState(false)
  const [profileVersion, setProfileVersion] = useState(0)
  const [displayName, setDisplayName] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    api.json<{ display_name: string | null }>('/auth/profile', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setDisplayName(value.display_name || '') })
      .catch(() => { /* Email remains available if profile details cannot load. */ })
    return () => controller.abort()
  }, [api, profileVersion])
  const [signoutError, setSignoutError] = useState('')
  const isAdmin = identity.role === 'admin'
  const navigation: { id: Page; title: string; icon: string }[] = [{ id: 'documents', title: 'Documents', icon: 'file' }, ...(isAdmin ? [{ id: 'upload' as Page, title: 'Upload original', icon: 'upload' }, { id: 'forensics' as Page, title: 'Forensic lookup', icon: 'search' }, { id: 'audit' as Page, title: 'Audit trail', icon: 'history' }] : [])]
  const pdfEnabled = useContext(PdfEnabled)
  async function signout() {
    const { error } = await auth.auth.signOut({ scope: 'local' })
    if (error) setSignoutError('Could not sign out. Please retry before leaving a shared device.')
  }
  return <div className="workspace"><aside className="sidebar"><Brand/><div className="workspace-label">WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(item => <button key={item.id} className={page === item.id ? 'nav-item active' : 'nav-item'} aria-current={page === item.id ? 'page' : undefined} onClick={() => setPage(item.id)}><Icon name={item.icon}/>{item.title}{page === item.id && <span className="nav-dot"/>}</button>)}</nav><button className="nav-item" onClick={() => setProfileOpen(true)}><Icon name="users"/>View profile</button><div className="sidebar-tip"><Icon/><strong>Protected by design</strong><p>Every download receives its own signed watermark.</p></div><div className="sidebar-bottom"><ProfileAvatar api={api} version={profileVersion} name={displayName || email}/><div><strong title={displayName || undefined}>{displayName || (isAdmin ? 'Administrator' : 'Member')}</strong><small title={email}>{email}</small></div><button className="icon-button" aria-label="Sign out" onClick={() => void signout()}><Icon name="logout"/></button></div></aside><div className="workspace-body"><header className="topbar"><div><span className="breadcrumb">Workspace</span><span className="slash">/</span>{navigation.find(n => n.id === page)?.title}</div><span className="role-badge"><span/>{isAdmin ? 'Admin access' : 'Member access'}</span></header><main className="content">{profileOpen && <UserProfile api={api} email={email} onSaved={() => setProfileVersion(n => n + 1)} onClose={() => setProfileOpen(false)}/>}<Notice>{signoutError}</Notice>{page === 'documents' && <Documents key={profileVersion} api={api} isAdmin={isAdmin} onUpload={() => setPage('upload')}/>} {isAdmin && page === 'upload' && <Upload api={api} onDone={() => setPage('documents')}/>} {isAdmin && page === 'forensics' && <Forensics api={api}/>} {isAdmin && page === 'audit' && <AuditTrail api={api}/>}</main><footer className="workspace-footer"><span>StegaShield · Secure document gateway</span><span>{pdfEnabled ? 'DOCX and PDF supported' : 'DOCX supported · PDF disabled'}</span></footer></div></div>
}

function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{children}</div>
}

function Documents({ api, isAdmin, onUpload }: { api: Api; isAdmin: boolean; onUpload: () => void }) {
  const [documents, setDocuments] = useState<DocumentRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState('')
  const [preview, setPreview] = useState<DocumentRow | null>(null)
  const [selected, setSelected] = useState<DocumentRow | null>(null)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError(''); setDocuments([])
    api.json<DocumentRow[]>('/documents', { signal: controller.signal }).then(setDocuments).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [api, refresh])
  async function download(document: DocumentRow) {
    setBusy(document.id); setError(''); setNotice('')
    try {
      const response = await api.request(`/documents/${document.id}/download`, { method: 'POST' })
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = window.document.createElement('a')
      anchor.href = url; anchor.download = `${document.id}-protected.${document.format === 'pdf' ? 'pdf' : 'docx'}`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 10000)
      setNotice('Your protected copy is ready. Keep the downloaded file unchanged for exact forensic matching.')
    } catch (e) { setError(errorMessage(e)) }
    finally { setBusy('') }
  }
  const filtered = documents.filter(d => d.title.toLowerCase().includes(query.toLowerCase()))
  return <><PageHeading eyebrow="DOCUMENT LIBRARY" title="A secure home for your documents." description={isAdmin ? 'Manage originals, control access, and issue protected copies.' : 'Your permitted documents, ready for a protected download.'}>{isAdmin && <button className="primary" onClick={onUpload}><Icon name="upload"/>Upload original</button>}</PageHeading><div className="stat-grid"><div className="stat"><span className="stat-icon"><Icon name="file"/></span><div><small>Available documents</small><strong>{loading ? '—' : documents.length}</strong></div></div><div className="stat"><span className="stat-icon"><Icon name="lock"/></span><div><small>Original storage</small><strong className="text-stat">Private</strong></div></div><div className="stat"><span className="stat-icon"><Icon/></span><div><small>Download protection</small><strong className="text-stat">Signed per copy</strong></div></div></div><Notice>{error}</Notice><Notice success>{notice}</Notice><section className="panel"><div className="panel-toolbar"><h2>{isAdmin ? 'Document library' : 'My documents'}<span className="count">{documents.length}</span></h2><div className="actions"><label className="search-box"><Icon name="search" size={17}/><input aria-label="Search documents" placeholder="Search documents…" value={query} onChange={e => setQuery(e.target.value)}/></label><button className="secondary" disabled={loading} onClick={() => setRefresh(n => n + 1)}>Refresh</button></div></div>{loading ? <div className="loading" role="status">Loading documents…</div> : filtered.length ? <div className="table-scroll"><table><thead><tr><th>Document name</th><th>Format</th><th>Added</th><th>Actions</th></tr></thead><tbody>{filtered.map(doc => <tr key={doc.id}><td><div className="document-cell"><span className="doc-icon"><Icon name="file"/></span><div><strong>{doc.title}</strong><small>{(doc.size_bytes / 1024).toFixed(1)} KB · Original stored privately</small></div></div></td><td><span className="format-tag">{doc.format.toUpperCase()}</span></td><td className="date-cell">{dateLabel(doc.created_at)}</td><td><div className="actions">{isAdmin && <button className="text-button" onClick={() => setSelected(doc)}><Icon name="users" size={16}/>Access</button>}<button className="text-button" onClick={() => setPreview(doc)}>Preview</button><button className="download-button" disabled={Boolean(busy)} onClick={() => void download(doc)}><Icon name="download" size={16}/>{busy === doc.id ? 'Preparing…' : 'Download'}</button></div></td></tr>)}</tbody></table></div> : <Empty title={query ? 'No matching documents' : 'No documents available'}>{query ? 'Try another title.' : isAdmin ? 'Upload your first original DOCX to get started.' : 'Your administrator can grant you access to a document.'}</Empty>}<div className="panel-footer"><Icon name="lock" size={14}/>Downloads are permission-checked and recorded before your copy is returned. Showing up to 100 documents.</div></section>{preview && <DocumentPreview key={preview.id} api={api} document={preview} onClose={() => setPreview(null)}/>} {selected && <Permissions key={selected.id} api={api} document={selected} onClose={() => setSelected(null)}/>}<div className="info-banner"><Icon/><div><strong>One download. One unique copy.</strong><p>Your document receives an invisible signed identifier. Personal information is never embedded in the file.</p></div></div></>
}

function FilePicker({ onChange, label = 'Choose a DOCX document', disabled = false }: { onChange: (file: File | undefined) => void; label?: string; disabled?: boolean }) {
  const pdfEnabled = useContext(PdfEnabled)
  return <label className="file-picker"><span className="upload-icon"><Icon name="upload" size={28}/></span><strong>{pdfEnabled ? label.replace('DOCX', 'DOCX or PDF') : label}</strong><span>{pdfEnabled ? 'DOCX or PDF' : 'DOCX only'} · Up to 10 MB</span><input type="file" accept={pdfEnabled ? ".docx,.pdf" : ".docx"} aria-label={pdfEnabled ? label.replace("DOCX", "DOCX or PDF") : label} disabled={disabled} onChange={e => onChange(e.target.files?.[0])}/></label>
}

function Upload({ api, onDone }: { api: Api; onDone: () => void }) {
  const pdfEnabled = useContext(PdfEnabled)
  const [file, setFile] = useState<File>()
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploaded, setUploaded] = useState<string | null>(null)
  async function submit(e: FormEvent) {
    e.preventDefault(); const validation = validateDocx(file, pdfEnabled)
    if (validation) { setError(validation); return }
    setBusy(true); setError('')
    const form = new FormData(); form.append('file', file!); form.append('title', title.trim())
    try { const result = await api.json<{ id: string }>('/documents', { method: 'POST', body: form }); setUploaded(result.id) }
    catch (e) { setError(errorMessage(e)) }
    finally { setBusy(false) }
  }
  return <><PageHeading eyebrow="ADMINISTRATION" title="Start with an original." description="Upload an unwatermarked original. Access is granted separately."/><div className="two-column"><section className="panel form-panel">{uploaded ? <div className="upload-success"><Icon size={40}/><h2>Original uploaded</h2><p>Your document is stored privately. Open Access in the library to choose who can download it.</p><code>{uploaded}</code><button className="primary" onClick={onDone}>Open document library<Icon name="arrow"/></button></div> : <form onSubmit={submit}><h2>Document details</h2><label>Document title<input value={title} onChange={e => setTitle(e.target.value)} maxLength={255} required placeholder="e.g. Internal security policy" disabled={busy}/></label><FilePicker disabled={busy} onChange={value => { setFile(value); setError('') }}/><Notice>{error}</Notice><button className="primary" disabled={busy || !title.trim()}>{busy ? 'Uploading original…' : 'Upload original'}<Icon name="upload"/></button></form>}</section><aside className="explainer"><span className="eyebrow">BEFORE YOU UPLOAD</span><h2>Keep the source clean.</h2><p>Use a supported original with no existing StegaShield watermark.</p><ol><li>The original stays in private storage.</li><li>You decide who can access it.</li><li>Every download generates a new protected copy.</li></ol><div className="small-note">{pdfEnabled ? 'PDF: static files only, up to 100 pages. Encrypted, interactive, and digitally signed PDFs are rejected.' : 'PDF is disabled. Macro-enabled documents are not supported.'}</div></aside></div></>
}

function Permissions({ api, document, onClose }: { api: Api; document: DocumentRow; onClose: () => void }) {
  const [users, setUsers] = useState<Profile[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [recipient, setRecipient] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [confirm, setConfirm] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); setLoading(true)
    Promise.all([api.json<Profile[]>('/admin/users', { signal: controller.signal }), api.json<Permission[]>(`/documents/${document.id}/permissions`, { signal: controller.signal })]).then(([u, p]) => { setUsers(u); setPermissions(p) }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [api, document.id, version])
  async function change(id: string, revoke = false) {
    setBusy(true); setError('')
    try {
      await api.request(`/documents/${document.id}/permissions${revoke ? `/${id}` : ''}`, revoke ? { method: 'DELETE' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: id }) })
      setRecipient(''); setConfirm(''); setVersion(n => n + 1)
    } catch (e) { setError(errorMessage(e)) }
    finally { setBusy(false) }
  }
  return <section className="panel form-panel access-panel" aria-label="Document access"><div className="section-title"><div><span className="eyebrow">MANAGE ACCESS</span><h2>{document.title}</h2></div><button onClick={onClose}>Close</button></div><PositionAccess api={api} documentId={document.id}/><h3>Individual member access</h3><Notice>{error}</Notice>{loading ? <p role="status">Loading access…</p> : <><form className="grant-form" onSubmit={e => { e.preventDefault(); void change(recipient) }}><label>Choose a member<select required value={recipient} disabled={busy} onChange={e => setRecipient(e.target.value)}><option value="">Select a user</option>{users.filter(u => u.role === 'user' && !permissions.some(p => p.user_id === u.id)).map(u => <option key={u.id} value={u.id}>{u.display_name || u.id}</option>)}</select></label><button className="primary" disabled={busy || !recipient}>Grant access</button></form><p className="muted">Administrators can access all active documents. User IDs are shown when no display name is set.</p>{permissions.length === 0 ? <p>No individual permissions yet.</p> : <ul className="permission-list">{permissions.map(p => <li key={p.user_id}><div><strong>{users.find(u => u.id === p.user_id)?.display_name || p.user_id}</strong><small>{p.expires_at ? `Expires ${dateLabel(p.expires_at)}` : 'No expiry'}</small></div><div className="actions">{confirm === p.user_id ? <><span>Revoke access?</span><button className="danger" disabled={busy} onClick={() => void change(p.user_id, true)}>Confirm revoke</button><button disabled={busy} onClick={() => setConfirm('')}>Cancel</button></> : <button disabled={busy} onClick={() => setConfirm(p.user_id)}>Revoke</button>}</div></li>)}</ul>}</>}</section>
}

export function ForensicOutcome({ result }: { result: ForensicResult }) {
  const reasons: Record<string, string> = { no_unique_valid_token: 'No single valid StegaShield watermark was recovered.', token_not_registered: 'The watermark does not have a matching download record.', document_bytes_changed: 'The file differs from the recorded protected copy. Edited or re-saved files cannot be attributed in this release.' }
  if (result.outcome === 'inconclusive') return <section className="result inconclusive" role="status"><span className="eyebrow">EXAMINATION COMPLETE</span><h2>Inconclusive</h2><p>{reasons[result.reason] || 'The available evidence does not support a verified match.'}</p><strong>No user attribution has been made.</strong></section>
  return <section className="result matched" role="status"><span className="eyebrow">EXAMINATION COMPLETE</span><h2><Icon/>Verified copy match</h2><p>The signature and exact file hash match a recorded download.</p><dl><dt>Recipient user ID</dt><dd>{result.download.user_id}</dd><dt>Document ID</dt><dd>{result.download.document_id}</dd><dt>Download event</dt><dd>{result.download.id}</dd><dt>Issued at</dt><dd>{dateLabel(result.download.downloaded_at)}</dd></dl><div className="small-note">A match identifies an issued copy. It does not prove who leaked it.</div></section>
}

function Forensics({ api }: { api: Api }) {
  const pdfEnabled = useContext(PdfEnabled)
  const [file, setFile] = useState<File>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<ForensicResult | null>(null)
  async function submit(e: FormEvent) {
    e.preventDefault(); setResult(null); setError('')
    const validation = validateDocx(file, pdfEnabled); if (validation) { setError(validation); return }
    setBusy(true); const form = new FormData(); form.append('file', file!)
    try { setResult(await api.json<ForensicResult>(`/forensics/${file!.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'docx'}`, { method: 'POST', body: form })) }
    catch (e) { setError(errorMessage(e)) }
    finally { setBusy(false) }
  }
  return <><PageHeading eyebrow="FORENSIC WORKSPACE" title="Follow the document’s trail." description="Examine a recovered document against verified download records."/><div className="two-column"><div><section className="panel form-panel"><form onSubmit={submit}><h2>Examine a document</h2><p className="muted">Submit the recovered file without editing or re-saving it.</p><FilePicker label="Choose a suspect DOCX" disabled={busy} onChange={value => { setFile(value); setResult(null); setError('') }}/><Notice>{error}</Notice><button className="primary" disabled={busy}>{busy ? 'Examining document…' : 'Run forensic lookup'}<Icon name="search"/></button></form></section>{result && <ForensicOutcome result={result}/>}</div><aside className="explainer"><span className="eyebrow">EVIDENCE, WITH LIMITS</span><h2>A match needs two checks.</h2><ol><li>A valid, signed per-download watermark.</li><li>An exact match to the issued file’s hash.</li></ol><p>Changes to a document—even re-saving in Word—can produce an inconclusive result.</p><div className="small-note"><Icon name="history"/>Every examination is audited. Suspect file contents are not retained.</div></aside></div></>
}

function AuditTrail({ api }: { api: Api }) {
  const [rows, setRows] = useState<Audit[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError(''); setRows([])
    api.json<Audit[]>('/admin/forensic-events', { signal: controller.signal }).then(setRows).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [api, version])
  return <><PageHeading eyebrow="ACCOUNTABILITY" title="An auditable trail." description="The latest 50 forensic audit entries. Started and completed entries share an attempt ID."><button disabled={loading} onClick={() => setVersion(n => n + 1)}>Refresh</button></PageHeading><Notice>{error}</Notice><section className="panel">{loading ? <div className="loading" role="status">Loading audit entries…</div> : rows.length ? <div className="table-scroll"><table><thead><tr><th>Recorded</th><th>Status</th><th>Attempt / administrator</th><th>Reason</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{dateLabel(row.attempted_at)}</td><td><span className={`status-tag ${row.completed && row.outcome === 'matched' ? 'green' : ''}`}>{row.completed ? row.outcome : 'started'}</span></td><td className="audit-ids"><code>{row.attempt_id}</code><small>{row.performed_by}</small></td><td>{row.reason?.replaceAll('_', ' ')}</td></tr>)}</tbody></table></div> : <Empty title="No forensic activity yet">Completed examinations and their start records will appear here.</Empty>}</section><p className="muted audit-note">A start entry without a completion may indicate an interrupted examination. Entries are append-only.</p></>
}
