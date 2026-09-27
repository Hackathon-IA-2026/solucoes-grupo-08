import type { ReactNode } from 'react'
import { InfoTooltip } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'

type KpiCardProps = {
  label: string
  /** O valor, já formatado. `null` mostra o estado sem valor (`emptyText`). */
  value: ReactNode | null
  unit?: string
  /** Explica o conceito. A nota (`note`) continua dizendo de onde o número vem. */
  tooltip?: string
  note?: ReactNode
  /** O número de entrada da linha: faixa azul na borda esquerda. */
  featured?: boolean
  emptyText?: string
}

/** Um número do resultado, com rótulo, unidade e uma nota de onde ele vem. */
export function KpiCard({
  label,
  value,
  unit,
  tooltip,
  note,
  featured,
  emptyText = '—',
}: KpiCardProps) {
  return (
    <div className={cn('sim-metric', featured && 'sim-metric-featured')}>
      <p className="sim-metric-label flex items-center gap-1.5">
        {label}
        {tooltip && <InfoTooltip label={`Ajuda: ${label}`}>{tooltip}</InfoTooltip>}
      </p>
      <p className="sim-metric-value mt-4 tabular-nums">
        {value === null ? (
          emptyText.charAt(0).toUpperCase() + emptyText.slice(1)
        ) : (
          <>
            {value}
            {unit && (
              <span className="ml-1 text-xs font-semibold text-(--sim-muted-foreground)">
                {unit}
              </span>
            )}
          </>
        )}
      </p>
      {note && <p className="mt-2 text-xs leading-5 text-(--sim-muted-foreground)">{note}</p>}
    </div>
  )
}
