import type { Derived } from '../../api/report'
import { cn } from '@/utils/cn'
import { capitalizeFirst } from '@/utils/format'

type Group = 'bateria' | 'operacao' | 'circuito' | 'financeiro' | 'outros'

const groupLabels: Record<Group, string> = {
  bateria: 'Bateria',
  operacao: 'Operação e degradação',
  circuito: 'Circuito',
  financeiro: 'Financeiro',
  outros: 'Outros',
}

// O grupo sai do caminho do campo em `Configuracao`, o mesmo que a API manda em `campo`.
function groupOf(campo: string): Group {
  if (campo === 'modalidade') return 'bateria'
  if (/^bateria\.(soc_|degradacao_)/.test(campo) || campo === 'financeira.cenario')
    return 'operacao'
  if (campo.startsWith('bateria.')) return 'bateria'
  if (campo.startsWith('equipamento.')) return 'circuito'
  if (campo.startsWith('financeira.')) return 'financeiro'
  return 'outros'
}

// Campos que a API ainda não rotula: sem isto, o caminho interno apareceria na tela.
const fallbackLabels: Record<string, string> = {
  'financeira.reposicoes': 'Reposições',
}

const labelOf = (campo: string, rotulo: string) =>
  rotulo === campo ? (fallbackLabels[campo] ?? campo) : rotulo

type Row = { campo: string; label: string; value: string; varied: boolean }

/** Cada parâmetro da configuração, agrupado: o que variou entre as revisões aparece marcado. */
export function ConfigMatrix({ derived }: { derived: Derived }) {
  const rows: Row[] = [
    ...derived.variou.map((field) => ({
      campo: field.campo,
      label: labelOf(field.campo, field.rotulo),
      value: (field.valores ?? []).map(capitalizeFirst).join(' → '),
      varied: true,
    })),
    ...derived.ficou_parado.map((field) => ({
      campo: field.campo,
      label: labelOf(field.campo, field.rotulo),
      value:
        field.valor == null || field.valor === 'vazio' ? 'vazio' : capitalizeFirst(field.valor),
      varied: false,
    })),
  ]
  const groups = (Object.keys(groupLabels) as Group[])
    .map((group) => ({ group, rows: rows.filter((row) => groupOf(row.campo) === group) }))
    .filter((entry) => entry.rows.length > 0)

  return (
    <article className="sim-panel flex flex-col gap-5 p-6!">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <h3 className="sim-display text-base font-semibold text-(--sim-brand-ink)">
            O que variou e o que ficou parado
          </h3>
        </div>
      </div>

      <div className="grid gap-x-8 gap-y-6 lg:grid-cols-3">
        {groups.map(({ group, rows: groupRows }) => (
          <div key={group} className="flex min-w-0 flex-col gap-1">
            <h4 className="mb-1 text-xs font-semibold text-(--sim-foreground)">
              {groupLabels[group]}
            </h4>
            <dl className="flex flex-col divide-y divide-(--sim-border) text-sm">
              {groupRows.map((row) => (
                <div key={row.campo} className="flex justify-between gap-3 py-2.5">
                  <dt className="flex items-center gap-1.5 text-(--sim-muted-foreground)">
                    {row.label}
                    {row.varied && <span className="sim-tag normal-case">variou</span>}
                  </dt>
                  <dd
                    className={cn(
                      'text-right font-semibold tabular-nums text-(--sim-brand-ink)',
                      row.value === 'vazio' && 'font-normal text-(--sim-muted-foreground)',
                    )}
                  >
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </article>
  )
}
