import { dataForModality, type SimulationFormData } from './schema'
import type { SaveRequest } from '../api/save-simulation'

/**
 * De onde a revisão parte. `create`: simulação nova, sob a restrição escolhida. `revise`: revisão
 * nova de uma simulação existente — a restrição vem dela, nunca do pedido, e por isso não se
 * manda aqui (o invariante é uma simulação, uma restrição).
 */
export type SubmitOrigin =
  { mode: 'create'; restrictionId: string } | { mode: 'revise'; simulationId: number }

/** Campo opcional vazio (`null`) some do pedido, e a API aplica o padrão do tipo. */
function optionalNumber(value: number | null): number | undefined {
  return value ?? undefined
}

/** Só se chama com dados que já passaram pelo `formSchema`: obrigatório vazio aqui é defeito. */
function requiredNumber(value: number | null, field: string): number {
  if (value === null) throw new Error(`Campo obrigatório sem valor: ${field}.`)
  return value
}

/**
 * Traduz o formulário para o corpo de `POST /simulacoes`.
 *
 * Os números já são `number` no formulário, sem conversão de texto: aqui só se escolhe o que vai. O bloco que a modalidade não aceita não vai (a API recusa com 422).
 */
export function buildRequest(origin: SubmitOrigin, data: SimulationFormData): SaveRequest {
  const { step1, step2, step3, step4, step5 } = dataForModality(data)
  const { bateria: battery, equipamento: equipment } = step4

  return {
    restricao_id: origin.mode === 'create' ? origin.restrictionId : undefined,
    simulacao_id: origin.mode === 'revise' ? origin.simulationId : undefined,
    nome: step1.nome.trim(),
    pergunta: step1.pergunta.trim() || null,
    // Quem salva pelo formulário é uma pessoa; `por_agente` é só das revisões da exploração.
    procedencia: 'por_pessoa',
    fonte: step2.fonte,
    correcao_minutos: step2.correcao_minutos,
    configuracao: {
      modalidade: step3.modalidade,
      bateria: battery && {
        subestacao: battery.subestacao,
        potencia_mw: requiredNumber(battery.potencia_mw, 'potencia_mw'),
        capacidade_mwh: requiredNumber(battery.capacidade_mwh, 'capacidade_mwh'),
        soc_inicial: optionalNumber(battery.soc_inicial),
        soc_min: optionalNumber(battery.soc_min),
        soc_max: optionalNumber(battery.soc_max),
        eficiencia_ida_volta: optionalNumber(battery.eficiencia_ida_volta),
        disponibilidade: optionalNumber(battery.disponibilidade),
        degradacao_por_ciclo: optionalNumber(battery.degradacao_por_ciclo),
        degradacao_por_ano: optionalNumber(battery.degradacao_por_ano),
        vida_util_anos: optionalNumber(battery.vida_util_anos),
      },
      equipamento: equipment && {
        tipo: 'adicao_circuito',
        cod_equipamento: equipment.cod_equipamento,
        ganho_limite_mw: requiredNumber(equipment.ganho_limite_mw, 'ganho_limite_mw'),
        capacidade_depois_mva: optionalNumber(equipment.capacidade_depois_mva),
        disponibilidade: optionalNumber(equipment.disponibilidade),
        vida_util_anos: optionalNumber(equipment.vida_util_anos),
      },
      financeira: {
        cenario: step5.cenario,
        taxa_desconto_aa: requiredNumber(step5.taxa_desconto_aa, 'taxa_desconto_aa'),
        horizonte_anos: requiredNumber(step5.horizonte_anos, 'horizonte_anos'),
        capex_reais: requiredNumber(step5.capex_reais, 'capex_reais'),
        opex_fixo_reais_ano: optionalNumber(step5.opex_fixo_reais_ano),
        opex_variavel_reais_mwh: optionalNumber(step5.opex_variavel_reais_mwh),
        valor_residual_reais: optionalNumber(step5.valor_residual_reais),
        receitas_adicionais_reais_ano: optionalNumber(step5.receitas_adicionais_reais_ano),
        reposicoes: step5.reposicoes.map((row) => ({
          ano: requiredNumber(row.ano, 'ano'),
          valor_reais: requiredNumber(row.valor_reais, 'valor_reais'),
        })),
      },
    },
  }
}
