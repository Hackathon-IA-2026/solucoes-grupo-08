import type { Derived, Report, RevisionRow } from '../../api/report'
import { formatNumber } from '@/utils/format'

/** Número com sinal explícito: "+3.400", "−23.300.000". Só apresentação do delta que veio pronto. */
export function formatSigned(value: number, decimalPlaces = 0) {
  if (value === 0) return formatNumber(0, decimalPlaces)
  const sign = value > 0 ? '+' : '−'
  return `${sign}${formatNumber(Math.abs(value), decimalPlaces)}`
}

export function formatOptional(value: number | null, format: (value: number) => string) {
  return value == null ? '—' : format(value)
}

/**
 * Valor em reais abreviado para o destaque: "R$ 106,1 mi", "R$ 2,3 bi". Troca só a escala da
 * escrita; o valor completo fica logo abaixo, como veio.
 */
export function formatReaisShort(value: number): { amount: string; scale: string } {
  const magnitude = Math.abs(value)
  if (magnitude >= 1e9) return { amount: formatNumber(value / 1e9, 1), scale: 'bi' }
  if (magnitude >= 1e6) return { amount: formatNumber(value / 1e6, 1), scale: 'mi' }
  if (magnitude >= 1e3) return { amount: formatNumber(value / 1e3, 1), scale: 'mil' }
  return { amount: formatNumber(value, 2), scale: '' }
}

/** Da revisão (id) para a linha dela no relatório. */
export function rowsById(rows: RevisionRow[]) {
  return new Map(rows.map((row) => [row.revisao_id, row]))
}

export function revisionLabel(rows: Map<number, RevisionRow>, revisionId: number) {
  const row = rows.get(revisionId)
  return row == null ? `revisão ${revisionId}` : `rev ${row.posicao}`
}

/** A revisão mais nova coberta: é dela o resultado em destaque e para ela "Abrir a simulação". */
export function newestRow(report: Report) {
  return report.por_revisao.reduce<RevisionRow | undefined>(
    (newest, row) => (!newest || row.posicao > newest.posicao ? row : newest),
    undefined,
  )
}

/**
 * O valor de um campo da configuração como a API escreveu ("R$ 216 por MWh", "15 anos").
 * Parado, um valor; variou, os valores distintos na ordem das revisões.
 */
export function fieldValues(derived: Derived | null, campo: string): string[] {
  if (!derived) return []
  const still = derived.ficou_parado.find((field) => field.campo === campo)
  if (still) return still.valor == null ? [] : [still.valor]
  return derived.variou.find((field) => field.campo === campo)?.valores ?? []
}

/**
 * Lê de volta um valor em reais que a API já escreveu ("R$ 0,42", "R$ 250.000"). Serve só para
 * decidir se um aviso aparece; a tela mostra sempre o texto como veio.
 */
export function readReais(text: string): number | null {
  const match = /R\$\s?(-?[\d.]+(?:,\d+)?)/.exec(text)
  if (!match) return null
  const value = Number(match[1].replaceAll('.', '').replace(',', '.'))
  return Number.isFinite(value) ? value : null
}

/** Abaixo disto, o investimento inicial registrado quase certamente é erro de digitação. */
export const SUSPICIOUS_CAPEX_REAIS = 1000

/** Nova revisão a partir de uma revisão salva: o formulário nasce cópia dela. */
export function newRevisionUrl(restrictionId: string | undefined, fromRevisionId: number) {
  return restrictionId
    ? `/restricoes/${restrictionId}/nova-simulacao?revisar=${fromRevisionId}`
    : `/simulacoes/${fromRevisionId}`
}
