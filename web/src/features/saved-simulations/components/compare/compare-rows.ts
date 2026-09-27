import { configurationFields, type FieldId } from '../../api/configuration-fields'
import type { FullRevision } from '../../api/get-simulation'
import { formatFractionAsPercent, formatNumber, formatReais } from '@/utils/format'

/** Uma célula: o valor já formatado, ou o motivo de não haver (sem bateria, sem circuito). */
export type Cell = { text: string } | { missing: string }

export type CompareRow = { label: string; a: Cell; b: Cell }
export type CompareSection = { title: string; rows: CompareRow[] }

const text = (value: string): Cell => ({ text: value })
const missing = (reason: string): Cell => ({ missing: reason })

type Side = { revision: FullRevision; lineName?: string }

const withBattery = (side: Side, value: string): Cell =>
  side.revision.configuracao.bateria ? text(value) : missing('sem bateria')

const withCircuit = (side: Side, value: string): Cell =>
  side.revision.configuracao.equipamento ? text(value) : missing('sem circuito')

/** Campos de configuração que o comparador mostra, na ordem, e o bloco que os torna aplicáveis. */
const configRows: { id: FieldId; block: 'bateria' | 'equipamento' | null }[] = [
  { id: 'modalidade', block: null },
  { id: 'subestacao', block: 'bateria' },
  { id: 'potencia', block: 'bateria' },
  { id: 'capacidade', block: 'bateria' },
  { id: 'linha', block: 'equipamento' },
  { id: 'ganho', block: 'equipamento' },
  { id: 'cenario', block: null },
  { id: 'taxa', block: null },
  { id: 'horizonte', block: null },
  { id: 'investimento', block: null },
]

function configCell(side: Side, id: FieldId): Cell {
  const field = configurationFields(side.revision.configuracao, side.lineName).find(
    (item) => item.id === id,
  )
  if (!field || field.value === null) {
    return missing(field?.block === 'equipamento' ? 'sem circuito' : 'sem bateria')
  }
  return text(field.value)
}

/**
 * A tabela do comparador, lado a lado. Todo número vem pronto de `GET /simulacoes/{id}`: a tela só
 * formata e alinha. Onde uma revisão não tem o bloco (bateria, circuito), diz por quê.
 */
export function compareSections(a: Side, b: Side): CompareSection[] {
  const both = (make: (side: Side) => Cell): Pick<CompareRow, 'a' | 'b'> => ({
    a: make(a),
    b: make(b),
  })
  const tech = (side: Side) => side.revision.resultado.tecnico
  const financials = (side: Side) => side.revision.resultado.financeiro
  const optional = (value: number | null, format: (v: number) => string): Cell =>
    value == null ? missing('—') : text(format(value))

  return [
    {
      title: 'Energia, 12 meses',
      rows: [
        {
          label: 'Energia cortada',
          ...both((s) => text(`${formatNumber(tech(s).energia_cortada_mwh)} MWh`)),
        },
        {
          label: 'Energia recuperada',
          ...both((s) => text(`${formatNumber(tech(s).energia_recuperada_mwh)} MWh`)),
        },
        {
          label: 'Fração recuperada',
          ...both((s) => text(`${formatFractionAsPercent(tech(s).fracao_recuperada)} %`)),
        },
        {
          label: 'Bateria absorveu',
          ...both((s) =>
            withBattery(s, `${formatNumber(tech(s).energia_absorvida_bateria_mwh)} MWh`),
          ),
        },
        {
          label: 'Bateria devolveu',
          ...both((s) =>
            withBattery(s, `${formatNumber(tech(s).energia_devolvida_bateria_mwh)} MWh`),
          ),
        },
        {
          label: 'Circuito evitou',
          ...both((s) =>
            withCircuit(s, `${formatNumber(tech(s).energia_evitada_equipamento_mwh)} MWh`),
          ),
        },
      ],
    },
    {
      title: 'Financeiro',
      rows: [
        { label: 'VPL', ...both((s) => text(formatReais(financials(s).vpl_reais))) },
        {
          label: 'TIR',
          ...both((s) =>
            optional(financials(s).tir_aa, (v) => `${formatFractionAsPercent(v)} % a.a.`),
          ),
        },
        {
          label: 'Payback simples',
          ...both((s) =>
            optional(financials(s).payback_simples_anos, (v) => `${formatNumber(v, 1)} anos`),
          ),
        },
        {
          label: 'Payback descontado',
          ...both((s) =>
            optional(financials(s).payback_descontado_anos, (v) => `${formatNumber(v, 1)} anos`),
          ),
        },
        {
          label: 'Custo por MWh recuperado',
          ...both((s) =>
            optional(financials(s).custo_por_mwh_reais, (v) => `${formatReais(v, 2)}/MWh`),
          ),
        },
      ],
    },
    {
      title: 'Configuração',
      rows: configRows.map(({ id }) => ({
        label:
          configurationFields(a.revision.configuracao).find((field) => field.id === id)?.label ??
          id,
        ...both((s) => configCell(s, id)),
      })),
    },
  ]
}
