import type { RestrictionListItem, RestrictionsSummary } from '../api/get-restrictions'
import { InfoTooltip } from '@/components/ui/tooltip'
import { formatInteger, formatMWhAsGWh, formatPercentage, truncateText } from '@/utils/format'

type MetricsProps = {
  summary: RestrictionsSummary
  /** A primeira do ranking, sem filtro de busca. Vem pronta da API, com a fatia dela. */
  top?: RestrictionListItem
}

export function Metrics({ summary, top }: MetricsProps) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Resumo">
      <article className="sim-overview-card">
        <span className="sim-overview-label flex items-center gap-1.5">
          Restrições
          <InfoTooltip label="Ajuda: Restrições">
            Quantas restrições entram no ranking. Restrição é a regra operativa do ONS que limita o
            escoamento de uma linha de transmissão e causa corte de geração. Só entram as de origem
            local e razão confiabilidade elétrica, com equipamento identificado no cadastro.
          </InfoTooltip>
        </span>
        <strong className="sim-overview-value tabular-nums">
          {formatInteger(summary.restricoes)}
        </strong>
        <span className="sim-overview-detail">no ranking</span>
      </article>

      <article className="sim-overview-card sim-overview-card-featured">
        <span className="sim-overview-label flex items-center gap-1.5">
          Energia cortada
          <InfoTooltip label="Ajuda: Energia cortada">
            Soma da geração eólica ou solar que o ONS mandou reduzir nessas restrições, nos 12
            meses, segundo a apuração oficial (GNRa, geração não realizada apurada).
          </InfoTooltip>
        </span>
        <strong className="sim-overview-value tabular-nums">
          {formatMWhAsGWh(summary.energia_mwh)} <small>GWh</small>
        </strong>
        <span className="sim-overview-detail">últimos 12 meses</span>
      </article>

      {top && (
        <div className="hidden lg:block">
          <article className="sim-overview-card h-full">
            <span className="sim-overview-label">Maior restrição</span>
            <strong className="sim-overview-value tabular-nums">
              {formatPercentage(top.fatia_do_total * 100)}%
            </strong>
            <span className="sim-overview-detail" title={top.texto}>
              {top.nome_curto ?? truncateText(top.texto, 40)}
            </span>
          </article>
        </div>
      )}
    </section>
  )
}
