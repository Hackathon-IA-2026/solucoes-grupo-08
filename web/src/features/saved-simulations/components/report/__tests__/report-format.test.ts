import { describe, expect, it } from 'vitest'
import { formatReaisShort, readReais } from '../report-format'

describe('report format', () => {
  it('reads back reais the API already wrote, in pt-BR', () => {
    expect(readReais('R$ 0,42')).toBe(0.42)
    expect(readReais('R$ 250.000')).toBe(250000)
    expect(readReais('R$ 216 por MWh')).toBe(216)
    expect(readReais('vazio')).toBeNull()
  })

  it('shortens large amounts to mi and bi, keeping small ones whole', () => {
    expect(formatReaisShort(106_129_420.22)).toEqual({ amount: '106,1', scale: 'mi' })
    expect(formatReaisShort(2_336_178_656)).toEqual({ amount: '2,3', scale: 'bi' })
    expect(formatReaisShort(-5_079_825_146)).toEqual({ amount: '-5,1', scale: 'bi' })
    expect(formatReaisShort(420)).toEqual({ amount: '420,00', scale: '' })
  })
})
