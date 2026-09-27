import { useEffect, useState } from 'react'
import { type Api } from './api'

export function ProfileAvatar({ api, version, name, large = false }: { api: Api; version: number; name: string; large?: boolean }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = ''
    setUrl('')
    api.request('/auth/profile/photo', { signal: controller.signal }).then(async r => {
      if (r.status === 204) return
      const blob = await r.blob()
      if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) }
    }).catch(() => { /* The initials remain visible when no picture is available. */ })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [api, version])
  return <span className={`avatar ${large ? 'profile-avatar-large' : ''}`}>{url ? <img src={url} alt="Your profile" onError={() => setUrl('')}/> : (name.trim().slice(0, 1).toUpperCase() || 'U')}</span>
}
