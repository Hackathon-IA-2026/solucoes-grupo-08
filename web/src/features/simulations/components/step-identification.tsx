import { useFormContext } from 'react-hook-form'
import { NAME_MAX_CHARACTERS, type SimulationFormData } from '../form/schema'
import { FieldError } from './form-field'
import { RestrictionPickerDialog } from './restriction-picker-dialog'
import type { DetailedRestriction } from '@/features/restrictions/api/get-restriction'
import { sourceLabels } from '@/features/restrictions/api/get-restrictions'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { InfoTooltip } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'
import { formatInteger, formatMWhAsGWh, truncateText } from '@/utils/format'

type StepIdentificationProps = {
  restriction: DetailedRestriction
  /** Falso em "Criar revisão": a revisão pertence à simulação, e a simulação, à restrição. */
  canSwapRestriction?: boolean
  onCancel: () => void
  onContinue: () => void
}

export function StepIdentification({
  restriction,
  canSwapRestriction = true,
  onCancel,
  onContinue,
}: StepIdentificationProps) {
  const { register, getFieldState, formState } = useFormContext<SimulationFormData>()
  const invalidName = Boolean(getFieldState('step1.nome', formState).error)

  return (
    <div>
      <h1 className="text-xl font-semibold text-text-primary">1. Identificação</h1>

      <div className="mt-6 rounded-lg border border-border bg-surface p-6">
        <label htmlFor="simulation-name" className="text-sm font-medium text-text-primary">
          Nome da simulação
        </label>
        <Input
          id="simulation-name"
          placeholder="Ex.: Bateria 100 MW / 400 MWh — referência"
          maxLength={NAME_MAX_CHARACTERS}
          aria-invalid={invalidName}
          containerClassName={cn('mt-2', invalidName && 'border-danger')}
          {...register('step1.nome')}
        />
        <FieldError name="step1.nome" />

        <label
          htmlFor="simulation-question"
          className="mt-5 block text-sm font-medium text-text-primary"
        >
          Pergunta que esta simulação responde{' '}
          <span className="font-normal text-text-muted">opcional</span>
        </label>
        <Textarea
          id="simulation-question"
          className="mt-2"
          rows={3}
          {...register('step1.pergunta')}
          placeholder="Ex.: se uma bateria nesta restrição existisse nos últimos 12 meses, quanto corte teria evitado, e isso se paga?"
        />
      </div>

      <div className="mt-4 rounded-lg border border-border bg-surface p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-medium text-text-primary">Restrição desta simulação</h2>
          {canSwapRestriction && <RestrictionPickerDialog currentRestrictionId={restriction.id} />}
        </div>

        <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-sm font-medium text-text-secondary">Nome curto</p>
            <p className="mt-0.5 text-sm font-medium text-text-primary">
              {restriction.nome_curto ?? truncateText(restriction.texto, 60)}
            </p>
          </div>
          <div>
            <p className="text-sm font-medium text-text-secondary">Energia cortada, 12 meses</p>
            <p className="mt-0.5 text-sm text-text-primary">
              {formatMWhAsGWh(restriction.energia_mwh)} GWh
            </p>
          </div>
          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-text-secondary">
              Origem · razão · fonte
              <InfoTooltip label="Ajuda: Origem · razão · fonte">
                LOC: corte local, num conjunto de usinas atrás de um equipamento. CNF: razão
                confiabilidade elétrica. Fonte: eólica, solar ou ambas. O ARCO só simula restrições
                LOC e CNF.
              </InfoTooltip>
            </p>
            <p className="mt-0.5 text-sm text-text-primary">
              {restriction.origem} · {restriction.razao} · {sourceLabels[restriction.fonte]}
            </p>
          </div>
          <div>
            <p className="text-sm font-medium text-text-secondary">Equipamentos</p>
            <p className="mt-0.5 text-sm text-text-primary">
              {formatInteger(restriction.equipamentos.length)}{' '}
              {restriction.equipamentos.length === 1 ? 'linha' : 'linhas'}
            </p>
          </div>
          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-text-secondary">
              Capacidades cadastradas
              <InfoTooltip label="Ajuda: Capacidades cadastradas">
                Capacidade de longa duração de cada linha, em MVA, do cadastro do ONS. Contexto, não
                base de cálculo: o que parametriza o circuito novo é o ganho de limite em MW.
              </InfoTooltip>
            </p>
            <RegisteredCapacities restriction={restriction} />
          </div>
          <div>
            <p className="flex items-center gap-1.5 text-sm font-medium text-text-secondary">
              Instrução de Operação
              <InfoTooltip label="Ajuda: Instrução de Operação">
                Documento do ONS que fixa o limite desta restrição. O código, como IO-ON.NE.5NE, é o
                que o operador usa para achar a regra.
              </InfoTooltip>
            </p>
            <p className="mt-0.5 text-sm text-text-muted">
              {restriction.instrucao_operacao ?? '—'}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="button" onClick={onContinue}>
          Continuar para período
        </Button>
      </div>
    </div>
  )
}

/** Uma capacidade por linha, lado a lado: com mais de uma linha não existe capacidade agregada. */
function RegisteredCapacities({ restriction }: { restriction: DetailedRestriction }) {
  const capacities = restriction.equipamentos.map((row) => row.capacidade_longa_mva)
  if (capacities.every((value) => value == null)) {
    return <p className="mt-0.5 text-sm text-warning">sem cadastro</p>
  }

  return (
    <p className="mt-0.5 text-sm text-text-primary">
      {capacities
        .map((value) => (value == null ? 'sem cadastro' : formatInteger(value)))
        .join(' · ')}{' '}
      MVA
    </p>
  )
}
