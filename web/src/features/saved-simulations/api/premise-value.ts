import { formatNumber } from '@/utils/format'

/** Valor da premissa como a tela lê: número em pt-BR, texto e booleano como estão. */
export function premiseValue(value: number | string | boolean): string {
  if (typeof value === 'number') return formatNumber(value, Number.isInteger(value) ? 0 : 4)
  if (typeof value === 'boolean') return value ? 'sim' : 'não'
  return value
}
