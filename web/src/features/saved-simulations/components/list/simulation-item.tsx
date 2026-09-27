import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import type { SimulationListItem } from '../../api/get-simulations'
import { modalityLabels } from '../../api/labels'
import { RevisionsTable } from './revisions-table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'

type SimulationItemProps = {
  simulation: SimulationListItem
  selected: boolean
  onSelectedChange: (selected: boolean) => void
  expanded: boolean
  onToggle: () => void
  /** A revisão atual foi calculada sobre um snapshot que não é o ativo. */
  outdated: boolean
}

/**
 * Uma simulação e o histórico dela. O título e o botão Abrir, no fim do cabeçalho, levam à revisão atual, e logo abaixo dele vai a
 * modalidade, em selo pequeno, com o aviso de dado anterior quando houver. O período não entra: é
 * o mesmo em todas as simulações, e o cabeçalho do app já o mostra.
 */
export function SimulationItem({
  simulation,
  selected,
  onSelectedChange,
  expanded,
  onToggle,
  outdated,
}: SimulationItemProps) {
  const current = simulation.revisoes.find((revision) => revision.atual) ?? simulation.revisoes[0]
  const revisionsLabel = `${simulation.revisoes.length} ${simulation.revisoes.length === 1 ? 'revisão' : 'revisões'}`

  return (
    <section className="sim-card min-w-0">
      <div className="sim-card-head flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4">
        <input
          type="checkbox"
          className="size-4.5 accent-(--sim-brand)"
          aria-label={`Selecionar ${simulation.nome} para comparar`}
          checked={selected}
          onChange={(event) => onSelectedChange(event.target.checked)}
        />

        <div className="flex min-w-0 grow flex-col gap-1.5">
          <Link
            to={`/simulacoes/${current.id}`}
            className="sim-display text-base font-semibold text-(--sim-brand-ink) hover:text-(--sim-brand)"
          >
            {simulation.nome}
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            {simulation.modalidade && (
              <span className="sim-tag px-1.5! py-0.5! text-[9px]!">
                {modalityLabels[simulation.modalidade]}
              </span>
            )}
            {outdated && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0} className="inline-flex">
                    <Badge variant="warning">Calculada com dado ONS anterior</Badge>
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  A revisão atual usou um snapshot que não é mais o ativo. O ONS publicou dado novo;
                  recalcular cria uma revisão com ele.
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-expanded={expanded}
            onClick={onToggle}
            className="inline-flex items-center gap-1.5 whitespace-nowrap px-1 text-xs font-bold text-(--sim-brand)"
          >
            <ChevronRight
              className={cn('size-3.5 transition-transform', expanded && 'rotate-90')}
              aria-hidden="true"
            />
            {revisionsLabel}
          </button>
          {outdated && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled
              title="Depende do envio do formulário, que ainda não está ligado à API"
            >
              Recalcular com o dado novo
            </Button>
          )}
          <Link
            to={`/simulacoes/${current.id}`}
            aria-label={`Abrir ${simulation.nome}`}
            className="sim-btn-secondary"
          >
            Abrir
          </Link>
        </div>
      </div>

      {expanded && <RevisionsTable simulation={simulation} />}
    </section>
  )
}
