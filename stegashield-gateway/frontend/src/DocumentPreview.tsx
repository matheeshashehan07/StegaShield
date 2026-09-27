import { useEffect, useRef, useState } from 'react'
import { type Api, type DocumentRow, errorMessage } from './api'

export function DocumentPreview({ api, document, onClose }: { api: Api; document: DocumentRow; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const frame = useRef<HTMLIFrameElement>(null)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')
  const [ready, setReady] = useState(false)
  useEffect(() => {
    dialog.current?.showModal()
    const controller = new AbortController()
    let objectUrl = ''
    api.request(`/documents/${document.id}/download`, { method: 'POST', signal: controller.signal })
      .then(r => r.blob()).then(value => {
        if (controller.signal.aborted) return
        objectUrl = URL.createObjectURL(value); setUrl(objectUrl); setBlob(value)
      }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, document.id])
  useEffect(() => {
    if (!blob || !ready || document.format !== 'docx' || !frame.current?.contentDocument) return
    const doc = frame.current.contentDocument
    import('docx-preview').then(({ renderAsync }) => renderAsync(blob, doc.body, doc.head, { renderAltChunks: false, useBase64URL: true, renderComments: false }))
      .catch(() => setError('Preview rendering failed. You can still save the protected copy.'))
  }, [blob, ready, document.format])
  return <dialog ref={dialog} className="preview-dialog" onCancel={onClose} aria-label="Document preview">
    <header className="section-title"><div><span className="eyebrow">PROTECTED PREVIEW</span><h2>{document.title}</h2></div><button onClick={onClose} autoFocus>Close preview</button></header>
    <p className="muted">Opening this preview issues and records a protected copy. Browser rendering may differ from the original application.</p>
    {error && <p role="alert">{error}</p>}
    {!blob && !error && <p role="status">Preparing your protected preview...</p>}
    {blob && document.format === 'pdf' && <iframe title="PDF document preview" src={url} className="preview-frame"/>}
    {blob && document.format === 'docx' && <iframe ref={frame} title="DOCX document preview" sandbox="allow-same-origin" className="preview-frame" onLoad={() => setReady(true)} srcDoc={'<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; font-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"></head><body></body></html>'}/>}
    {url && <a className="primary" href={url} download={`${document.id}-protected.${document.format === 'pdf' ? 'pdf' : 'docx'}`}>Save this protected copy</a>}
    <p className="muted">Screenshots and text copied from a preview cannot be forensically attributed. Keep the protected file unchanged.</p>
  </dialog>
}
