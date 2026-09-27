import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { DetailedRestriction } from '../api/get-restriction'
import { InfoTooltip } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'
import { formatInteger, formatMWhAsGWh, formatPercentage } from '@/utils/format'

type RestrictionDetailMetricsProps = {
  item: DetailedRestriction
}

type CellProps = {
  label: ReactNode
  emphasized?: boolean
  children: ReactNode
}

function Cell({ label, emphasized = false, children }: CellProps) {
  return (
    <div
      className={cn(
        'min-h-28 border-t border-(--sim-border) p-5 sm:border-l lg:border-t-0 lg:first:border-l-0',
        emphasized && 'bg-(--sim-sky-soft)/30',
      )}
    >
      <p
        className={cn(
          'sim-overview-label flex items-center gap-1.5',
          emphasized && 'text-(--sim-brand)!',
        )}
      >
        {label}
      </p>
      {children}
    </div>
  )
}

function Value({ children, unit }: { children: ReactNode; unit?: string }) {
  return (
    <div className="mt-3 flex items-baseline gap-1.5">
      <strong className="sim-display text-2xl font-semibold tabular-nums text-(--sim-brand-ink)">
        {children}
      </strong>
      {unit && <span className="text-xs font-bold text-(--sim-muted-foreground)">{unit}</span>}
    </div>
  )
}

export function RestrictionDetailMetrics({ item }: RestrictionDetailMetricsProps) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4">
      <Cell
        emphasized
        label={
          <>
            Energia cortada, 12 meses
            <InfoTooltip label="Ajuda: Energia cortada, 12 meses">
              Geração que o ONS mandou reduzir por causa desta restrição na janela analisada,
              segundo a apuração oficial.
            </InfoTooltip>
          </>
        }
      >
        <Value unit="GWh">{formatMWhAsGWh(item.energia_mwh)}</Value>
      </Cell>

      <Cell label="Fatia do universo">
        <Value>{formatPercentage(item.fatia_do_total * 100)}%</Value>
      </Cell>

      <Cell label="Linhas">
        <Value>{formatInteger(item.equipamentos.length)}</Value>
        <p className="mt-1 text-xs text-(--sim-muted-foreground)">
          {formatInteger(item.subestacoes.length)} subestações
        </p>
      </Cell>

      <Cell label="Avisos vigentes">
        {item.avisos.length === 0 ? (
          <div className="mt-4 flex items-center gap-2 text-sm font-bold text-(--sim-positive)">
            <span className="size-2 rounded-full bg-(--sim-positive)" aria-hidden="true" />
            Nenhum aviso vigente
          </div>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {item.avisos.map((warning) => (
              <li
                key={warning.codigo}
                className="flex items-start gap-1.5 text-xs font-medium leading-5 text-warning"
              >
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                {warning.mensagem}
              </li>
            ))}
          </ul>
        )}
      </Cell>
    </div>
  )
}
