import type { ReportHeader } from '../../api/report'
import { SectionHeading } from './report-section'
import { sourceLabels } from '@/features/restrictions/api/get-restrictions'
import {
  capitalizeFirst,
  formatFractionAsPercent,
  formatInteger,
  formatNumber,
} from '@/utils/format'

// Uma cor por fonte, fixa: a cor segue a fonte, nunca a posição.
const sourceColors: Record<string, string> = {
  eolica: 'var(--sim-brand)',
  solar: '#d97706',
  ambas: '#0f766e',
}

function Figure({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="sim-summary flex flex-col gap-1.5 px-5 py-5">
      <p className="text-xs text-(--sim-muted-foreground)">{label}</p>
      {children}
    </div>
  )
}

/**
 * O tamanho do corte no período, para ler o resultado em proporção. O fundo cinza da barra é o
 * que as fontes com corte não cobrem: a tela não soma nem subtrai fatias.
 */
export function CurtailmentContext({ header }: { header: ReportHeader }) {
  const shares = header.fatia_por_fonte
  const described = shares
    .map(
      (share) =>
        `${capitalizeFirst(sourceLabels[share.fonte])} ${formatFractionAsPercent(share.fatia)} %`,
    )
    .join(', ')

  return (
    <section aria-labelledby="contexto" className="flex flex-col gap-3">
      <SectionHeading id="contexto" title="Contexto do corte no período" />
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr_2fr]">
        <Figure label="Energia cortada">
          <p className="flex items-baseline gap-1.5">
            <span className="sim-display text-2xl font-semibold tabular-nums text-(--sim-brand-ink)">
              {formatNumber(header.energia_cortada_mwh)}
            </span>
            <span className="text-sm text-(--sim-muted-foreground)">MWh</span>
          </p>
        </Figure>
        <Figure label="Ocorrências de corte">
          <p className="sim-display text-2xl font-semibold tabular-nums text-(--sim-brand-ink)">
            {formatInteger(header.ocorrencias.total)}
          </p>
        </Figure>
        <Figure label="Fatia do ranking, por fonte">
          <div
            role="img"
            aria-label={`${described}; o restante são as demais restrições`}
            className="mt-1.5 flex h-3 gap-0.5 overflow-hidden rounded-full bg-(--sim-border)"
          >
            {shares.map((share) => (
              <div
                key={share.fonte}
                style={{
                  width: `${share.fatia * 100}%`,
                  background: sourceColors[share.fonte] ?? 'var(--sim-brand)',
                }}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1.5 text-xs text-(--sim-foreground)">
            {shares.map((share) => (
              <span key={share.fonte} className="inline-flex items-center gap-1.5">
                <span
                  className="size-2.5 rounded-xs"
                  style={{ background: sourceColors[share.fonte] ?? 'var(--sim-brand)' }}
                  aria-hidden="true"
                />
                {capitalizeFirst(sourceLabels[share.fonte])}{' '}
                <strong className="tabular-nums text-(--sim-brand-ink)">
                  {formatFractionAsPercent(share.fatia)} %
                </strong>
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-xs bg-(--sim-border)" aria-hidden="true" />
              Demais
            </span>
          </div>
        </Figure>
      </div>
    </section>
  )
}
