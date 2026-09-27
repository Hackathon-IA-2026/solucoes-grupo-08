import { Check, FileText, LoaderCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/utils/cn'

// Só apresentação. A API não devolve progresso, então nenhuma etapa aqui diz que algo terminou
// de verdade: a sequência anda por tempo e, ao chegar na última, fica nela até os dados
// chegarem. Quando chegam, este componente deixa de ser renderizado e o relatório aparece.
const STEPS = [
  'Preparando seu relatório',
  'Analisando informações',
  'Organizando resultados',
  'Finalizando relatório',
]
const STEP_MS = 2500

type ReportLoadingProps = {
  title: string
  /** Chamado quando a sequência chega na última etapa. */
  onLastStep?: () => void
}

export function ReportLoading({ title, onLastStep }: ReportLoadingProps) {
  const [active, setActive] = useState(0)

  useEffect(() => {
    if (active === STEPS.length - 1) onLastStep?.()
  }, [active, onLastStep])

  useEffect(() => {
    if (active >= STEPS.length - 1) return
    const timer = window.setTimeout(() => setActive((current) => current + 1), STEP_MS)
    return () => window.clearTimeout(timer)
  }, [active])

  return (
    <div
      role="status"
      aria-live="polite"
      className="sim-card mx-auto flex w-full max-w-md flex-col items-center px-6 py-10 text-center sm:px-10"
    >
      <span
        className="grid size-12 place-items-center rounded-lg bg-(--sim-sky-soft) text-(--sim-brand)"
        aria-hidden="true"
      >
        <FileText className="size-6" />
      </span>
      <p className="sim-eyebrow mt-5 text-(--sim-brand)">Relatório</p>
      <h2 className="sim-display mt-2 text-2xl font-semibold text-(--sim-brand-ink)">{title}</h2>
      <p className="mt-2 text-sm text-(--sim-muted-foreground)">
        Estamos preparando seus resultados.
      </p>

      <ol className="mt-7 flex w-full flex-col gap-1 text-left">
        {STEPS.map((step, index) => {
          const done = index < active
          const current = index === active

          return (
            <li
              key={step}
              aria-current={current ? 'step' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm',
                done && 'text-(--sim-foreground)',
                current &&
                  'bg-[color-mix(in_oklab,var(--sim-sky-soft)_55%,var(--sim-surface))] font-semibold text-(--sim-brand-ink)',
                !done && !current && 'text-(--sim-muted-foreground)',
              )}
            >
              <span
                className={cn(
                  'flex size-5 shrink-0 items-center justify-center rounded-full border',
                  done && 'border-success bg-success text-white',
                  current && 'border-(--sim-brand) text-(--sim-brand)',
                  !done && !current && 'border-(--sim-border)',
                )}
                aria-hidden="true"
              >
                {done ? (
                  <Check className="size-3" />
                ) : current ? (
                  <LoaderCircle className="size-3.5 motion-safe:animate-spin" />
                ) : null}
              </span>
              {current && index === STEPS.length - 1 ? `${step}…` : step}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
