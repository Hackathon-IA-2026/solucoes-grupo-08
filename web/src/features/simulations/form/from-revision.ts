import { sources, initialValues, type SimulationFormData } from './schema'
import type { FullRevision } from '@/features/saved-simulations/api/get-simulation'

/**
 * O valor de uma premissa usada, como booleano. `premissas_usadas` guarda o que a revisão de
 * fato calculou, e não o padrão de hoje.
 */
function asBoolean(value: string | number | boolean | undefined, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback
}

/** O mesmo, para `fonte_geracao`: só aceita um dos três valores do contrato. */
function asSource(
  value: string | number | boolean | undefined,
  fallback: SimulationFormData['step2']['fonte'],
): SimulationFormData['step2']['fonte'] {
  return typeof value === 'string' && (sources as readonly string[]).includes(value)
    ? (value as SimulationFormData['step2']['fonte'])
    : fallback
}

/**
 * Preenche o formulário com o que uma revisão salva já tem, para "Criar revisão" reabrir a
 * Nova simulação como cópia dela — o usuário edita a partir de valores reais, não do padrão do
 * tipo. Vem de `GET /simulacoes/{revisao_id}`.
 *
 * `configuracao` grava tudo que o cálculo usou: campo opcional omitido no envio já chega aqui
 * com o padrão do tipo, exceto `soc_inicial`, que continua `null` quando a revisão assumiu a
 * carga mínima. O bloco que a modalidade da revisão não tinha (bateria ou equipamento) volta ao
 * vazio do formulário, para os campos existirem mesmo que o usuário troque de modalidade.
 *
 * `fonte` e `correcao_minutos` não são campos de `configuracao`: entram pela premissa carimbada
 * em `premissas_usadas` (feature 15, `fonte_geracao`). Revisão calculada antes dessa mudança não
 * tem `fonte_geracao` no que guardou, e cai no padrão eólica — não há como recuperá-la depois.
 *
 * `nome`/`pergunta` a API ignora ao revisar — são da simulação, fixados ao criar —, mas entram
 * aqui do mesmo jeito: o usuário vê o que já existe, mesmo sabendo que editá-los aqui não pega.
 */
export function formDataFromRevision(revision: FullRevision): SimulationFormData {
  const { configuracao: config, premissas_usadas: premises } = revision

  return {
    step1: { nome: revision.nome, pergunta: revision.pergunta ?? '' },
    step2: {
      fonte: asSource(premises.fonte_geracao?.valor, 'eolica'),
      correcao_minutos: asBoolean(premises.correcao_minutos?.valor, true),
    },
    step3: { modalidade: config.modalidade },
    step4: {
      bateria: config.bateria
        ? { ...config.bateria, soc_inicial: config.bateria.soc_inicial ?? null }
        : initialValues.step4.bateria,
      equipamento: config.equipamento
        ? {
            ...config.equipamento,
            capacidade_depois_mva: config.equipamento.capacidade_depois_mva ?? null,
          }
        : initialValues.step4.equipamento,
    },
    step5: {
      cenario: config.financeira.cenario,
      taxa_desconto_aa: config.financeira.taxa_desconto_aa,
      horizonte_anos: config.financeira.horizonte_anos,
      capex_reais: config.financeira.capex_reais,
      opex_fixo_reais_ano: config.financeira.opex_fixo_reais_ano,
      opex_variavel_reais_mwh: config.financeira.opex_variavel_reais_mwh,
      valor_residual_reais: config.financeira.valor_residual_reais,
      receitas_adicionais_reais_ano: config.financeira.receitas_adicionais_reais_ano,
      reposicoes: (config.financeira.reposicoes ?? []).map((row) => ({
        ano: row.ano,
        valor_reais: row.valor_reais,
      })),
    },
  }
}
