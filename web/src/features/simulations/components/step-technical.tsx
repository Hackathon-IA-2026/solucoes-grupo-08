import { modalityOptions } from '../api/simulation-modality'
import type { Modality, SimulationFormData } from '../form/schema'
import { useFormContext, useWatch } from 'react-hook-form'
import { FieldError, FieldLabel, NumericField, ReadOnlyField } from './form-field'
import type { DetailedRestriction } from '@/features/restrictions/api/get-restriction'
import { fieldTooltips } from '@/features/saved-simulations/api/field-tooltips'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { cn } from '@/utils/cn'
import { capitalizeFirst, formatInteger } from '@/utils/format'

type StepTechnicalProps = {
  restriction: DetailedRestriction
  modality: Modality
  onBack: () => void
  onContinue: () => void
}

export function StepTechnical({ restriction, modality, onBack, onContinue }: StepTechnicalProps) {
  const hasBattery = modality === 'bateria' || modality === 'combinada'
  const hasCircuit = modality === 'equipamento' || modality === 'combinada'
  const modalityTitle = modalityOptions.find((option) => option.id === modality)?.title

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold text-text-primary">4. Configuração técnica</h1>
        {modalityTitle && <Badge variant="outline">{modalityTitle}</Badge>}
      </div>

      <div className="mt-6 flex flex-col gap-4">
        {hasBattery && <BatterySection restriction={restriction} />}
        {hasCircuit && <CircuitSection restriction={restriction} />}
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Voltar
        </Button>
        <Button type="button" onClick={onContinue}>
          Continuar para premissas financeiras
        </Button>
      </div>
    </div>
  )
}

function BatterySection({ restriction }: { restriction: DetailedRestriction }) {
  const { register } = useFormContext<SimulationFormData>()
  const substations = restriction.subestacoes

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold text-text-primary">Bateria</h2>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="sm:col-span-2 lg:col-span-3">
          <FieldLabel
            htmlFor="campo-bateria-subestacao"
            required
            tooltip={fieldTooltips.subestacao}
          >
            Ponto de conexão da bateria
          </FieldLabel>
          <Select id="campo-bateria-subestacao" {...register('step4.bateria.subestacao')}>
            <option value="">Escolha uma subestação</option>
            {substations.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
          <FieldError name="step4.bateria.subestacao" />
        </div>

        <NumericField
          name="step4.bateria.potencia_mw"
          label="Potência da bateria"
          unit="MW"
          required
        />
        <NumericField
          name="step4.bateria.capacidade_mwh"
          label="Capacidade da bateria"
          unit="MWh"
          required
        />
        <NumericField
          name="step4.bateria.soc_inicial"
          label="Carga no início da janela"
          placeholder="Assume a carga mínima"
          unit="0 a 1"
        />
        <NumericField name="step4.bateria.soc_min" label="Carga mínima" unit="0 a 1" />
        <NumericField name="step4.bateria.soc_max" label="Carga máxima" unit="0 a 1" />
        <NumericField
          name="step4.bateria.eficiencia_ida_volta"
          label="Eficiência de ida e volta"
          unit="0 a 1"
          tooltip={fieldTooltips.eficiencia}
          help="Pesa na devolução."
        />
        <NumericField
          name="step4.bateria.disponibilidade"
          label="Disponibilidade da bateria"
          unit="0 a 1"
        />
        <NumericField
          name="step4.bateria.degradacao_por_ciclo"
          label="Degradação por ciclo"
          unit="0 a 1"
        />
        <NumericField
          name="step4.bateria.degradacao_por_ano"
          label="Degradação por ano"
          unit="0 a 1"
        />
        <NumericField
          name="step4.bateria.vida_util_anos"
          kind="integer"
          label="Vida útil da bateria"
          unit="anos"
        />
      </div>
    </section>
  )
}

function CircuitSection({ restriction }: { restriction: DetailedRestriction }) {
  const { register } = useFormContext<SimulationFormData>()
  const lines = restriction.equipamentos
  const selectedCode = useWatch<SimulationFormData, 'step4.equipamento.cod_equipamento'>({
    name: 'step4.equipamento.cod_equipamento',
  })
  const selectedLine = lines.find((line) => line.cod_equipamento === selectedCode)

  return (
    <section className="rounded-lg border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold text-text-primary">Circuito novo</h2>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ReadOnlyField label="Tipo de intervenção">Adição de circuito</ReadOnlyField>
      </div>

      <div className="mt-4" role="radiogroup" aria-label="Linha que recebe o circuito novo">
        <FieldLabel required>Linha que recebe o circuito novo</FieldLabel>
        <div className="flex flex-col gap-2">
          {lines.map((line) => {
            const isSelected = line.cod_equipamento === selectedCode
            return (
              <label
                key={line.cod_equipamento}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-focus',
                  isSelected ? 'border-primary' : 'border-border hover:border-text-muted',
                )}
              >
                <input
                  type="radio"
                  value={line.cod_equipamento}
                  className="h-4 w-4 accent-primary"
                  {...register('step4.equipamento.cod_equipamento')}
                />
                <span className="text-sm font-medium text-text-primary">
                  {line.nome ?? line.cod_equipamento}
                </span>
                <Badge variant="outline">{capitalizeFirst(line.papel)}</Badge>
                <span
                  className={cn(
                    'ml-auto text-sm',
                    line.capacidade_longa_mva ? 'text-text-secondary' : 'text-text-muted',
                  )}
                >
                  {line.capacidade_longa_mva
                    ? `${formatInteger(line.capacidade_longa_mva)} MVA`
                    : 'cadastro não informa a capacidade'}
                </span>
              </label>
            )
          })}
        </div>
        <FieldError name="step4.equipamento.cod_equipamento" />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <ReadOnlyField label="Capacidade do circuito existente">
          {selectedLine?.capacidade_longa_mva
            ? `${formatInteger(selectedLine.capacidade_longa_mva)} MVA`
            : selectedLine
              ? 'cadastro não informa'
              : 'escolha uma linha'}
        </ReadOnlyField>
        <NumericField
          name="step4.equipamento.capacidade_depois_mva"
          label="Capacidade depois da adição"
          unit="MVA"
        />
        <NumericField
          name="step4.equipamento.ganho_limite_mw"
          label="Ganho de limite"
          unit="MW"
          required
          tooltip={fieldTooltips.ganho}
        />
        <NumericField
          name="step4.equipamento.disponibilidade"
          label="Disponibilidade do circuito"
          unit="0 a 1"
        />
        <NumericField
          name="step4.equipamento.vida_util_anos"
          kind="integer"
          label="Vida útil do circuito"
          unit="anos"
        />
      </div>
    </section>
  )
}
