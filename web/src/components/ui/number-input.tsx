import { useState, type ChangeEvent, type ClipboardEvent, type FocusEvent } from 'react'
import { Input, type InputProps } from './input'
import {
  formatDecimal,
  formatMoney,
  moneyFromPaste,
  moneyFromTyping,
  parseDecimal,
  parseInteger,
  sanitizeDecimal,
} from '@/utils/number-input'

/**
 * `integer`: só dígitos. `decimal`: dígitos e uma vírgula. `money`: máscara de dinheiro, em que
 * cada dígito entra pelos centavos ("125050" vira "1.250,50").
 */
export type NumberKind = 'integer' | 'decimal' | 'money'

type NumberInputProps = Omit<InputProps, 'value' | 'defaultValue' | 'onChange' | 'type'> & {
  kind: NumberKind
  value: number | null
  onValueChange: (value: number | null) => void
}

const INPUT_MODE = { integer: 'numeric', decimal: 'decimal', money: 'numeric' } as const

/**
 * Campo numérico controlado: o valor que entra e o que sai é `number | null`, e `null` é campo
 * vazio, nunca zero. Serve ao `Controller` do React Hook Form (`value`, `onValueChange`, `onBlur`,
 * `ref`) e não guarda estado do formulário.
 *
 * O único estado próprio é o texto do modo decimal, porque "10," ainda é o número 10 mas o
 * usuário precisa ver a vírgula enquanto digita.
 */
export function NumberInput({ kind, value, onValueChange, onBlur, ...props }: NumberInputProps) {
  const [draft, setDraft] = useState(() => formatDecimal(value))

  // Valor mudou por fora (valor inicial do cenário, reset): o texto acompanha. Se o texto já
  // vale esse número, ele fica como está, para não engolir a vírgula em digitação.
  if (kind === 'decimal' && parseDecimal(draft) !== value) setDraft(formatDecimal(value))

  const shown =
    kind === 'decimal' ? draft : kind === 'money' ? formatMoney(value) : integerText(value)

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const text = event.target.value
    if (kind === 'integer') return onValueChange(parseInteger(text))
    if (kind === 'money') return onValueChange(moneyFromTyping(text, shown))

    const sanitized = sanitizeDecimal(text)
    setDraft(sanitized)
    onValueChange(parseDecimal(sanitized))
  }

  // Dinheiro colado vale como valor, e não como dígitos a empurrar pelos centavos.
  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    if (kind !== 'money') return
    event.preventDefault()
    onValueChange(moneyFromPaste(event.clipboardData.getData('text')))
  }

  function handleBlur(event: FocusEvent<HTMLInputElement>) {
    if (kind === 'decimal') setDraft(formatDecimal(value))
    onBlur?.(event)
  }

  return (
    <Input
      inputMode={INPUT_MODE[kind]}
      autoComplete="off"
      {...props}
      value={shown}
      onChange={handleChange}
      onPaste={handlePaste}
      onBlur={handleBlur}
    />
  )
}

function integerText(value: number | null): string {
  return value === null ? '' : String(value)
}
