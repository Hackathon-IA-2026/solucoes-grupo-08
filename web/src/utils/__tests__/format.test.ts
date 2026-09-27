import { describe, expect, it } from 'vitest'
import { formatDate, formatSnapshotId, withoutControlPrefix } from '../format'

describe('withoutControlPrefix', () => {
  it('drops the "Controle de inequação:" the ONS puts before the restriction text', () => {
    expect(
      withoutControlPrefix('Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV AÇU III'),
    ).toBe('LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV AÇU III')
  })

  it('accepts the spelling without accents and any case', () => {
    expect(withoutControlPrefix('controle de inequacao : LT X')).toBe('LT X')
  })

  it('leaves a text without the prefix as it is', () => {
    expect(withoutControlPrefix('LT 500 KV AÇU III')).toBe('LT 500 KV AÇU III')
  })
})

describe('formatSnapshotId', () => {
  it('shows the snapshot date in the Brazilian format', () => {
    expect(formatSnapshotId('2026-09-21')).toBe('21/09/2026')
  })

  it('leaves an id that is not a date as it came', () => {
    expect(formatSnapshotId('snapshot-teste')).toBe('snapshot-teste')
    expect(formatSnapshotId('2026-09-21T10:00:00')).toBe('2026-09-21T10:00:00')
  })
})

describe('formatDate', () => {
  it('does not move a date without time to the day before', () => {
    // "2026-09-21" lido como UTC viraria 20/09 no fuso do Brasil.
    expect(formatDate('2026-09-21')).toBe('21/09/2026')
  })

  it('formats a timestamp in the Brazilian format', () => {
    expect(formatDate('2026-09-21T15:00:00')).toBe('21/09/2026')
  })
})
