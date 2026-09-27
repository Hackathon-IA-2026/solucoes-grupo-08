import type { FieldPath } from 'react-hook-form'
import type { Modality, SimulationFormData } from './schema'

export type FormFieldPath = FieldPath<SimulationFormData>

export const STEPS = [1, 2, 3, 4, 5] as const
export type Step = (typeof STEPS)[number]
export const FIRST_STEP: Step = 1
export const LAST_STEP: Step = 5

const batteryFields = [
  'step4.bateria.subestacao',
  'step4.bateria.potencia_mw',
  'step4.bateria.capacidade_mwh',
  'step4.bateria.soc_inicial',
  'step4.bateria.soc_min',
  'step4.bateria.soc_max',
  'step4.bateria.eficiencia_ida_volta',
  'step4.bateria.disponibilidade',
  'step4.bateria.degradacao_por_ciclo',
  'step4.bateria.degradacao_por_ano',
  'step4.bateria.vida_util_anos',
] as const satisfies readonly FormFieldPath[]

const equipmentFields = [
  'step4.equipamento.cod_equipamento',
  'step4.equipamento.capacidade_depois_mva',
  'step4.equipamento.ganho_limite_mw',
  'step4.equipamento.disponibilidade',
  'step4.equipamento.vida_util_anos',
] as const satisfies readonly FormFieldPath[]

/**
 * O que cada etapa valida ao clicar em Continuar. É a única lista: etapa nova ou campo novo se
 * declara aqui e no schema, e a navegação não muda.
 */
export const stepFields: Record<Step, readonly FormFieldPath[]> = {
  1: ['step1.nome', 'step1.pergunta'],
  2: ['step2.fonte', 'step2.correcao_minutos'],
  3: ['step3.modalidade'],
  4: [...batteryFields, ...equipmentFields],
  5: [
    'step5.cenario',
    'step5.taxa_desconto_aa',
    'step5.horizonte_anos',
    'step5.capex_reais',
    'step5.opex_fixo_reais_ano',
    'step5.opex_variavel_reais_mwh',
    'step5.valor_residual_reais',
    'step5.receitas_adicionais_reais_ano',
    'step5.reposicoes',
  ],
}

/**
 * Os campos que a etapa mostra de fato. Na etapa 4 depende da modalidade: bloco que a tela não
 * mostra não bloqueia o avanço, mesmo que tenha sobrado texto dele de uma escolha anterior.
 */
export function visibleFields(step: Step, modality: Modality): FormFieldPath[] {
  if (step !== 4) return [...stepFields[step]]
  return [
    ...(modality === 'equipamento' ? [] : batteryFields),
    ...(modality === 'bateria' ? [] : equipmentFields),
  ]
}

/** Campo de `Configuracao` (o `campo` de `GET /premissas`) → campo deste formulário. */
export function fieldForPremise(field: string): FormFieldPath | undefined {
  const [block, name] = field.split('.')
  const path = block === 'financeira' ? `step5.${name}` : `step4.${field}`
  return Object.values(stepFields)
    .flat()
    .find((existing) => existing === path)
}
