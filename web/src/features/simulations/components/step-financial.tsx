import { Plus, X } from 'lucide-react'
import { Controller, useFieldArray, useFormContext } from 'react-hook-form'
import type { Scenario, ScreenPremises } from '../api/get-premises'
import type { SimulationFormData } from '../form/schema'
import { FieldError, FieldLabel, NumericField, ReadOnlyField } from './form-field'
import { fieldTooltips } from '@/features/saved-simulations/api/field-tooltips'
import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

type StepFinancialProps = {
  premises: ScreenPremises | undefined
  /** Última etapa: o botão final envia o formulário inteiro, e não só avança. */
  isSubmitting: boolean
  onBack: () => void
}

const scenarios: { id: Scenario; label: string }[] = [
  { id: 'conservador', label: 'Conservador' },
  { id: 'referencia', label: 'Referência' },
  { id: 'otimista', label: 'Otimista' },
]

export function StepFinancial({ premises, isSubmitting, onBack }: StepFinancialProps) {
  const { control } = useFormContext<SimulationFormData>()
  const replacements = useFieldArray({ control, name: 'step5.reposicoes' })
  const price = premises?.metodo.find((premise) => premise.id === 'preco_energia')

  return (
    <div>
      <h1 className="text-xl font-semibold text-text-primary">5. Premissas financeiras</h1>

      <section className="mt-6 rounded-lg border border-border bg-surface p-5">
        <div>
          <FieldLabel tooltip={fieldTooltips.cenario}>Cenário</FieldLabel>
          <Controller
            control={control}
            name="step5.cenario"
            render={({ field }) => (
              <ToggleGroup
                type="single"
                value={field.value}
                onValueChange={(value: string) => {
                  if (value) field.onChange(value as Scenario)
                }}
                aria-label="Cenário"
              >
                {scenarios.map((scenario) => (
                  <ToggleGroupItem key={scenario.id} value={scenario.id}>
                    {scenario.label}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
          <FieldError name="step5.cenario" />
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumericField
            name="step5.taxa_desconto_aa"
            label="Taxa de desconto"
            unit="0 a 1 ao ano"
            required
            tooltip={fieldTooltips.taxa}
          />
          <NumericField
            name="step5.horizonte_anos"
            kind="integer"
            label="Horizonte"
            unit="anos"
            required
            tooltip={fieldTooltips.horizonte}
          />
          <NumericField
            name="step5.capex_reais"
            kind="money"
            label="Investimento inicial"
            unit="R$"
            required
            tooltip={fieldTooltips.investimento}
          />
          <NumericField
            name="step5.opex_fixo_reais_ano"
            kind="money"
            label="Custo fixo de operação"
            unit="R$ por ano"
            tooltip="OPEX fixo: gasto anual de operação e manutenção que não depende da energia."
          />
          <NumericField
            name="step5.opex_variavel_reais_mwh"
            kind="money"
            label="Custo variável de operação"
            unit="R$ por MWh"
            tooltip="OPEX variável: gasto por MWh recuperado. Multiplica a energia recuperada de cada ano."
          />
          <NumericField
            name="step5.valor_residual_reais"
            kind="money"
            label="Valor residual"
            unit="R$"
          />
          <ReadOnlyField
            label="Preço da energia"
            tooltip="Valor de cada MWh recuperado, fixo para todo o horizonte. Ponto de partida: 216 R$/MWh, o CMO médio ponderado de 2025 nas meias horas de corte local por confiabilidade — uma premissa proposta, não validada. Não é receita contratada: energia recuperável não é receita capturável."
          >
            {price
              ? `premissa: ${String(price.valor).replace('.', ',')} ${price.unidade ?? ''}`
              : '—'}
          </ReadOnlyField>
          <NumericField
            name="step5.receitas_adicionais_reais_ano"
            kind="money"
            label="Receitas adicionais"
            unit="R$ por ano"
          />
        </div>
      </section>

      <section className="mt-4 rounded-lg border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-text-primary">Reposições</h2>

        {replacements.fields.length === 0 ? (
          <div className="mt-3 flex items-center gap-4 rounded-lg border border-dashed border-border px-4 py-3.5 text-sm text-text-muted">
            <span>Sem reposição.</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="ml-auto"
              onClick={() => replacements.append({ ano: null, valor_reais: null })}
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              Adicionar reposição
            </Button>
          </div>
        ) : (
          <div className="mt-3 flex flex-col gap-3">
            {replacements.fields.map((row, index) => (
              <div key={row.id} className="grid items-start gap-3 sm:grid-cols-[1fr_1fr_auto]">
                <NumericField
                  name={`step5.reposicoes.${index}.ano`}
                  kind="integer"
                  label="Ano da reposição"
                  unit="ano do fluxo"
                  required
                />
                <NumericField
                  name={`step5.reposicoes.${index}.valor_reais`}
                  kind="money"
                  label="Valor da reposição"
                  unit="R$"
                  required
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="mt-5"
                  aria-label={`Remover reposição ${index + 1}`}
                  onClick={() => replacements.remove(index)}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            ))}
            <div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => replacements.append({ ano: null, valor_reais: null })}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Adicionar reposição
              </Button>
            </div>
          </div>
        )}
      </section>

      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Voltar
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Enviando…' : 'Continuar para revisão'}
        </Button>
      </div>
    </div>
  )
}
