import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ForensicOutcome } from './App'

describe('forensic evidence presentation', () => {
  it('makes no attribution for inconclusive results', () => {
    render(<ForensicOutcome result={{ outcome: 'inconclusive', reason: 'document_bytes_changed' }}/>)
    expect(screen.getByText('Inconclusive')).toBeInTheDocument()
    expect(screen.getByText('No user attribution has been made.')).toBeInTheDocument()
    expect(screen.queryByText('Recipient user ID')).not.toBeInTheDocument()
  })
  it('labels a match as an issued copy, not proof of the leaker', () => {
    render(<ForensicOutcome result={{ outcome: 'matched', exact_copy: true, message: 'match', download: { id: 'event-1', user_id: 'alice', document_id: 'doc-1', downloaded_at: '2026-09-05T12:00:00Z' } }}/>)
    expect(screen.getByText('Verified copy match')).toBeInTheDocument()
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.getByText('A match identifies an issued copy. It does not prove who leaked it.')).toBeInTheDocument()
  })
})
