import { z } from 'zod'
import { formatCurrency, formatDecimal } from '@/utils/number-input'

/**
 * O formulário inteiro da Nova simulação, num schema só. É a fonte de verdade da estrutura e da
 * validação: o tipo do formulário sai daqui (`SimulationFormData`) e nenhum outro lugar o repete.
 *
 * Os limites de cada número são os de `motor/src/arco_motor/tipos.py`, o mesmo que a API aplica.
 * Nada aqui inventa regra: onde o motor tem `gt=0`, o schema diz "maior que 0".
 *
 * Número digitado é texto ("0,85") e assim fica no formulário. O schema só confere que o texto é
 * um número dentro do limite; virar `number` é de `paraNumero`, na hora de montar o pedido.
 */

export const modalities = ['bateria', 'equipamento', 'combinada'] as const
export const sources = ['eolica', 'solar', 'ambas'] as const
export const scenarios = ['conservador', 'referencia', 'otimista'] as const

const REQUIRED = 'Campo obrigatório.'
const INVALID_NUMBER = 'Informe um valor válido.'

type Rule = {
  required?: boolean
  integer?: boolean
  /** Dinheiro: os limites aparecem nas mensagens como "R$ 100,00". */
  money?: boolean
  min?: number
  exclusiveMin?: number
  max?: number
  exclusiveMax?: number
}

/**
 * Campo numérico, `number | null`. `null` é campo vazio e só passa quando ele não é obrigatório:
 * vazio nunca vira zero. Os limites são os do motor, e as mensagens dizem o limite em palavras.
 */
function numberField(rule: Rule = {}) {
  const limit = (value: number) =>
    rule.money ? formatCurrency(value) : value.toLocaleString('pt-BR')

  return z
    .number({ error: INVALID_NUMBER })
    .nullable()
    .superRefine((value, ctx) => {
      const fail = (message: string) => ctx.addIssue({ code: 'custom', message })

      if (value === null) {
        if (rule.required) fail(REQUIRED)
      } else if (!Number.isFinite(value)) {
        fail(INVALID_NUMBER)
      } else if (rule.integer && !Number.isInteger(value)) {
        fail('Informe um número inteiro.')
      } else if (rule.min !== undefined && value < rule.min) {
        fail(`Deve ser maior ou igual a ${limit(rule.min)}.`)
      } else if (rule.exclusiveMin !== undefined && value <= rule.exclusiveMin) {
        fail(`Deve ser maior que ${limit(rule.exclusiveMin)}.`)
      } else if (rule.max !== undefined && value > rule.max) {
        fail(`Deve ser menor ou igual a ${limit(rule.max)}.`)
      } else if (rule.exclusiveMax !== undefined && value >= rule.exclusiveMax) {
        fail(`Deve ser menor que ${limit(rule.exclusiveMax)}.`)
      }
    })
}

/** Limite do contrato para `nome` (`PedidoDeSalvamento`). O input usa o mesmo número. */
export const NAME_MAX_CHARACTERS = 200

const step1 = z.object({
  nome: z
    .string()
    .trim()
    .min(1, 'Dê um nome à simulação.')
    .max(NAME_MAX_CHARACTERS, `O nome aceita até ${NAME_MAX_CHARACTERS} caracteres.`),
  /** Opcional: o contrato aceita simulação sem pergunta. */
  pergunta: z.string(),
})

const step2 = z.object({
  fonte: z.enum(sources, { message: 'Escolha a fonte considerada.' }),
  correcao_minutos: z.boolean(),
})

const step3 = z.object({
  modalidade: z.enum(modalities, { message: 'Escolha uma modalidade.' }),
})

/**
 * Bateria e circuito só são obrigatórios na modalidade que os pede, e isso depende da etapa 3:
 * quem exige vazio ou não é o `superRefine` do schema principal. Aqui só o formato.
 */
const step4 = z.object({
  bateria: z.object({
    subestacao: z.string(),
    potencia_mw: numberField({ exclusiveMin: 0 }),
    capacidade_mwh: numberField({ exclusiveMin: 0 }),
    soc_inicial: numberField({ min: 0, max: 1 }),
    soc_min: numberField({ min: 0, max: 1 }),
    soc_max: numberField({ min: 0, max: 1 }),
    eficiencia_ida_volta: numberField({ exclusiveMin: 0, max: 1 }),
    disponibilidade: numberField({ exclusiveMin: 0, max: 1 }),
    degradacao_por_ciclo: numberField({ min: 0, exclusiveMax: 1 }),
    degradacao_por_ano: numberField({ min: 0, exclusiveMax: 1 }),
    vida_util_anos: numberField({ exclusiveMin: 0, integer: true }),
  }),
  equipamento: z.object({
    cod_equipamento: z.string(),
    capacidade_depois_mva: numberField({ exclusiveMin: 0 }),
    ganho_limite_mw: numberField({ min: 0 }),
    disponibilidade: numberField({ exclusiveMin: 0, max: 1 }),
    vida_util_anos: numberField({ exclusiveMin: 0, integer: true }),
  }),
})

