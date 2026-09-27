import { Search } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import {
  matchesSearch,
  useRestrictions,
  type RestrictionListItem,
} from '@/features/restrictions/api/get-restrictions'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/utils/cn'
import { formatInteger, formatMWhAsGWh, truncateText } from '@/utils/format'

type RestrictionPickerDialogProps = {
  /** A restrição em uso, marcada como "atual". Sem ela, é a escolha da primeira restrição. */
  currentRestrictionId?: string
  /** O elemento que abre o modal. Sem ele, o link "Trocar de restrição". */
  trigger?: ReactNode
  title?: string
  description?: string
}

/**
 * "Trocar de restrição" sem sair da Nova simulação: o ranking abre num modal e escolher uma
 * restrição troca só a rota. O formulário continua montado, então o que já foi preenchido fica.
 */
export function RestrictionPickerDialog({
  currentRestrictionId,
  trigger,
  title = 'Trocar de restrição',
  description = 'Ordenadas por energia cortada nos últimos 12 meses. O que você já preencheu na simulação continua.',
}: RestrictionPickerDialogProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  // A Nova simulação lê a restrição com fonte eólica: a lista usa a mesma, para os números baterem.
  const restrictionsQuery = useRestrictions({ source: 'eolica', queryConfig: { enabled: open } })

  const items = useMemo(() => {
    const all = restrictionsQuery.data?.itens ?? []
    if (search.trim() === '') return all
    return all.filter((item) => matchesSearch(item, search))
  }, [restrictionsQuery.data, search])

  function choose(item: RestrictionListItem) {
    setOpen(false)
    if (item.id !== currentRestrictionId) navigate(`/restricoes/${item.id}/nova-simulacao`)
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) setSearch('')
      }}
    >
      {trigger ? (
        <DialogTrigger asChild>{trigger}</DialogTrigger>
      ) : (
        <DialogTrigger className="text-sm text-primary hover:underline">{title}</DialogTrigger>
      )}

      <DialogContent className="sm:h-[min(40rem,calc(100dvh-2rem))]">
        <DialogTitle className="sim-display pr-8">{title}</DialogTitle>
        <DialogDescription className="text-xs leading-5 text-(--sim-muted-foreground)">
          {description}
        </DialogDescription>

        <span className="relative mt-4 block shrink-0">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-(--sim-muted-foreground)"
            aria-hidden="true"
          />
          <input
            type="text"
            aria-label="Buscar restrição"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Texto original do ONS ou subestação"
            className="sim-filter-input pr-3 pl-9"
          />
        </span>

        <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
          {restrictionsQuery.isPending ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : restrictionsQuery.isError ? (
            <p className="py-6 text-sm text-warning">
              Não foi possível carregar as restrições: {restrictionsQuery.error.message}
            </p>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-(--sim-muted-foreground)">
              Nenhuma restrição para esta busca.
            </p>
          ) : (
            <ul className="flex flex-col gap-1">
              {items.map((item) => {
                const isCurrent = item.id === currentRestrictionId

                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => choose(item)}
                      aria-current={isCurrent || undefined}
                      title={item.texto}
                      className={cn(
                        'flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors',
                        'focus-visible:ring-2 focus-visible:ring-(--sim-ring) focus-visible:outline-none',
                        isCurrent
                          ? 'border-(--sim-brand) bg-(--sim-sky-soft)/30'
                          : 'border-transparent hover:border-(--sim-border) hover:bg-(--sim-muted)',
                      )}
                    >
                      <span className="sim-rank-number shrink-0">{item.posicao}</span>
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-[0.8125rem] font-bold text-(--sim-brand-ink)">
                            {item.nome_curto ?? truncateText(item.texto, 80)}
                          </span>
                          {isCurrent && <span className="sim-tag">atual</span>}
                        </span>
                        <span className="mt-0.5 block text-xs text-(--sim-muted-foreground)">
                          {item.subestacoes.join(' · ')}
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-xs tabular-nums">
                        <span className="sim-display block text-[0.8125rem] font-semibold text-(--sim-brand-ink)">
                          {formatMWhAsGWh(item.energia_mwh)} GWh
                        </span>
                        <span className="block text-(--sim-muted-foreground)">
                          {formatInteger(item.equipamentos)}{' '}
                          {item.equipamentos === 1 ? 'linha' : 'linhas'}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
