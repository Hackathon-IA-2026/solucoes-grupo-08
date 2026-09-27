import type { DetailedRestriction } from '@/features/restrictions/api/get-restriction'
import { formatInteger, truncateText } from '@/utils/format'

type SimulationSummaryBarProps = {
  restriction: DetailedRestriction
}

/** A faixa do topo da Nova simulação: o que está sendo simulado, sobre qual restrição. */
export function SimulationSummaryBar({ restriction }: SimulationSummaryBarProps) {
  const equipmentCount = restriction.equipamentos.length

  return (
    <div className="border-b border-(--sim-border) bg-(--sim-surface)">
      <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-3 text-xs text-(--sim-muted-foreground) sm:px-6 lg:px-8">
        <span className="sim-chip">Nova simulação</span>
        <span className="sim-display text-sm font-semibold text-(--sim-brand-ink)">
          {restriction.nome_curto ?? truncateText(restriction.texto, 60)}
        </span>
        <span aria-hidden="true">·</span>
        <span>
          {formatInteger(equipmentCount)} {equipmentCount === 1 ? 'linha' : 'linhas'}
        </span>
        <span aria-hidden="true">·</span>
        <span>set/2025 a ago/2026</span>
      </div>
    </div>
  )
}
