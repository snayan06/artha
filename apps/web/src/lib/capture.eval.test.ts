/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import type { HouseholdMember, LedgerAccount } from '../types'
import { parseCaptureLocally } from './capture'

interface EvalCase {
  id: string
  utterance: string
  outcome: 'draft' | 'clarify' | 'reject'
  expected: {
    kind?: 'expense' | 'income' | 'transfer'
    amount_paise?: number
    source_account_id?: string
    destination_account_id?: string
    occurred_on?: string
    member_ids?: string[]
  }
}

const repoRoot = resolve(process.cwd(), '../..')
const context = JSON.parse(readFileSync(resolve(repoRoot, 'evals/capture-context-v1.json'), 'utf8')) as {
  accounts: LedgerAccount[]
  members: HouseholdMember[]
}
const casesRaw = readFileSync(resolve(repoRoot, 'evals/capture-parser-v1.jsonl'), 'utf8')
const cases = casesRaw.trim().split('\n').map((line) => JSON.parse(line) as EvalCase)
const byId = new Map(cases.map((item) => [item.id, item]))

// These are the high-frequency and safety-sensitive cases guaranteed by the
// no-provider fallback. The full 50-case set is reserved for hosted-model scoring.
const MUST_PASS_DRAFTS = [
  'CAP-001', 'CAP-002', 'CAP-003', 'CAP-004', 'CAP-005', 'CAP-006',
  'CAP-009', 'CAP-010', 'CAP-011', 'CAP-012', 'CAP-013', 'CAP-014',
  'CAP-015', 'CAP-018', 'CAP-019', 'CAP-023', 'CAP-027', 'CAP-039',
  'CAP-042', 'CAP-043', 'CAP-044', 'CAP-050'
]

describe('deterministic capture evaluation gate', () => {
  it.each(MUST_PASS_DRAFTS)('%s matches critical structured fields', (caseId) => {
    vi.setSystemTime(new Date('2026-08-04T08:00:00+05:30'))
    const item = byId.get(caseId)
    expect(item, `missing evaluation case ${caseId}`).toBeDefined()
    const draft = parseCaptureLocally(item!.utterance, context.members, context.accounts)
    const expected = item!.expected

    expect(draft.kind).toBe(expected.kind === 'income' ? 'credit' : expected.kind === 'transfer' ? 'transfer' : 'debit')
    expect(draft.amountPaise).toBe(expected.amount_paise)
    expect(draft.sourceAccountId).toBe(expected.source_account_id)
    expect(draft.destinationAccountId).toBe(expected.destination_account_id)
    if (expected.occurred_on) expect(draft.occurredAt).toBe(expected.occurred_on)
    if (expected.member_ids) expect(draft.memberSplits.map((split) => split.memberId)).toEqual(expected.member_ids)
  })

  it('rejects negative amount confirmation and does not claim high confidence without an account', () => {
    const negative = parseCaptureLocally(byId.get('CAP-032')!.utterance, context.members, context.accounts)
    const ambiguous = parseCaptureLocally(byId.get('CAP-049')!.utterance, context.members, context.accounts)
    const unknownMember = parseCaptureLocally(byId.get('CAP-036')!.utterance, context.members, context.accounts)

    expect(negative.amountPaise).toBe(0)
    expect(negative.confidence).toBe('review')
    expect(ambiguous.confidence).toBe('review')
    expect(ambiguous.merchant).toBe('')
    expect(unknownMember.confidence).toBe('review')
    expect(unknownMember.memberSplits).toEqual([])
  })
})
