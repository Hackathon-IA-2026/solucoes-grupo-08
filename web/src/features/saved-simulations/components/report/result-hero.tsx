import { BatteryCharging, Cable, TriangleAlert } from 'lucide-react'
import type { Derived, ReportHeader, RevisionRow } from '../../api/report'
import { modalityLabels } from '../../api/labels'
import { fieldValues, formatReaisShort, readReais, SUSPICIOUS_CAPEX_REAIS } from './report-format'
import { SectionHeading } from './report-section'
import { formatFractionAsPercent, formatNumber, formatReais } from '@/utils/format'

type ResultHeroProps = {
  row: RevisionRow
  header: ReportHeader | null
  derived: Derived | null
}

/** O resultado da revisão mais nova coberta: energia, VPL e o que se instalou. */
export function ResultHero({ row, header, derived }: ResultHeroProps) {
  const npv = formatReaisShort(row.vpl_reais)
  const horizon = fieldValues(derived, 'financeira.horizonte_anos')
  const rate = fieldValues(derived, 'financeira.taxa_desconto_aa')
  const capex = fieldValues(derived, 'financeira.capex_reais')
  const suspiciousCapex = capex.filter((value) => {
    const reais = readReais(value)
    return reais != null && reais < SUSPICIOUS_CAPEX_REAIS
  })
  const Icon = row.modalidade === 'equipamento' ? Cable : BatteryCharging

  return (
    <section aria-labelledby="resultado" className="flex flex-col gap-3">
      <SectionHeading id="resultado" title={`Resultado da intervenção · rev ${row.posicao}`} />
      <div className="sim-card grid lg:grid-cols-[1.4fr_1fr_1fr]">
        <div className="flex flex-col gap-3.5 border-b border-(--sim-border) p-6 lg:border-r lg:border-b-0 lg:p-7">
          <p className="text-sm font-semibold text-(--sim-foreground)">Energia recuperada</p>
          <p className="flex items-baseline gap-2">
            <span className="sim-display text-4xl font-semibold tabular-nums text-(--sim-brand-ink)">
              {formatNumber(row.energia_recuperada_mwh)}
            </span>
            <span className="text-sm text-(--sim-muted-foreground)">MWh</span>
          </p>
          <div
            className="sim-bar h-2.5!"
            role="img"
            aria-label={`${formatFractionAsPercent(row.fracao_recuperada)} % da energia cortada foi recuperada`}
          >
            <div
              className="min-w-2"
              style={{ width: `${Math.min(100, row.fracao_recuperada * 100)}%` }}
            />
          </div>
          <p className="text-xs text-(--sim-muted-foreground)">
            <span className="font-semibold tabular-nums text-(--sim-brand-ink)">
              {formatFractionAsPercent(row.fracao_recuperada)} %
            </span>{' '}
            {header ? (
              <>
                dos{' '}
                <span className="tabular-nums">{formatNumber(header.energia_cortada_mwh)} MWh</span>{' '}
                cortados no período
              </>
            ) : (
              'da energia cortada no período'
            )}
          </p>
        </div>

        <div className="flex flex-col gap-3.5 border-b border-(--sim-border) p-6 lg:border-r lg:border-b-0 lg:p-7">
          <p className="text-sm font-semibold text-(--sim-foreground)">Valor presente líquido</p>
          <p className="flex items-baseline gap-2">
            <span className="text-sm text-(--sim-muted-foreground)">R$</span>
            <span className="sim-display text-4xl font-semibold tabular-nums text-(--sim-brand-ink)">
              {npv.amount}
            </span>
            {npv.scale && (
              <span className="text-sm text-(--sim-muted-foreground)">{npv.scale}</span>
            )}
          </p>
          <p className="text-xs leading-5 text-(--sim-muted-foreground)">
            <span className="tabular-nums">{formatReais(row.vpl_reais, 2)}</span>
            {(horizon.length > 0 || rate.length > 0) && (
              <>
                <br />
                {[
                  horizon.length > 0 && `horizonte de ${horizon.join(' · ')}`,
                  rate.length > 0 && `desconto de ${rate.join(' · ')}`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </>
            )}
          </p>
        </div>

        <div className="flex flex-col gap-3.5 bg-(--sim-background)/60 p-6 lg:p-7">
          <p className="text-sm font-semibold text-(--sim-foreground)">Intervenção avaliada</p>
          <div className="flex items-center gap-3">
            <span
              className="grid size-11 shrink-0 place-items-center rounded-lg bg-(--sim-sky-soft) text-(--sim-brand)"
              aria-hidden="true"
            >
              <Icon className="size-5" />
            </span>
            <div className="min-w-0">
              <p className="sim-display text-base font-semibold text-(--sim-brand-ink)">
                {modalityLabels[row.modalidade]}
              </p>
              <p className="text-sm tabular-nums text-(--sim-foreground)">{row.alavanca}</p>
            </div>
          </div>
          {suspiciousCapex.length > 0 && (
            <p
              role="note"
              className="flex items-start gap-2 rounded-lg bg-(--sim-alert-soft) px-3 py-2.5 text-xs leading-5 text-(--sim-foreground)"
            >
              <TriangleAlert
                className="mt-0.5 size-4 shrink-0 text-(--sim-alert)"
                aria-hidden="true"
              />
              <span>
                Investimento inicial registrado de{' '}
                <strong className="tabular-nums">{suspiciousCapex.join(' · ')}</strong>. Confira as
                premissas de custo.
              </span>
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
