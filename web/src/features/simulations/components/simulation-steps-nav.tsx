import { Check } from 'lucide-react'
import { cn } from '@/utils/cn'

/** A etapa que a rota mostra. O número é o mesmo do item na sidebar. */
export type SimulationStep = 1 | 2 | 3 | 4 | 5

type StepConfig = {
  step: SimulationStep
  title: string
  subtitle: string
}

const steps: StepConfig[] = [
  { step: 1, title: 'Identificação', subtitle: 'Nome que você vai procurar depois' },
  { step: 2, title: 'Período', subtitle: '12 meses completos, fixo' },
  { step: 3, title: 'Modalidade', subtitle: 'Bateria, circuito ou as duas' },
  { step: 4, title: 'Configuração técnica', subtitle: 'Bateria, ponto de conexão, ordem' },
  { step: 5, title: 'Premissas financeiras', subtitle: 'Cenário de partida: referência' },
]

type SimulationStepsNavProps = {
  currentStep: SimulationStep
  simulationName: string
  onStepChange: (step: SimulationStep) => void
}

export function SimulationStepsNav({
  currentStep,
  simulationName,
  onStepChange,
}: SimulationStepsNavProps) {
  return (
    <nav
      aria-label="Etapas"
      className="flex max-w-full shrink-0 gap-1 self-stretch overflow-x-auto lg:self-start p-2 lg:w-72 lg:flex-col lg:overflow-visible"
    >
      {steps.map((item) => {
        const isCurrent = item.step === currentStep
        const isDone = item.step < currentStep
        const subtitle = item.step === 1 && isDone ? simulationName : item.subtitle

        return (
          <button
            key={item.step}
            type="button"
            onClick={() => onStepChange(item.step)}
            aria-current={isCurrent ? 'step' : undefined}
            className={cn(
              'flex min-w-52 items-start gap-3 rounded-md px-3 py-2.5 text-left transition-colors lg:min-w-0',
              isCurrent ? 'bg-primary-light' : 'hover:bg-(--sim-muted)',
            )}
          >
            <span
              className={cn(
                'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border text-[0.7rem] font-bold',
                isDone && 'border-success bg-success text-white',
                isCurrent && !isDone && 'border-primary text-primary',
                !isCurrent && !isDone && 'border-border text-text-secondary',
              )}
            >
              {isDone ? <Check className="h-3 w-3" aria-hidden="true" /> : item.step}
            </span>
            <span className="min-w-0">
              <span
                className={cn(
                  'block text-sm font-semibold',
                  isCurrent ? 'text-primary' : 'text-text-primary',
                )}
              >
                {item.title}
              </span>
              <span className="block truncate text-xs text-text-muted">{subtitle}</span>
            </span>
          </button>
        )
      })}
    </nav>
  )
}
