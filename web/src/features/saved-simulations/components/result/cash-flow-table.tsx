import type { Result } from '../../api/get-simulation'
import { HeaderTooltip } from '@/components/ui/tooltip'
import { formatNumber } from '@/utils/format'

const columns: { key: string; label: string; tooltip?: string }[] = [
  {
    key: 'beneficio_bruto_reais',
    label: 'Benefício bruto (R$)',
    tooltip: 'Energia recuperada no ano vezes o preço da energia.',
  },
  { key: 'receitas_adicionais_reais', label: 'Receitas adicionais (R$)' },
  { key: 'opex_reais', label: 'Custo de operação (R$)' },
  { key: 'reposicoes_reais', label: 'Reposições (R$)' },
  {
    key: 'fluxo_liquido_reais',
    label: 'Fluxo líquido (R$)',
    tooltip:
      'Benefício bruto mais receitas adicionais, menos custo de operação e reposições. No último ano soma o valor residual.',
  },
  {
    key: 'fluxo_descontado_reais',
    label: 'Fluxo descontado (R$)',
    tooltip:
      'Fluxo líquido do ano trazido a valor presente: dividido por (1 + taxa) elevado ao ano.',
  },
  { key: 'acumulado_reais', label: 'Acumulado (R$)' },
  { key: 'acumulado_descontado_reais', label: 'Acumulado descontado (R$)' },
]

/** O fluxo de caixa ano a ano, do ano 0 (investimento) ao horizonte. Tudo pronto na API. */
export function CashFlowTable({ result }: { result: Result }) {
  const { fluxos: cashFlows } = result.financeiro

  return (
    <section id="fluxo" className="sim-panel">
      <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="sim-panel-title">Fluxo de caixa, ano a ano</h2>
          <p className="sim-panel-subtitle">Valores nominais e descontados em reais.</p>
        </div>
      </div>

      {cashFlows.length === 0 ? (
        <p className="text-sm text-(--sim-muted-foreground)">
          A revisão não trouxe fluxo de caixa.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="sim-table w-full min-w-275 text-xs tabular-nums">
            <thead>
              <tr>
                <th>Ano</th>
                {columns.map((column) => (
                  <th key={column.key}>
                    {column.tooltip ? (
                      <HeaderTooltip label={column.label}>{column.tooltip}</HeaderTooltip>
                    ) : (
                      column.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cashFlows.map((cashFlow) => (
                <tr key={cashFlow.ano}>
                  <td>{cashFlow.ano}</td>
                  {columns.map((column) => (
                    <td key={column.key}>
                      {formatNumber(cashFlow[column.key as keyof typeof cashFlow])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
