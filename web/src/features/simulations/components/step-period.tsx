import { ArrowRight } from 'lucide-react'
import { Controller, useFormContext } from 'react-hook-form'
import type { SimulationFormData } from '../form/schema'
import { simulationWindow } from '../api/simulation-period'
import { useSnapshot } from '@/features/snapshot/api/get-snapshot'
import type { Source } from '@/features/restrictions/api/get-restrictions'
import { FieldError } from './form-field'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { InfoTooltip } from '@/components/ui/tooltip'

type StepPeriodProps = {
  onBack: () => void
  onContinue: () => void
}

export function StepPeriod({ onBack, onContinue }: StepPeriodProps) {
  const { control } = useFormContext<SimulationFormData>()
  const snapshot = useSnapshot()
  const window = simulationWindow(snapshot.data)

  return (
    <div>
      <h1 className="text-xl font-semibold text-text-primary">2. Período</h1>

      <div className="mt-6 rounded-lg border border-border bg-surface p-6">
        <h2 className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
          Janela analisada
          <InfoTooltip label="Ajuda: Janela analisada">
            Os últimos 12 meses completos publicados pelo ONS. É única e fixa: o dado com texto de
            restrição só existe desde setembro de 2025.
          </InfoTooltip>
        </h2>

        {!window ? (
          <p className="mt-3 text-sm text-text-muted">
            {snapshot.isPending
              ? 'Carregando a janela do snapshot…'
              : snapshot.isError
                ? `Não foi possível carregar a janela: ${snapshot.error.message}`
                : 'O snapshot não declara a janela analisada.'}
          </p>
        ) : (
          <>
            <div className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-12">
              {window.months.map((month) => (
                <div
                  key={`${month.label}-${month.year}`}
                  className="rounded-lg border border-primary bg-primary-light py-2 text-center"
                >
                  <p className="text-sm font-medium text-primary">{month.label}</p>
                  <p className="text-sm text-primary">{month.year}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-4">
              <PeriodEdge label="Início" value={window.start} />
              <ArrowRight className="h-4.5 w-4.5 shrink-0 text-text-muted" aria-hidden="true" />
              <PeriodEdge label="Fim" value={window.end} />
            </div>
          </>
        )}
      </div>

      <section className="mt-4 flex flex-col gap-3.5 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-base font-semibold leading-6 text-text-primary">
          Como o corte do período é lido
        </h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex items-start gap-3">
            <Controller
              control={control}
              name="step2.correcao_minutos"
              render={({ field }) => (
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-label="Correção pelos minutos dentro da meia hora"
                  id="half-hour-correction"
                />
              )}
            />
            <label htmlFor="half-hour-correction">
              <span className="flex items-center gap-1.5 font-semibold text-text-primary">
                Correção pelos minutos dentro da meia hora
                <InfoTooltip label="Ajuda: Correção pelos minutos dentro da meia hora">
                  O ONS registra a potência média da meia hora e quantos minutos dela tiveram corte.
                  Ligada, a correção recompõe o pico: 100 MW médios em 10 minutos viram 300 MW de
                  pico, e é contra o pico que bateria e circuito são dimensionados. A energia da
                  meia hora não muda. Só eólica na v1.
                </InfoTooltip>
              </span>
              <span className="block text-sm leading-5 text-text-secondary">
                Ligada por padrão. Só eólica na v1.
              </span>
            </label>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1.5 text-sm font-semibold text-text-secondary">
              Fonte considerada
              <InfoTooltip label="Ajuda: Fonte considerada">
                Qual série de corte alimenta o cálculo: eólica, solar ou a soma das duas. Na v1 só
                eólica está disponível.
              </InfoTooltip>
            </span>
            <Controller
              control={control}
              name="step2.fonte"
              render={({ field }) => (
                <ToggleGroup
                  type="single"
                  value={field.value}
                  onValueChange={(value: string) => {
                    if (value) field.onChange(value as Source)
                  }}
                  aria-label="Fonte de geração considerada nesta simulação"
                  className="self-start"
                >
                  <ToggleGroupItem value="eolica">Eólica</ToggleGroupItem>
                  <ToggleGroupItem value="solar" disabled title="Ainda não implementado">
                    Solar
                  </ToggleGroupItem>
                  <ToggleGroupItem value="ambas" disabled title="Ainda não implementado">
                    Ambas
                  </ToggleGroupItem>
                </ToggleGroup>
              )}
            />
            <FieldError name="step2.fonte" />
          </div>
        </div>
      </section>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Voltar
        </Button>
        <Button type="button" onClick={onContinue}>
          Continuar para modalidade
        </Button>
      </div>
    </div>
  )
}

/** Uma ponta da janela: a data em destaque e a hora ao lado, mais discreta. */
function PeriodEdge({ label, value }: { label: string; value: { date: string; time: string } }) {
  const { date, time } = value

  return (
    <div className="flex grow flex-col gap-1 rounded-lg border border-border bg-surface-secondary px-5 py-3.5">
      <span className="text-[0.6875rem] font-semibold uppercase tracking-[0.04em] text-text-secondary">
        {label}
      </span>
      <span className="text-xl font-semibold text-text-primary">
        {date} <span className="text-sm font-normal text-text-muted">{time}</span>
      </span>
    </div>
  )
}
