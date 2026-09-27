import { Controller, useFormContext } from 'react-hook-form'
import { modalityOptions } from '../api/simulation-modality'
import type { SimulationFormData } from '../form/schema'
import { FieldError } from './form-field'
import { ModalityIllustration } from './modality-illustration'
import { Button } from '@/components/ui/button'
import { InfoTooltip } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'

type StepModalityProps = {
  onBack: () => void
  onContinue: () => void
}

export function StepModality({ onBack, onContinue }: StepModalityProps) {
  const { control } = useFormContext<SimulationFormData>()

  return (
    <div>
      <h1 className="flex items-center gap-1.5 text-xl font-semibold text-text-primary">
        3. Modalidade
        <InfoTooltip label="Ajuda: Modalidade">
          Tipo de intervenção hipotética que o cálculo aplica sobre o histórico: bateria, adição de
          circuito, ou as duas. Na combinada o circuito reduz o corte primeiro e a bateria atua
          sobre o que sobra.
        </InfoTooltip>
      </h1>

      <Controller
        control={control}
        name="step3.modalidade"
        render={({ field }) => (
          <div role="radiogroup" aria-label="Modalidade" className="mt-6 grid gap-4 lg:grid-cols-3">
            {modalityOptions.map((option) => {
              const isSelected = option.id === field.value

              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => field.onChange(option.id)}
                  className={cn(
                    'relative flex flex-col items-start rounded-lg border bg-surface p-5 text-left transition-colors',
                    isSelected
                      ? 'border-primary ring-1 ring-primary'
                      : 'border-border hover:border-text-muted',
                  )}
                >
                  <ModalityIllustration modality={option.id} />
                  <span
                    className={cn(
                      'absolute top-4 right-4 h-4 w-4 rounded-full border-2',
                      isSelected ? 'border-primary bg-primary' : 'border-border bg-surface',
                    )}
                    aria-hidden="true"
                  />

                  <h2 className="mt-4 text-sm font-semibold text-text-primary">{option.title}</h2>
                  <p className="mt-1.5 text-sm text-text-secondary">{option.description}</p>
                  <p className="mt-2 text-sm text-text-muted">{option.caption}</p>
                </button>
              )
            })}
          </div>
        )}
      />
      <FieldError name="step3.modalidade" />

      <div className="mt-4 rounded-lg border border-border bg-surface p-6">
        <h2 className="text-sm font-medium text-text-primary">O que a escolha muda adiante</h2>
        <p className="mt-1.5 text-sm text-text-secondary">
          Bateria: ponto de conexão obrigatório na etapa 5. Adição de circuito: a etapa 4 pede qual
          linha recebe o circuito novo e a configuração de cada uma. Combinação: as duas, mais a
          ordem de aplicação.
        </p>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Voltar
        </Button>
        <Button type="button" onClick={onContinue}>
          Continuar para configuração técnica
        </Button>
      </div>
    </div>
  )
}
