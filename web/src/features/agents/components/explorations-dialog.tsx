import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useTasks } from '../api/exploration'
import { ExplorationList } from './exploration-list'
import { NewExplorationForm } from './new-exploration-form'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/utils/cn'

type ExplorationsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  simulationId: number
  /** A revisão de onde se chegou é a partida da nova exploração. */
  revisionId: number
}

/**
 * As explorações da simulação num modal, da mais nova para a mais velha. "Nova exploração" troca
 * a lista pelo campo do pedido, no mesmo modal. A API aceita uma em andamento por simulação: com
 * uma rodando, o botão leva a ela em vez de começar outra. A lista só é buscada com o modal aberto.
 */
export function ExplorationsDialog({
  open,
  onOpenChange,
  simulationId,
  revisionId,
}: ExplorationsDialogProps) {
  const [creating, setCreating] = useState(false)
  const tasks = useTasks(simulationId, { enabled: open })
  const running = tasks.data?.find((task) => task.estado === 'em_andamento')

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next)
        // Reabrir começa pela lista.
        if (!next) setCreating(false)
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        {/* pr-8: o X de fechar do modal fica no canto, e o botão não pode ficar sob ele. */}
        <div className="flex items-center justify-between gap-4 pr-8">
          <div className="min-w-0">
            <DialogTitle className="sim-display text-(--sim-brand-ink)">
              {creating ? 'Nova exploração' : 'Explorações'}
            </DialogTitle>
            <DialogDescription className="mt-1 text-(--sim-muted-foreground)">
              {creating
                ? 'Descreva o que os agentes devem explorar a partir desta revisão.'
                : 'Os agentes partem de uma revisão, testam variações e salvam cada uma como revisão nova desta simulação.'}
            </DialogDescription>
          </div>
          {!creating &&
            (running ? (
              <Link
                to={`/simulacoes/${simulationId}/exploracoes/${running.id}`}
                className="sim-btn-primary shrink-0"
              >
                Acompanhar a exploração {running.id}
              </Link>
            ) : (
              <button
                type="button"
                onClick={() => setCreating(true)}
                disabled={tasks.isPending}
                className={cn('sim-btn-primary shrink-0 gap-2', tasks.isPending && 'opacity-60')}
              >
                <Plus className="size-4" aria-hidden="true" />
                Nova exploração
              </button>
            ))}
        </div>
        <div className="mt-4 flex flex-col gap-3">
          {creating ? (
            <NewExplorationForm
              simulationId={simulationId}
              revisionId={revisionId}
              onCancel={() => setCreating(false)}
            />
          ) : (
            <ExplorationList tasks={tasks} onNew={() => setCreating(true)} inDialog />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
