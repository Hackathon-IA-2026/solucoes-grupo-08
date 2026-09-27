import { describe, expect, it } from 'vitest'
import {
  formatCurrency,
  formatDecimal,
  formatMoney,
  moneyFromPaste,
  moneyFromTyping,
  parseDecimal,
  parseInteger,
  sanitizeDecimal,
} from '../number-input'

/** Digita dígito a dígito, como o campo de dinheiro recebe: cada tecla reformata o que já estava. */
function typeMoney(keys: string): string {
  let shown = ''
  for (const key of keys) {
    shown = formatMoney(moneyFromTyping(shown + key, shown))
  }
  return shown
}

describe('money typed', () => {
  it.each([
    ['0', '0,00'],
    ['1', '0,01'],
    ['10', '0,10'],
    ['100', '1,00'],
    ['1000', '10,00'],
    ['1250', '12,50'],
    ['125050', '1.250,50'],
  ])('typing %s shows %s', (keys, shown) => {
    expect(typeMoney(keys)).toBe(shown)
  })

  it('deleting the cents down to nothing empties the field', () => {
    expect(moneyFromTyping('0,0', '0,01')).toBeNull()
    expect(moneyFromTyping('', '0,01')).toBeNull()
  })

  it('deleting one digit shifts the cents', () => {
    expect(moneyFromTyping('1.250,5', '1.250,50')).toBe(125.05)
  })

  it('typed zero stays zero', () => {
    expect(moneyFromTyping('0', '')).toBe(0)
  })

  it('ignores letters and signs', () => {
    expect(moneyFromTyping('1a2-3', '')).toBe(1.23)
  })

  it('caps the length so precision does not overflow', () => {
    expect(moneyFromTyping('9'.repeat(30), '')).toBe(9999999999.99)
  })
})

describe('money pasted', () => {
  it.each([
    ['R$ 1.250,50', 1250.5],
    ['1.250,50', 1250.5],
    ['1250,5', 1250.5],
    ['1250.50', 1250.5],
    ['1.250', 1250],
    ['R$ 10.000,00', 10000],
    ['0,999', 1],
  ])('pasting %s is worth %s', (pasted, value) => {
    expect(moneyFromPaste(pasted)).toBe(value)
  })

  it('text with no number empties the field', () => {
    expect(moneyFromPaste('abc')).toBeNull()
  })
})

describe('money formatting', () => {
  it("brings the API's value to the field with two decimals and a thousands separator", () => {
    expect(formatMoney(1250.5)).toBe('1.250,50')
    expect(formatMoney(1500000)).toBe('1.500.000,00')
    expect(formatMoney(0)).toBe('0,00')
    expect(formatMoney(null)).toBe('')
  })

  it('round trip loses no cent', () => {
    const shown = formatMoney(1250.5)
    expect(moneyFromPaste(shown)).toBe(1250.5)
  })

  it('the error message carries the currency symbol', () => {
    expect(formatCurrency(100)).toBe('R$ 100,00')
  })
})

describe('integers', () => {
  it.each([
    ['0', 0],
    ['1', 1],
    ['10', 10],
    ['100', 100],
    ['abc', null],
    ['', null],
    ['-10', 10],
    ['1e3', 13],
    ['10.5', 10],
    ['10,5', 10],
    ['1.000', 1000],
  ])('%s becomes %s', (typed, value) => {
    expect(parseInteger(typed)).toBe(value)
  })
})

describe('decimals', () => {
  it.each([
    ['0', 0],
    ['10', 10],
    ['10,5', 10.5],
    ['10.50', 10.5],
    ['0.85', 0.85],
    ['0,85', 0.85],
    ['0.850', 0.85],
    ['1.250,50', 1250.5],
    ['abc', null],
    ['', null],
    [',', null],
    ['10,', 10],
    ['-5', 5],
  ])('%s becomes %s', (typed, value) => {
    expect(parseDecimal(typed)).toBe(value)
  })

  it('keeps the comma that is still being typed', () => {
    expect(sanitizeDecimal('10,')).toBe('10,')
    expect(sanitizeDecimal('10,5,')).toBe('10,5')
  })

  it('strips letters, signs and symbols', () => {
    expect(sanitizeDecimal('R$ 1e+2')).toBe('12')
  })

  it('shows the number the way the user reads it', () => {
    expect(formatDecimal(0.85)).toBe('0,85')
    expect(formatDecimal(10)).toBe('10')
    expect(formatDecimal(null)).toBe('')
  })
})