const step5 = z.object({
  cenario: z.enum(scenarios, { message: 'Escolha o cenário.' }),
  taxa_desconto_aa: numberField({ required: true, min: 0, exclusiveMax: 1 }),
  horizonte_anos: numberField({ required: true, exclusiveMin: 0, integer: true }),
  capex_reais: numberField({ money: true, required: true, min: 0 }),
  opex_fixo_reais_ano: numberField({ money: true, min: 0 }),
  opex_variavel_reais_mwh: numberField({ money: true, min: 0 }),
  valor_residual_reais: numberField({ money: true, min: 0 }),
  receitas_adicionais_reais_ano: numberField({ money: true, min: 0 }),
  reposicoes: z.array(
    z.object({
      ano: numberField({ required: true, min: 1, integer: true }),
      valor_reais: numberField({ money: true, required: true, min: 0 }),
    }),
  ),
})

export const formSchema = z
  .object({ step1, step2, step3, step4, step5 })
  .superRefine((data, ctx) => {
    const { modalidade: modality } = data.step3
    const { bateria: battery, equipamento: equipment } = data.step4
    const requires = (path: string[], value: string | number | null, message = REQUIRED) => {
      const empty = value === null || (typeof value === 'string' && value.trim() === '')
      if (empty) ctx.addIssue({ code: 'custom', path, message })
    }

    if (modality === 'bateria' || modality === 'combinada') {
      requires(['step4', 'bateria', 'subestacao'], battery.subestacao, 'Escolha uma subestação.')
      requires(['step4', 'bateria', 'potencia_mw'], battery.potencia_mw)
      requires(['step4', 'bateria', 'capacidade_mwh'], battery.capacidade_mwh)

      // Regra do contrato: soc_min <= soc_inicial <= soc_max. Carga inicial vazia assume soc_min,
      // então omitir é sempre seguro; só se confere o que o usuário preencheu, e a faixa
      // invertida é recusada por si, sem depender da carga inicial.
      const { soc_min: minimum, soc_inicial: initialCharge, soc_max: maximum } = battery
      const fail = (field: string, message: string) =>
        ctx.addIssue({ code: 'custom', path: ['step4', 'bateria', field], message })

      if (minimum !== null && maximum !== null && minimum > maximum) {
        fail(
          'soc_min',
          `A carga mínima (${formatDecimal(minimum)}) não pode passar da máxima (${formatDecimal(maximum)}).`,
        )
      } else if (initialCharge !== null) {
        if (minimum !== null && initialCharge < minimum) {
          fail('soc_inicial', `Deve ser maior ou igual à carga mínima (${formatDecimal(minimum)}).`)
        } else if (maximum !== null && initialCharge > maximum) {
          fail('soc_inicial', `Deve ser menor ou igual à carga máxima (${formatDecimal(maximum)}).`)
        }
      }
    }

    if (modality === 'equipamento' || modality === 'combinada') {
      requires(
        ['step4', 'equipamento', 'cod_equipamento'],
        equipment.cod_equipamento,
        'Escolha uma linha.',
      )
      requires(['step4', 'equipamento', 'ganho_limite_mw'], equipment.ganho_limite_mw)
    }
  })

export type SimulationFormData = z.infer<typeof formSchema>
export type Modality = SimulationFormData['step3']['modalidade']

/**
 * Começo do formulário. Os campos opcionais já nascem com o padrão do tipo em `tipos.py` (carga
 * mínima 0 e máxima 1, disponibilidade 1, vida útil do circuito 25, custos e receitas extras 0);
 * `soc_inicial` fica vazio, que assume `soc_min`. O que a premissa do cenário preenche (eficiência, taxa, horizonte...) chega
 * depois, de `GET /premissas`, e só nos campos que o usuário ainda não tocou.
 */
export const initialValues: SimulationFormData = {
  step1: { nome: '', pergunta: '' },
  step2: { fonte: 'eolica', correcao_minutos: true },
  step3: { modalidade: 'combinada' },
  step4: {
    bateria: {
      subestacao: '',
      potencia_mw: null,
      capacidade_mwh: null,
      soc_inicial: null,
      soc_min: 0,
      soc_max: 1,
      eficiencia_ida_volta: null,
      disponibilidade: null,
      degradacao_por_ciclo: null,
      degradacao_por_ano: null,
      vida_util_anos: null,
    },
    equipamento: {
      cod_equipamento: '',
      capacidade_depois_mva: null,
      ganho_limite_mw: null,
      disponibilidade: 1,
      vida_util_anos: 25,
    },
  },
  step5: {
    cenario: 'referencia',
    taxa_desconto_aa: null,
    horizonte_anos: null,
    capex_reais: null,
    opex_fixo_reais_ano: 0,
    opex_variavel_reais_mwh: 0,
    valor_residual_reais: 0,
    receitas_adicionais_reais_ano: 0,
    reposicoes: [],
  },
}

/**
 * Os dados que valem para a modalidade escolhida. Voltar e mudar de modalidade não apaga o que o
 * usuário digitou no bloco que saiu (ele pode voltar atrás), mas o envio não leva bloco que a
 * modalidade não aceita: a API recusa com 422.
 */
export function dataForModality(data: SimulationFormData) {
  const { modalidade: modality } = data.step3
  return {
    ...data,
    step4: {
      bateria: modality === 'equipamento' ? undefined : data.step4.bateria,
      equipamento: modality === 'bateria' ? undefined : data.step4.equipamento,
    },
  }
}
