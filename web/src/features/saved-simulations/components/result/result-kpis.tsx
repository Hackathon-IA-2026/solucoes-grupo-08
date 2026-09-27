import type { Configuration, Result } from '../../api/get-simulation'
import { KpiCard } from './kpi-card'
import { InfoTooltip } from '@/components/ui/tooltip'
import { formatFractionAsPercent, formatNumber, formatReais } from '@/utils/format'

type ResultKpisProps = {
  result: Result
  configuration: Configuration
}

const gridClass = 'grid gap-3 sm:grid-cols-2 lg:grid-cols-5'

/** Energia: o que a intervenção recuperou do corte histórico. Os números vêm prontos da API. */
export function TechnicalKpis({ result, configuration }: ResultKpisProps) {
  const { tecnico: technical } = result
  const hasBattery = configuration.bateria != null
  const hasCircuit = configuration.equipamento != null

  return (
    <div className={gridClass}>
      <KpiCard
        featured
        label="Energia recuperada"
        value={formatNumber(technical.energia_recuperada_mwh)}
        unit="MWh"
        tooltip="Energia que a intervenção teria evitado cortar nos 12 meses históricos. É a soma do que o circuito evitou com o que a bateria devolveu à rede. Nunca passa da energia cortada."
        note={`${formatFractionAsPercent(technical.fracao_recuperada)} % da energia cortada`}
      />
      <KpiCard
        label="Energia cortada"
        value={formatNumber(technical.energia_cortada_mwh)}
        unit="MWh"
        note="histórico do ONS, 12 meses"
      />
      <KpiCard
        label="Bateria absorveu"
        value={hasBattery ? formatNumber(technical.energia_absorvida_bateria_mwh) : null}
        unit="MWh"
        emptyText="sem bateria"
        note="do corte, nas meias horas com corte"
      />
      <KpiCard
        label="Bateria devolveu"
        value={hasBattery ? formatNumber(technical.energia_devolvida_bateria_mwh) : null}
        unit="MWh"
        emptyText="sem bateria"
        tooltip="Energia que a bateria entregou à rede fora das meias horas com corte. É o absorvido menos as perdas de eficiência. É esta parcela que conta como recuperada."
        note="à rede, fora das meias horas com corte"
      />
      <KpiCard
        label="Circuito evitou"
        value={hasCircuit ? formatNumber(technical.energia_evitada_equipamento_mwh) : null}
        unit="MWh"
        emptyText="sem circuito"
        note="pelo ganho de limite informado"
      />
    </div>
  )
}

type FinancialSummaryProps = ResultKpisProps & {
  /** Posição da revisão, para dizer de qual são as métricas. */
  position: number
}

function MetricRow({
  label,
  value,
  unit,
  tooltip,
  note,
}: {
  label: string
  value: string | null
  unit?: string
  tooltip: string
  note?: string
}) {
  return (
    <div className="sim-finance-row">
      <span className="flex items-center gap-1.5">
        {label}
        <InfoTooltip label={`Ajuda: ${label}`}>{tooltip}</InfoTooltip>
      </span>
      {value === null ? (
        <span className="text-right text-xs italic text-(--sim-muted-foreground)">
          {note ?? '—'}
        </span>
      ) : (
        <strong className="tabular-nums">
          {value}
          {unit && ` ${unit}`}
        </strong>
      )}
    </div>
  )
}

/** Financeiro: VPL, TIR, payback e custo por MWh. `null` da API vira "—", com o motivo. */
export function FinancialSummary({ result, configuration, position }: FinancialSummaryProps) {
  const { financeiro: finance } = result
  const { taxa_desconto_aa, horizonte_anos } = configuration.financeira

  return (
    <section aria-labelledby="retorno-financeiro" className="sim-panel lg:col-span-4">
      <h2 id="retorno-financeiro" className="sim-panel-title">
        Retorno financeiro
      </h2>
      <p className="sim-panel-subtitle mb-4">Métricas de viabilidade da revisão {position}.</p>

      <div className="space-y-3">
        <div className="sim-finance-highlight">
          <span className="flex items-center gap-1.5">
            VPL
            <InfoTooltip label="Ajuda: VPL">
              Valor Presente Líquido: soma de todos os fluxos de caixa do horizonte trazidos a hoje
              pela taxa de desconto, menos o investimento inicial. Positivo indica que o benefício
              supera o custo à taxa escolhida. É a métrica principal.
            </InfoTooltip>
          </span>
          <strong className="tabular-nums">R$ {formatNumber(finance.vpl_reais)}</strong>
          <small>
            a {formatFractionAsPercent(taxa_desconto_aa)} % a.a., {horizonte_anos} anos
          </small>
        </div>

        <MetricRow
          label="TIR"
          value={finance.tir_aa == null ? null : formatFractionAsPercent(finance.tir_aa)}
          unit="% a.a."
          note="não existe no intervalo procurado"
          tooltip="Taxa Interna de Retorno: a taxa de desconto que zera o VPL. Compare com a taxa de desconto informada. Vazio quando o fluxo não tem retorno no intervalo procurado."
        />
        <MetricRow
          label="Payback simples"
          value={
            finance.payback_simples_anos == null
              ? null
              : formatNumber(finance.payback_simples_anos, 1)
          }
          unit="anos"
          note="não se paga no horizonte"
          tooltip="Anos até o fluxo de caixa acumulado, sem desconto, cobrir o investimento. Vazio quando não se paga dentro do horizonte."
        />
        <MetricRow
          label="Payback descontado"
          value={
            finance.payback_descontado_anos == null
              ? null
              : formatNumber(finance.payback_descontado_anos, 1)
          }
          unit="anos"
          note="não se paga no horizonte"
          tooltip="Anos até o fluxo acumulado, trazido a valor presente pela taxa de desconto, cobrir o investimento. Sempre maior que o simples."
        />
        <MetricRow
          label="Custo por MWh recuperado"
          value={
            finance.custo_por_mwh_reais == null
              ? null
              : `${formatReais(finance.custo_por_mwh_reais, 2)}/MWh`
          }
          note="sem energia recuperada"
          tooltip="Investimento mais custos de operação e reposições do horizonte, divididos pela energia recuperada no horizonte. Compare com o preço da energia."
        />
      </div>
    </section>
  )
}
