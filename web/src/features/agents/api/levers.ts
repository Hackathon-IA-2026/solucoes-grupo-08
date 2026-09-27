import type { AllowedRange, Lever, Premise, TaskState } from './exploration'
import { formatNumber } from '@/utils/format'

const leverLabels: Record<Lever, string> = {
  'bateria.potencia_mw': 'Potência da bateria',
  'bateria.duracao_horas': 'Duração da bateria',
  'bateria.subestacao': 'Ponto de conexão',
  'equipamento.ganho_limite_mw': 'Ganho de limite',
}

const leverUnits: Record<Lever, string> = {
  'bateria.potencia_mw': 'MW',
  'bateria.duracao_horas': 'h',
  'bateria.subestacao': '',
  'equipamento.ganho_limite_mw': 'MW',
}

export const leverLabel = (lever: Lever | null) => (lever ? leverLabels[lever] : 'Variação')

/** O valor com a unidade da alavanca: "100 MW", "6 h", ou o nome da subestação. */
export function leverValue(lever: Lever | null, value: number | string | null) {
  if (value == null) return '—'
  const text =
    typeof value === 'number' ? formatNumber(value, Number.isInteger(value) ? 0 : 1) : value
  const unit = lever ? leverUnits[lever] : ''
  return unit ? `${text} ${unit}` : text
}

/** Onde cada alavanca aparece na faixa permitida do resumo. */
export const leverRangeKey: Record<Lever, Exclude<keyof AllowedRange, 'avisos'>> = {
  'bateria.potencia_mw': 'potencia_mw',
  'bateria.duracao_horas': 'duracao_horas',
  'bateria.subestacao': 'subestacoes',
  'equipamento.ganho_limite_mw': 'ganho_limite_mw',
}

export const LEVERS = Object.keys(leverRangeKey) as Lever[]

/** As alavancas que a modalidade deixa variar: as que têm faixa no resumo. */
export const availableLevers = (range: AllowedRange) =>
  LEVERS.filter((lever) => range[leverRangeKey[lever]] != null)

/** A faixa de uma alavanca em texto: "100 a 1.200 MW" ou a lista de subestações. */
export function leverRange(lever: Lever, range: AllowedRange) {
  const value = range[leverRangeKey[lever]]
  if (value == null) return '—'
  if (Array.isArray(value)) return value.join(', ')
  return `${leverValue(lever, value.minimo)} a ${leverValue(lever, value.maximo)}`
}

export const premiseStatusLabels: Record<Premise['status'], string> = {
  nao_verificada: 'não verificada',
  proposta: 'proposta',
  validada: 'validada',
}

export const taskStateLabels: Record<TaskState, string> = {
  em_andamento: 'Em andamento',
  concluida: 'Concluída',
  falhou: 'Falhou',
}
