import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useTasks } from '@/features/agents/api/exploration'
import { NewExplorationForm } from '@/features/agents/components/new-exploration-form'
import { ExplorationList } from '@/features/agents/components/exploration-list'
import { useSimulationCrumb } from '@/features/saved-simulations/api/simulation-crumb'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'
import { cn } from '@/utils/cn'

/**
 * As explorações da simulação, da mais nova para a mais velha, e o caminho para criar uma. A API
 * aceita uma em andamento por simulação: com uma rodando, "Nova exploração" leva a ela.
 */
export default function SimulationExplorations() {
  const simulationId = Number(useParams().simulacaoId)
  // A revisão de onde se chegou (a tela de resultado) vira a partida sugerida da nova exploração.
  const revision = useSearchParams()[0].get('revisao')
  const tasks = useTasks(simulationId)
  // Chegando do resultado, o nível da simulação volta para a revisão de onde se veio.
  const simulationCrumb = useSimulationCrumb(simulationId, revision ? Number(revision) : undefined)
  const running = tasks.data?.find((task) => task.estado === 'em_andamento')
  const [creating, setCreating] = useState(false)

  return (
    <div className="sim-page">
      <main className="mx-auto flex max-w-screen-2xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
        <Breadcrumbs
          items={[
            { label: 'Simulações', to: '/simulacoes' },
            simulationCrumb,
            { label: 'Explorações' },
          ]}
        />

        <section className="flex flex-col gap-4 border-b border-(--sim-border) pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="sim-eyebrow text-(--sim-brand)">Com agentes</p>
            <h1 className="sim-display mt-1 text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
              Explorações
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-(--sim-muted-foreground)">
              Os agentes partem de uma revisão, testam variações e salvam cada uma como revisão nova
              desta simulação.
            </p>
          </div>
          {running ? (
            <Link
              to={`/simulacoes/${simulationId}/exploracoes/${running.id}`}
              className="sim-btn-primary"
            >
              Acompanhar a exploração {running.id}
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => setCreating(true)}
              disabled={tasks.isPending}
              className={cn('sim-btn-primary gap-2', tasks.isPending && 'opacity-60')}
            >
              <Plus className="size-4" aria-hidden="true" />
              Nova exploração
            </button>
          )}
        </section>

        {running && (
          <p className="text-xs text-(--sim-muted-foreground)">
            Uma exploração por vez em cada simulação: a nova pode começar quando a {running.id}{' '}
            terminar.
          </p>
        )}

        <ExplorationList tasks={tasks} onNew={() => setCreating(true)} />

        <Dialog open={creating} onOpenChange={setCreating}>
          <DialogContent>
            <DialogTitle className="sim-display text-(--sim-brand-ink)">
              Nova exploração
            </DialogTitle>
            <DialogDescription className="mb-4 text-(--sim-muted-foreground)">
              Descreva o que os agentes devem explorar a partir desta revisão.
            </DialogDescription>
            <NewExplorationForm
              simulationId={simulationId}
              revisionId={revision ? Number(revision) : undefined}
              onCancel={() => setCreating(false)}
            />
          </DialogContent>
        </Dialog>
      </main>
    </div>
  )
}
