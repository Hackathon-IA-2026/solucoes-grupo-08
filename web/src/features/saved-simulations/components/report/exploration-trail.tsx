import { Link } from 'react-router'
import type { RevisionRow, TrailStep } from '../../api/report'
import { formatDate } from '@/utils/format'

const trailOrigins: Record<TrailStep['origem_do_texto'], string> = {
  nota_da_pessoa: 'Nota da pessoa',
  nota_do_agente: 'Agente',
  resumo_da_configuracao: 'Manual, sem nota',
}

type ExplorationTrailProps = {
  steps: TrailStep[]
  rows: Map<number, RevisionRow>
  /** Para onde "Criar próxima revisão" leva, ou nada quando não há de onde partir. */
  nextRevisionUrl?: string
}

/** As revisões cobertas na ordem em que foram feitas, cada uma com a nota que a explica. */
export function ExplorationTrail({ steps, rows, nextRevisionUrl }: ExplorationTrailProps) {
  return (
    <article className="sim-panel flex min-w-0 flex-col gap-5 p-6!">
      <div className="flex items-center gap-2.5">
        <h3 className="sim-display text-base font-semibold text-(--sim-brand-ink)">
          Trilha da exploração
        </h3>
      </div>

      {steps.length === 0 ? (
        <p className="text-sm text-(--sim-muted-foreground)">Nenhuma revisão coberta.</p>
      ) : (
        <ol className="flex flex-col">
          {steps.map((step) => {
            const row = rows.get(step.revisao_id)
            return (
              <li key={step.revisao_id} className="flex gap-3.5">
                <span className="flex shrink-0 flex-col items-center" aria-hidden="true">
                  <span className="mt-1 size-3 rounded-full bg-(--sim-brand) ring-4 ring-(--sim-sky-soft)" />
                  <span className="mt-1.5 w-0.5 grow bg-(--sim-border)" />
                </span>
                <div className="flex min-w-0 flex-col gap-1.5 pb-5">
                  <p className="flex items-center gap-2">
                    {row ? (
                      <Link
                        to={row.url}
                        className="text-sm font-semibold text-(--sim-brand) hover:underline"
                      >
                        rev {step.posicao}
                      </Link>
                    ) : (
                      <span className="text-sm font-semibold text-(--sim-brand-ink)">
                        rev {step.posicao}
                      </span>
                    )}
                    <span className="text-xs tabular-nums text-(--sim-muted-foreground)">
                      {formatDate(step.criada_em)}
                    </span>
                  </p>
                  <p className="text-sm leading-6 text-(--sim-foreground)">{step.texto}</p>
                  <p className="flex flex-wrap gap-1.5">
                    <span className="rounded-md bg-(--sim-muted) px-2 py-0.5 text-xs text-(--sim-foreground)">
                      {trailOrigins[step.origem_do_texto]}
                    </span>
                    <span className="sim-tag normal-case">Neste relatório</span>
                  </p>
                </div>
              </li>
            )
          })}
          {nextRevisionUrl && (
            <li className="flex gap-3.5">
              <span
                className="mt-1 size-3 shrink-0 rounded-full border-2 border-dashed border-(--sim-muted-foreground)"
                aria-hidden="true"
              />
              <Link
                to={nextRevisionUrl}
                className="text-sm font-semibold text-(--sim-brand) hover:underline"
              >
                Criar próxima revisão
              </Link>
            </li>
          )}
        </ol>
      )}
    </article>
  )
}
