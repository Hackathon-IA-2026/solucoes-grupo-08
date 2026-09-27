import { AlertCircle } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'
import { useRestriction } from '@/features/restrictions/api/get-restriction'
import { useSimulation, type FullRevision } from '@/features/saved-simulations/api/get-simulation'
import { CompareColumns } from '@/features/saved-simulations/components/compare/compare-columns'
import { compareSections } from '@/features/saved-simulations/components/compare/compare-rows'
import { CompareTable } from '@/features/saved-simulations/components/compare/compare-table'
import { Breadcrumbs } from '@/components/layout/breadcrumbs'
import { Spinner } from '@/components/ui/spinner'
import { formatSnapshotId } from '@/utils/format'

function Notice({ title, children }: { title: string; children: string }) {
  return (
    <div className="sim-page">
      <div className="mx-auto max-w-screen-2xl px-4 py-16 text-center sm:px-6 lg:px-8">
        <p className="sim-display text-base font-semibold text-(--sim-brand-ink)">{title}</p>
        <p className="mt-1 text-sm text-(--sim-muted-foreground)">{children}</p>
        <Link to="/simulacoes" className="sim-btn-secondary mt-4">
          Escolher em Simulações
        </Link>
      </div>
    </div>
  )
}

function differenceMessage(a: FullRevision, b: FullRevision): string | null {
  if (a.snapshot_id === b.snapshot_id) return null
  return `As duas revisões foram calculadas sobre snapshots diferentes do ONS: versão ${formatSnapshotId(a.snapshot_id)} e versão ${formatSnapshotId(b.snapshot_id)}. O corte histórico não é o mesmo nas duas, e as diferenças abaixo misturam hipótese com dado.`
}

/**
 * Duas revisões lado a lado: `?a=<revisão>&b=<revisão>`. Exige a mesma restrição, porque comparar
 * a recuperação de gargalos diferentes soma o que não se soma. Sem vencedor declarado.
 */
export default function SimulationCompare() {
  const [params] = useSearchParams()
  const idA = Number(params.get('a'))
  const idB = Number(params.get('b'))
  const valid = Number.isInteger(idA) && Number.isInteger(idB) && idA > 0 && idB > 0

  const queryA = useSimulation({ revisionId: valid ? idA : Number.NaN })
  const queryB = useSimulation({ revisionId: valid ? idB : Number.NaN })
  const restriction = useRestriction({ restrictionId: queryA.data?.restricao_id ?? '' })

  if (!valid) {
    return (
      <Notice title="Escolha duas revisões para comparar">
        Marque duas simulações, ou use "rev N contra rev M" dentro de uma simulação.
      </Notice>
    )
  }
  if (idA === idB) {
    return (
      <Notice title="A e B são a mesma revisão">
        Escolha duas revisões diferentes para comparar.
      </Notice>
    )
  }

  if (queryA.isPending || queryB.isPending) {
    return (
      <div className="sim-page">
        <div className="flex justify-center px-6 py-16">
          <Spinner />
        </div>
      </div>
    )
  }
  if (queryA.isError || queryB.isError) {
    const message = (queryA.error ?? queryB.error)?.message
    return (
      <Notice title="Não foi possível carregar as revisões">
        {message ?? 'Erro desconhecido.'}
      </Notice>
    )
  }

  const a = queryA.data
  const b = queryB.data
  if (a.restricao_id !== b.restricao_id) {
    return (
      <Notice title="Restrições diferentes">
        Só é possível comparar revisões da mesma restrição.
      </Notice>
    )
  }

  const lineName = (side: FullRevision) =>
    restriction.data?.equipamentos.find(
      (row) => row.cod_equipamento === side.configuracao.equipamento?.cod_equipamento,
    )?.nome ?? undefined
  const difference = differenceMessage(a, b)

  return (
    <div className="sim-page">
      <main className="mx-auto flex max-w-screen-2xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
        <Breadcrumbs items={[{ label: 'Simulações', to: '/simulacoes' }, { label: 'Comparar' }]} />

        <section className="flex flex-col gap-4 border-b border-(--sim-border) pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex min-w-0 flex-col gap-2">
            <h1 className="sim-display text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
              Comparar duas revisões
            </h1>
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
              <span className="sim-eyebrow text-(--sim-muted-foreground)">Restrição</span>
              <Link
                to={`/restricoes/${a.restricao_id}`}
                title={restriction.data?.texto}
                className="max-w-full truncate text-xs uppercase text-(--sim-brand) hover:underline sm:max-w-190"
              >
                {restriction.data?.texto ?? `restrição ${a.restricao_id}`}
              </Link>
            </div>
          </div>
          <Link to="/simulacoes" className="sim-btn-primary shrink-0">
            Trocar a seleção
          </Link>
        </section>

        {difference && (
          <div
            role="note"
            className="flex items-start gap-3 rounded-lg border border-(--sim-alert) bg-(--sim-alert-soft) px-4 py-3"
          >
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-(--sim-alert)" aria-hidden="true" />
            <span className="text-xs leading-5 text-(--sim-muted-foreground)">{difference}</span>
          </div>
        )}

        <CompareColumns a={a} b={b} />
        <CompareTable
          sections={compareSections(
            { revision: a, lineName: lineName(a) },
            { revision: b, lineName: lineName(b) },
          )}
        />
      </main>
    </div>
  )
}
