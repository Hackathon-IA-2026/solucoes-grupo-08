export function formatGWh(value: number, decimalPlaces = 1) {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  })
}

/** A API devolve energia em MWh; GWh é só apresentação. */
export function formatMWhAsGWh(valueMWh: number, decimalPlaces = 1) {
  return formatGWh(valueMWh / 1000, decimalPlaces)
}

/**
 * O texto do ONS de uma restrição abre com "Controle de inequação:", que não diz nada a quem lê
 * uma lista de restrições. Só apresentação: o texto guardado e usado na busca não muda.
 */
export function withoutControlPrefix(text: string) {
  return text.replace(/^\s*Controle de inequa[cç][aã]o\s*:\s*/i, '')
}

export function truncateText(value: string, maxLength = 90) {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength).trimEnd()}…`
}

export function formatInteger(value: number) {
  return Math.floor(value).toLocaleString('pt-BR')
}

export function formatPercentage(value: number, decimalPlaces = 1) {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  })
}

export function formatDateTime(isoDate: string) {
  return new Date(isoDate).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatMonthYear(isoDate: string) {
  return new Date(isoDate).toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' })
}

/** `periodo_fim` do snapshot é exclusivo; a tela mostra o último mês contido nele. */
export function formatPeriod(periodStart: string | null, periodEnd: string | null) {
  if (!periodStart || !periodEnd) return 'período não declarado no snapshot'
  const inclusiveEnd = new Date(new Date(periodEnd).getTime() - 1)
  return `${formatMonthYear(periodStart)} a ${formatMonthYear(inclusiveEnd.toISOString())}`
}

export function formatNumber(value: number, decimalPlaces = 0) {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  })
}

export function formatReais(value: number, decimalPlaces = 0) {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  })
}

/** O contrato guarda fração (0,85); a tela mostra por cento (85). Só apresentação. */
export function formatFractionAsPercent(fraction: number, decimalPlaces = 1) {
  return formatNumber(fraction * 100, decimalPlaces)
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/

/**
 * O identificador do snapshot é a data em que ele foi tirado ("2026-09-21"); a tela mostra no
 * formato brasileiro ("21/09/2026"). Um id que não tem esse formato aparece como veio. É só
 * apresentação: comparar snapshots e falar com a API continua pelo id original.
 */
export function formatSnapshotId(id: string) {
  const match = DATE_ONLY.exec(id)
  return match ? `${match[3]}/${match[2]}/${match[1]}` : id
}

export function formatDate(isoDate: string) {
  // Data sem hora ("2026-09-21") não passa por `Date`: ela seria lida como meia-noite UTC e, no
  // Brasil, apareceria como o dia anterior.
  if (DATE_ONLY.test(isoDate)) return formatSnapshotId(isoDate)
  return new Date(isoDate).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

/** Primeira letra maiúscula, o resto como veio: "monitorado" vira "Monitorado". */
export function capitalizeFirst(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** "rev 1 a rev 5", ou "rev 1" quando cobre uma só. */
export function formatRevisionRange(positions: number[]) {
  if (positions.length === 0) return 'nenhuma revisão'
  const first = positions[0]
  const last = positions[positions.length - 1]
  return first === last ? `rev ${first}` : `rev ${first} a rev ${last}`
}
