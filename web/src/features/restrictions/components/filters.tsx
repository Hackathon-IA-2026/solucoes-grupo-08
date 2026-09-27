import { CalendarDays, Search, SlidersHorizontal, Wind } from 'lucide-react'
import { useState } from 'react'
import type { Source } from '../api/get-restrictions'
import { cn } from '@/utils/cn'

type FiltersProps = {
  search: string
  onSearchChange: (value: string) => void
  source: Source
  onSourceChange: (value: Source) => void
  period: string
}

const sources: { value: Source; label: string }[] = [
  { value: 'eolica', label: 'Eólica' },
  { value: 'solar', label: 'Solar' },
  { value: 'ambas', label: 'Ambas' },
]

/** Busca, fonte e período. No celular ficam recolhidos atrás do botão de filtros. */
export function Filters({ search, onSearchChange, source, onSourceChange, period }: FiltersProps) {
  const [open, setOpen] = useState(false)

  return (
    <section
      aria-label="Busca e filtros"
      className="rounded-lg border border-(--sim-border) bg-(--sim-surface) p-3 sm:p-4"
    >
      <div className="flex items-center justify-between lg:hidden">
        <span className="text-sm font-bold text-(--sim-brand-ink)">Busca e filtros</span>
        <button
          type="button"
          className="sim-icon-action"
          aria-label="Mostrar filtros"
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <SlidersHorizontal className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div
        className={cn(
          'mt-3 gap-4 lg:mt-0 lg:grid lg:grid-cols-[minmax(260px,1fr)_auto_auto] lg:items-end',
          open ? 'grid' : 'hidden',
        )}
      >
        <label className="block">
          <span className="sim-filter-label">Buscar</span>
          <span className="relative mt-2 block">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-(--sim-muted-foreground)"
              aria-hidden="true"
            />
            <input
              type="text"
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              className="sim-filter-input pr-3 pl-9"
              placeholder="Texto original do ONS ou subestação"
            />
          </span>
        </label>

        <fieldset>
          <legend className="sim-filter-label">Fonte</legend>
          <div
            role="group"
            aria-label="Filtrar por fonte de geração"
            className="mt-2 inline-flex rounded-md bg-(--sim-muted) p-1"
          >
            {sources.map((item) => (
              <button
                key={item.value}
                type="button"
                aria-pressed={source === item.value}
                onClick={() => onSourceChange(item.value)}
                className={cn(
                  'sim-filter-option',
                  source === item.value && 'sim-filter-option-active',
                )}
              >
                {item.value === 'eolica' && <Wind className="size-3.5" aria-hidden="true" />}
                {item.label}
              </button>
            ))}
          </div>
        </fieldset>

        <div>
          <span className="sim-filter-label">Período</span>
          <div className="mt-2 flex h-10 items-center gap-2 rounded-md border border-(--sim-border) bg-(--sim-background) px-3 text-xs font-semibold text-(--sim-brand-ink)">
            <CalendarDays className="size-4 text-(--sim-brand)" aria-hidden="true" />
            {period}
          </div>
        </div>
      </div>
    </section>
  )
}
